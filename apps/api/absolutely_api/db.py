from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any

from .embeddings import EMBEDDING_MODEL_NAME, compose_embedding_text, vectorize_text
from .models import ActorType, CommandEvent
from .redaction import redact_text, redact_value
from .schema import create_schema, utc_now_iso


def stable_id(*parts: str) -> str:
    payload = "\x1f".join(parts)
    return sha256(payload.encode("utf-8")).hexdigest()


def isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)


def open_database(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def initialize_database(conn: sqlite3.Connection) -> None:
    create_schema(conn)


def _upsert_session(conn: sqlite3.Connection, event: CommandEvent) -> str:
    session_row_id = stable_id("session", event.host, event.session_id)
    started_at = isoformat(event.timestamp_start)
    last_seen_at = isoformat(event.timestamp_end or event.timestamp_start)
    conn.execute(
        """
        INSERT INTO sessions (
            id,
            session_key,
            host,
            shell,
            started_at,
            last_seen_at,
            ended_at,
            session_type,
            metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(host, session_key) DO UPDATE SET
            id = excluded.id,
            host = excluded.host,
            shell = excluded.shell,
            started_at = MIN(sessions.started_at, excluded.started_at),
            last_seen_at = MAX(sessions.last_seen_at, excluded.last_seen_at),
            ended_at = COALESCE(sessions.ended_at, excluded.ended_at),
            metadata_json = excluded.metadata_json
        """,
        (
            session_row_id,
            event.session_id,
            event.host,
            event.shell,
            started_at,
            last_seen_at,
            None,
            "terminal",
            to_json(redact_value(event.metadata)),
        ),
    )
    return session_row_id


def _upsert_repository(conn: sqlite3.Connection, event: CommandEvent) -> str | None:
    if not event.repository_root:
        return None
    root_path = str(Path(event.repository_root).expanduser().resolve(strict=False))
    repository_name = event.repository_name or Path(root_path).name
    repository_id = stable_id("repository", event.host, root_path)
    first_seen_at = isoformat(event.timestamp_start)
    last_seen_at = isoformat(event.timestamp_end or event.timestamp_start)
    conn.execute(
        """
        INSERT INTO repositories (
            id,
            host,
            name,
            root_path,
            branch,
            current_commit_hash,
            first_seen_at,
            last_seen_at,
            metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(host, root_path) DO UPDATE SET
            id = excluded.id,
            name = excluded.name,
            branch = COALESCE(excluded.branch, repositories.branch),
            current_commit_hash = COALESCE(excluded.current_commit_hash, repositories.current_commit_hash),
            first_seen_at = MIN(repositories.first_seen_at, excluded.first_seen_at),
            last_seen_at = MAX(repositories.last_seen_at, excluded.last_seen_at),
            metadata_json = excluded.metadata_json
        """,
        (
            repository_id,
            event.host,
            repository_name,
            root_path,
            event.git_branch,
            event.git_commit_hash,
            first_seen_at,
            last_seen_at,
            to_json(redact_value(event.metadata)),
        ),
    )
    return repository_id


def _upsert_agent(conn: sqlite3.Connection, event: CommandEvent) -> str | None:
    if event.actor_type != ActorType.AGENT and not event.actor_name and not event.agent_session_id:
        return None
    actor_name = event.actor_name or "unknown-agent"
    agent_session_id = event.agent_session_id or ""
    agent_id = stable_id("agent", event.host, event.actor_type.value, actor_name, agent_session_id)
    first_seen_at = isoformat(event.timestamp_start)
    last_seen_at = isoformat(event.timestamp_end or event.timestamp_start)
    conn.execute(
        """
        INSERT INTO agents (
            id,
            host,
            actor_type,
            actor_name,
            agent_session_id,
            first_seen_at,
            last_seen_at,
            metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(host, actor_type, actor_name, agent_session_id) DO UPDATE SET
            id = excluded.id,
            first_seen_at = MIN(agents.first_seen_at, excluded.first_seen_at),
            last_seen_at = MAX(agents.last_seen_at, excluded.last_seen_at),
            metadata_json = excluded.metadata_json
        """,
        (
            agent_id,
            event.host,
            event.actor_type.value,
            actor_name,
            agent_session_id,
            first_seen_at,
            last_seen_at,
            to_json(redact_value(event.metadata)),
        ),
    )
    return agent_id


def _record_embedding(
    conn: sqlite3.Connection,
    *,
    entity_type: str,
    entity_id: str,
    text: str,
    created_at: datetime,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    normalized_text = text.strip()
    if not normalized_text or not entity_id.strip():
        return

    vector = vectorize_text(normalized_text)
    embedding_id = stable_id("embedding", entity_type, entity_id, EMBEDDING_MODEL_NAME)
    conn.execute(
        """
        INSERT INTO embeddings (
            id,
            entity_type,
            entity_id,
            model_name,
            dimensions,
            vector_json,
            created_at,
            metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(entity_type, entity_id, model_name) DO UPDATE SET
            id = excluded.id,
            dimensions = excluded.dimensions,
            vector_json = excluded.vector_json,
            created_at = excluded.created_at,
            metadata_json = excluded.metadata_json
        """,
        (
            embedding_id,
            entity_type,
            entity_id,
            EMBEDDING_MODEL_NAME,
            len(vector),
            to_json(vector),
            isoformat(created_at or datetime.now(timezone.utc)),
            to_json(redact_value(metadata or {})),
        ),
    )


def _looks_like_git_commit(command: str) -> bool:
    normalized = command.strip().lower()
    return (
        normalized.startswith("git commit ")
        or normalized == "git commit"
        or " git commit " in normalized
    )


def _coerce_metadata_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _coerce_commit_timestamp(value: Any, fallback: datetime) -> str:
    if isinstance(value, datetime):
        return isoformat(value) or isoformat(fallback) or ""
    if isinstance(value, (int, float)):
        return isoformat(datetime.fromtimestamp(float(value), tz=timezone.utc)) or ""
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return isoformat(fallback) or ""
        try:
            numeric = float(candidate)
        except ValueError:
            parsed_value = candidate.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(parsed_value)
            except ValueError:
                return isoformat(fallback) or ""
            return isoformat(parsed) or ""
        return isoformat(datetime.fromtimestamp(numeric, tz=timezone.utc)) or ""
    return isoformat(fallback) or ""


def _commit_snapshot_metadata(metadata: Mapping[str, Any]) -> dict[str, Any] | None:
    snapshot = metadata.get("git_commit_snapshot")
    if isinstance(snapshot, Mapping):
        return dict(snapshot)
    return None


def _coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate or candidate == "-":
            return 0
        try:
            return int(candidate)
        except ValueError:
            return 0
    return 0


def _upsert_commit(
    conn: sqlite3.Connection,
    event: CommandEvent,
    *,
    repository_id: str,
    session_record_id: str,
) -> str | None:
    snapshot = _commit_snapshot_metadata(event.metadata)
    commit_hash = (
        (snapshot.get("commit_hash") if snapshot else None)
        or event.git_commit_hash
        or ""
    ).strip()
    if not commit_hash:
        return None
    if not snapshot and not _looks_like_git_commit(event.command):
        return None

    message = ""
    if snapshot is not None:
        message = str(snapshot.get("message") or "").strip()
    if not message:
        message = str(event.metadata.get("git_commit_message") or "").strip()
    if not message:
        message = event.command.strip()
    author_name = None
    if snapshot is not None:
        author_name_value = snapshot.get("author_name")
        if isinstance(author_name_value, str) and author_name_value.strip():
            author_name = author_name_value.strip()
    if not author_name and event.actor_name:
        author_name = event.actor_name

    authored_at = _coerce_commit_timestamp(
        snapshot.get("authored_at") if snapshot is not None else None,
        event.timestamp_start,
    )
    committed_at = _coerce_commit_timestamp(
        snapshot.get("committed_at") if snapshot is not None else None,
        event.timestamp_end,
    )
    diff_summary = None
    if snapshot is not None:
        diff_summary_value = snapshot.get("diff_summary")
        if isinstance(diff_summary_value, str) and diff_summary_value.strip():
            diff_summary = diff_summary_value.strip()

    commit_id = stable_id("commit", repository_id, commit_hash)
    conn.execute(
        """
        INSERT INTO commits (
            id,
            repository_id,
            session_record_id,
            commit_hash,
            message,
            diff_summary,
            author_name,
            authored_at,
            committed_at,
            metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(repository_id, commit_hash) DO UPDATE SET
            id = excluded.id,
            session_record_id = COALESCE(excluded.session_record_id, commits.session_record_id),
            message = excluded.message,
            diff_summary = excluded.diff_summary,
            author_name = COALESCE(excluded.author_name, commits.author_name),
            authored_at = excluded.authored_at,
            committed_at = excluded.committed_at,
            metadata_json = excluded.metadata_json
        """,
        (
            commit_id,
            repository_id,
            session_record_id,
            commit_hash,
            message,
            diff_summary,
            author_name,
            authored_at,
            committed_at,
            to_json(redact_value(snapshot or {})),
        ),
    )

    _record_embedding(
        conn,
        entity_type="commit",
        entity_id=commit_id,
        text=_commit_embedding_text(event, snapshot),
        created_at=event.timestamp_end or event.timestamp_start,
        metadata={"source": "commit"},
    )

    if snapshot is not None:
        _replace_commit_file_changes(conn, repository_id, commit_id, snapshot)

    return commit_id


def _replace_commit_file_changes(
    conn: sqlite3.Connection,
    repository_id: str,
    commit_id: str,
    snapshot: Mapping[str, Any],
) -> None:
    file_changes = snapshot.get("file_changes")
    if not isinstance(file_changes, list):
        return

    conn.execute("DELETE FROM file_changes WHERE commit_id = ?", (commit_id,))
    for index, change in enumerate(file_changes):
        if not isinstance(change, Mapping):
            continue
        path = str(change.get("path") or "").strip()
        if not path:
            continue
        old_path_value = change.get("old_path")
        old_path = (
            str(old_path_value).strip()
            if isinstance(old_path_value, str) and old_path_value.strip()
            else None
        )
        change_type_value = change.get("change_type")
        change_type = (
            str(change_type_value).strip()
            if isinstance(change_type_value, str) and change_type_value.strip()
            else "modified"
        )
        status_value = change.get("status")
        status = (
            str(status_value).strip()
            if isinstance(status_value, str) and status_value.strip()
            else change_type
        )
        raw_value = change.get("raw")
        raw = (
            str(raw_value).strip()
            if isinstance(raw_value, str) and raw_value.strip()
            else path
        )
        lines_added = _coerce_int(change.get("lines_added"))
        lines_removed = _coerce_int(change.get("lines_removed"))
        file_change_id = stable_id(
            "file_change",
            commit_id,
            path,
            old_path or "",
            change_type,
            str(index),
        )
        conn.execute(
            """
            INSERT INTO file_changes (
                id,
                repository_id,
                commit_id,
                path,
                old_path,
                change_type,
                lines_added,
                lines_removed,
                metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                repository_id = excluded.repository_id,
                commit_id = excluded.commit_id,
                path = excluded.path,
                old_path = excluded.old_path,
                change_type = excluded.change_type,
                lines_added = excluded.lines_added,
                lines_removed = excluded.lines_removed,
                metadata_json = excluded.metadata_json
            """,
            (
                file_change_id,
                repository_id,
                commit_id,
                path,
                old_path,
                change_type,
                lines_added,
                lines_removed,
                to_json(redact_value(_coerce_metadata_dict(change))),
            ),
        )


def _command_embedding_text(event: CommandEvent, command: str, stdout: str | None, stderr: str | None) -> str:
    return compose_embedding_text(
        [
            command,
            stdout,
            stderr,
            event.repository_name,
            event.repository_root,
            event.actor_name,
            event.cwd,
            event.git_branch,
            event.git_commit_hash,
            redact_value(event.metadata),
        ]
    )


def _commit_embedding_text(event: CommandEvent, snapshot: Mapping[str, Any] | None) -> str:
    return compose_embedding_text(
        [
            snapshot or {},
            event.repository_name,
            event.repository_root,
            event.actor_name,
            event.git_branch,
            event.git_commit_hash,
            event.command,
        ]
    )


def record_command(conn: sqlite3.Connection, event: CommandEvent) -> str:
    command_result = redact_text(event.command)
    stdout_result = redact_text(event.stdout) if event.stdout is not None else None
    stderr_result = redact_text(event.stderr) if event.stderr is not None else None
    findings = list(command_result.findings)
    if stdout_result is not None:
        findings.extend(stdout_result.findings)
    if stderr_result is not None:
        findings.extend(stderr_result.findings)
    unique_findings = tuple(dict.fromkeys(findings))
    session_record_id = _upsert_session(conn, event)
    repository_id = _upsert_repository(conn, event)
    agent_id = _upsert_agent(conn, event)
    command_id = stable_id(
        "command",
        event.host,
        event.session_id,
        isoformat(event.timestamp_start) or "",
        isoformat(event.timestamp_end) or "",
        event.cwd,
        event.command,
        str(event.exit_code),
    )
    conn.execute(
        """
        INSERT INTO commands (
            id,
            session_id,
            session_record_id,
            repository_id,
            repository_name,
            repository_root,
            agent_id,
            command,
            cwd,
            timestamp_start,
            timestamp_end,
            duration_ms,
            exit_code,
            stdout,
            stderr,
            shell,
            host,
            actor_type,
            actor_name,
            agent_session_id,
            git_branch,
            git_commit_hash,
            redaction_findings_json,
            metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            session_record_id = excluded.session_record_id,
            repository_id = excluded.repository_id,
            repository_name = excluded.repository_name,
            repository_root = excluded.repository_root,
            agent_id = excluded.agent_id,
            command = excluded.command,
            cwd = excluded.cwd,
            timestamp_start = excluded.timestamp_start,
            timestamp_end = excluded.timestamp_end,
            duration_ms = excluded.duration_ms,
            exit_code = excluded.exit_code,
            stdout = excluded.stdout,
            stderr = excluded.stderr,
            shell = excluded.shell,
            host = excluded.host,
            actor_type = excluded.actor_type,
            actor_name = excluded.actor_name,
            agent_session_id = excluded.agent_session_id,
            git_branch = excluded.git_branch,
            git_commit_hash = excluded.git_commit_hash,
            redaction_findings_json = excluded.redaction_findings_json,
            metadata_json = excluded.metadata_json
        """,
        (
            command_id,
            event.session_id,
            session_record_id,
            repository_id,
            event.repository_name,
            event.repository_root,
            agent_id,
            command_result.redacted_text,
            event.cwd,
            isoformat(event.timestamp_start),
            isoformat(event.timestamp_end),
            event.duration_ms,
            event.exit_code,
            stdout_result.redacted_text if stdout_result is not None else None,
            stderr_result.redacted_text if stderr_result is not None else None,
            event.shell,
            event.host,
            event.actor_type.value,
            event.actor_name,
            event.agent_session_id,
            event.git_branch,
            event.git_commit_hash,
            to_json(unique_findings),
            to_json(redact_value(event.metadata)),
        ),
    )

    _record_embedding(
        conn,
        entity_type="command",
        entity_id=command_id,
        text=_command_embedding_text(
            event,
            command_result.redacted_text,
            stdout_result.redacted_text if stdout_result is not None else None,
            stderr_result.redacted_text if stderr_result is not None else None,
        ),
        created_at=event.timestamp_end or event.timestamp_start,
        metadata={"source": "command"},
    )

    if repository_id is not None and event.exit_code == 0 and _looks_like_git_commit(event.command):
        _upsert_commit(
            conn,
            event,
            repository_id=repository_id,
            session_record_id=session_record_id,
        )

    conn.commit()
    return command_id


def bootstrap_database(path: str | Path) -> sqlite3.Connection:
    conn = open_database(path)
    initialize_database(conn)
    return conn


def fetch_one(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    return conn.execute(query, params).fetchone()


def now_iso() -> str:
    return utc_now_iso()
