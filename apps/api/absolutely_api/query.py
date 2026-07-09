from __future__ import annotations

from collections.abc import Sequence
import json
import sqlite3
from typing import Any

from .embeddings import (
    EMBEDDING_MODEL_NAME,
    SEMANTIC_GROUPS,
    compose_embedding_text,
    cosine_similarity,
    semantic_concept,
    tokenize,
    vectorize_text,
)


def _json_or_default(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _semantic_concept(token: str) -> str:
    return semantic_concept(token)


def _semantic_token_set(value: str) -> set[str]:
    semantic_tokens: set[str] = set()
    for token in tokenize(value):
        semantic_tokens.add(token)
        semantic_tokens.add(_semantic_concept(token))
    return semantic_tokens


def score_text(query: str, text: str) -> float:
    query = query.strip().lower()
    text = text.strip().lower()
    if not query or not text:
        return 0.0
    query_tokens = _semantic_token_set(query)
    text_tokens = _semantic_token_set(text)
    if not query_tokens or not text_tokens:
        return 0.0
    overlap = query_tokens & text_tokens
    if not overlap and query not in text:
        return 0.0
    coverage = len(overlap) / max(len(query_tokens), 1)
    density = len(overlap) / max(len(text_tokens), 1)
    phrase_bonus = 1.5 if query in text else 0.0
    return round(phrase_bonus + coverage * 2.0 + density + len(overlap) * 0.1, 6)


def _like_terms(query: str) -> list[str]:
    terms = [query.strip()]
    terms.extend(tokenize(query))
    for token in tokenize(query):
        concept = _semantic_concept(token)
        terms.append(concept)
        terms.extend(SEMANTIC_GROUPS.get(concept, ()))
    unique_terms: list[str] = []
    seen: set[str] = set()
    for term in terms:
        normalized = term.lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_terms.append(term)
    return unique_terms


def _add_query_clause(
    clauses: list[str],
    params: dict[str, Any],
    query: str | None,
    fields: Sequence[str],
    *,
    prefix: str,
) -> None:
    if not query:
        return
    term_clauses: list[str] = []
    for index, term in enumerate(_like_terms(query)):
        param_name = f"{prefix}_q_{index}"
        params[param_name] = f"%{_escape_like(term)}%"
        field_checks = [
            f"LOWER(COALESCE({field}, '')) LIKE :{param_name} ESCAPE '\\'"
            for field in fields
        ]
        term_clauses.append("(" + " OR ".join(field_checks) + ")")
    if term_clauses:
        clauses.append("(" + " OR ".join(term_clauses) + ")")


def _add_scalar_filter(
    clauses: list[str],
    params: dict[str, Any],
    field: str,
    value: Any,
    *,
    operator: str = "=",
    param_name: str,
) -> None:
    if value is None:
        return
    clauses.append(f"{field} {operator} :{param_name}")
    params[param_name] = value


def _add_range_filter(
    clauses: list[str],
    params: dict[str, Any],
    field: str,
    *,
    after: str | None = None,
    before: str | None = None,
    prefix: str,
) -> None:
    if after is not None:
        clauses.append(f"{field} >= :{prefix}_after")
        params[f"{prefix}_after"] = after
    if before is not None:
        clauses.append(f"{field} <= :{prefix}_before")
        params[f"{prefix}_before"] = before


def command_row_to_item(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["metadata"] = _json_or_default(item.pop("metadata_json", None), {})
    item["redaction_findings"] = _json_or_default(item.pop("redaction_findings_json", None), [])
    item["session_key"] = item.get("session_id")
    repository_name = item.pop("repository_name", None) or item.pop("repository_name_resolved", None)
    repository_root = item.pop("repository_root", None) or item.pop("repository_root_resolved", None)
    item["repository_name"] = repository_name
    item["repository_root"] = repository_root
    item["kind"] = "command"
    item["title"] = item["command"]
    item["subtitle"] = " · ".join(
        part
        for part in [
            repository_name or repository_root or "no repo",
            item.get("cwd"),
            f"exit {item.get('exit_code')}",
        ]
        if part
    )
    item["timestamp"] = item["timestamp_start"]
    return item


def session_row_to_item(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["metadata"] = _json_or_default(item.pop("metadata_json", None), {})
    item["commands_count"] = int(item.get("commands_count") or 0)
    item["worked_ms"] = int(item.get("worked_ms") or 0)
    item["repositories_count"] = int(item.get("repositories_count") or 0)
    item["actor_count"] = int(item.get("actor_count") or 0)
    item["kind"] = "session"
    item["title"] = item["session_key"]
    item["subtitle"] = " · ".join(
        part
        for part in [
            item.get("host") or "unknown host",
            item.get("shell") or "unknown shell",
            f"{item['commands_count']} commands",
        ]
        if part
    )
    item["timestamp"] = item["started_at"]
    return item


def commit_row_to_item(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["metadata"] = _json_or_default(item.pop("metadata_json", None), {})
    item["kind"] = "commit"
    item["title"] = item["message"]
    item["subtitle"] = " · ".join(
        part
        for part in [
            item.get("repository_name") or "unknown repo",
            item.get("commit_hash", "")[:12],
        ]
        if part
    )
    item["timestamp"] = item["committed_at"]
    return item


def summary_row_to_item(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["metadata"] = _json_or_default(item.pop("metadata_json", None), {})
    item["repositories"] = _json_or_default(item.pop("repositories_json", None), [])
    item["top_tools"] = _json_or_default(item.pop("top_tools_json", None), [])
    item["kind"] = "daily_summary"
    item["title"] = item["summary_date"]
    item["subtitle"] = item.get("summary_text") or ""
    item["timestamp"] = item["created_at"]
    return item


def _command_select_base() -> str:
    return """
        SELECT
            c.*,
            r.name AS repository_name_resolved,
            r.root_path AS repository_root_resolved
        FROM commands c
        LEFT JOIN repositories r ON r.id = c.repository_id
        LEFT JOIN sessions s ON s.id = c.session_record_id
    """


def _command_filters(
    *,
    host: str | None = None,
    session_key: str | None = None,
    repository: str | None = None,
    shell: str | None = None,
    exit_code: int | None = None,
    actor_type: str | None = None,
    actor_name: str | None = None,
    git_commit_hash: str | None = None,
    started_after: str | None = None,
    started_before: str | None = None,
    cwd: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    _add_scalar_filter(clauses, params, "c.host", host, param_name="host")
    if session_key:
        clauses.append("(c.session_id = :session_key OR s.session_key = :session_key)")
        params["session_key"] = session_key
    _add_scalar_filter(clauses, params, "c.shell", shell, param_name="shell")
    _add_scalar_filter(clauses, params, "c.exit_code", exit_code, param_name="exit_code")
    _add_scalar_filter(clauses, params, "c.actor_type", actor_type, param_name="actor_type")
    _add_scalar_filter(clauses, params, "c.actor_name", actor_name, param_name="actor_name")
    _add_scalar_filter(clauses, params, "c.git_commit_hash", git_commit_hash, param_name="git_commit_hash")
    _add_scalar_filter(clauses, params, "c.cwd", cwd, param_name="cwd")
    _add_range_filter(
        clauses,
        params,
        "c.timestamp_start",
        after=started_after,
        before=started_before,
        prefix="started",
    )
    if repository:
        clauses.append(
            "("
            "c.repository_name = :repository OR "
            "c.repository_root = :repository OR "
            "r.name = :repository OR "
            "r.root_path = :repository"
            ")"
        )
        params["repository"] = repository
    return clauses, params


def _session_filters(
    *,
    host: str | None = None,
    shell: str | None = None,
    session_key: str | None = None,
    session_type: str | None = None,
    started_after: str | None = None,
    started_before: str | None = None,
    active: bool | None = None,
    query: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    _add_scalar_filter(clauses, params, "s.host", host, param_name="host")
    _add_scalar_filter(clauses, params, "s.shell", shell, param_name="shell")
    _add_scalar_filter(clauses, params, "s.session_key", session_key, param_name="session_key")
    _add_scalar_filter(clauses, params, "s.session_type", session_type, param_name="session_type")
    _add_range_filter(
        clauses,
        params,
        "s.started_at",
        after=started_after,
        before=started_before,
        prefix="started",
    )
    if active is True:
        clauses.append("s.ended_at IS NULL")
    elif active is False:
        clauses.append("s.ended_at IS NOT NULL")
    _add_query_clause(
        clauses,
        params,
        query,
        fields=("s.session_key", "s.host", "s.shell", "s.session_type"),
        prefix="session",
    )
    return clauses, params


def list_commands(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
    offset: int = 0,
    query: str | None = None,
    host: str | None = None,
    session_key: str | None = None,
    repository: str | None = None,
    shell: str | None = None,
    exit_code: int | None = None,
    actor_type: str | None = None,
    actor_name: str | None = None,
    git_commit_hash: str | None = None,
    started_after: str | None = None,
    started_before: str | None = None,
    cwd: str | None = None,
) -> list[dict[str, Any]]:
    clauses, params = _command_filters(
        host=host,
        session_key=session_key,
        repository=repository,
        shell=shell,
        exit_code=exit_code,
        actor_type=actor_type,
        actor_name=actor_name,
        git_commit_hash=git_commit_hash,
        started_after=started_after,
        started_before=started_before,
        cwd=cwd,
    )
    _add_query_clause(
        clauses,
        params,
        query,
        fields=(
            "c.command",
            "c.stdout",
            "c.stderr",
            "c.repository_name",
            "c.repository_root",
            "c.actor_name",
            "c.cwd",
            "c.git_branch",
            "c.git_commit_hash",
            "r.name",
            "r.root_path",
        ),
        prefix="command",
    )
    sql = _command_select_base()
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY c.timestamp_start DESC, c.id DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset
    rows = conn.execute(sql, params).fetchall()
    return [command_row_to_item(row) for row in rows]


def list_sessions(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
    offset: int = 0,
    query: str | None = None,
    host: str | None = None,
    shell: str | None = None,
    session_key: str | None = None,
    session_type: str | None = None,
    started_after: str | None = None,
    started_before: str | None = None,
    active: bool | None = None,
) -> list[dict[str, Any]]:
    clauses, params = _session_filters(
        host=host,
        shell=shell,
        session_key=session_key,
        session_type=session_type,
        started_after=started_after,
        started_before=started_before,
        active=active,
        query=query,
    )
    sql = """
        SELECT
            s.*,
            COUNT(c.id) AS commands_count,
            COALESCE(SUM(c.duration_ms), 0) AS worked_ms,
            MIN(c.timestamp_start) AS first_command_at,
            MAX(c.timestamp_end) AS last_command_at,
            COUNT(DISTINCT c.repository_id) AS repositories_count,
            COUNT(DISTINCT c.actor_name) AS actor_count
        FROM sessions s
        LEFT JOIN commands c ON c.session_record_id = s.id
    """
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " GROUP BY s.id ORDER BY s.last_seen_at DESC, s.id DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset
    rows = conn.execute(sql, params).fetchall()
    return [session_row_to_item(row) for row in rows]


def count_sessions(
    conn: sqlite3.Connection,
    *,
    query: str | None = None,
    host: str | None = None,
    shell: str | None = None,
    session_key: str | None = None,
    session_type: str | None = None,
    started_after: str | None = None,
    started_before: str | None = None,
    active: bool | None = None,
) -> int:
    clauses, params = _session_filters(
        host=host,
        shell=shell,
        session_key=session_key,
        session_type=session_type,
        started_after=started_after,
        started_before=started_before,
        active=active,
        query=query,
    )
    sql = """
        SELECT COUNT(*)
        FROM sessions s
    """
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    return int(conn.execute(sql, params).fetchone()[0])


def count_commands(
    conn: sqlite3.Connection,
    *,
    query: str | None = None,
    host: str | None = None,
    session_key: str | None = None,
    repository: str | None = None,
    shell: str | None = None,
    exit_code: int | None = None,
    actor_type: str | None = None,
    actor_name: str | None = None,
    git_commit_hash: str | None = None,
    started_after: str | None = None,
    started_before: str | None = None,
    cwd: str | None = None,
) -> int:
    clauses, params = _command_filters(
        host=host,
        session_key=session_key,
        repository=repository,
        shell=shell,
        exit_code=exit_code,
        actor_type=actor_type,
        actor_name=actor_name,
        git_commit_hash=git_commit_hash,
        started_after=started_after,
        started_before=started_before,
        cwd=cwd,
    )
    _add_query_clause(
        clauses,
        params,
        query,
        fields=(
            "c.command",
            "c.stdout",
            "c.stderr",
            "c.repository_name",
            "c.repository_root",
            "c.actor_name",
            "c.cwd",
            "c.git_branch",
            "c.git_commit_hash",
            "r.name",
            "r.root_path",
        ),
        prefix="command_count",
    )
    sql = """
        SELECT COUNT(*)
        FROM commands c
        LEFT JOIN repositories r ON r.id = c.repository_id
        LEFT JOIN sessions s ON s.id = c.session_record_id
    """
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    return int(conn.execute(sql, params).fetchone()[0])


def list_commits(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
    offset: int = 0,
    query: str | None = None,
    repository: str | None = None,
    committed_after: str | None = None,
    committed_before: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if repository:
        clauses.append("(r.name = :repository OR r.root_path = :repository OR c.repository_id = :repository)")
        params["repository"] = repository
    _add_range_filter(
        clauses,
        params,
        "c.committed_at",
        after=committed_after,
        before=committed_before,
        prefix="committed",
    )
    _add_query_clause(
        clauses,
        params,
        query,
        fields=("c.message", "c.diff_summary", "c.author_name", "r.name", "r.root_path", "c.commit_hash"),
        prefix="commit",
    )
    sql = """
        SELECT
            c.*,
            r.name AS repository_name,
            r.root_path AS repository_root
        FROM commits c
        LEFT JOIN repositories r ON r.id = c.repository_id
    """
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY c.committed_at DESC, c.id DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset
    rows = conn.execute(sql, params).fetchall()
    return [commit_row_to_item(row) for row in rows]


def get_commit(
    conn: sqlite3.Connection,
    *,
    commit_hash: str,
    repository: str | None = None,
) -> dict[str, Any] | None:
    clauses = ["c.commit_hash = :commit_hash"]
    params: dict[str, Any] = {"commit_hash": commit_hash}
    if repository:
        clauses.append("(r.name = :repository OR r.root_path = :repository OR c.repository_id = :repository)")
        params["repository"] = repository
    sql = """
        SELECT
            c.*,
            r.name AS repository_name,
            r.root_path AS repository_root
        FROM commits c
        LEFT JOIN repositories r ON r.id = c.repository_id
    """
    sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY c.committed_at DESC, c.id DESC LIMIT 1"
    row = conn.execute(sql, params).fetchone()
    return commit_row_to_item(row) if row is not None else None


def list_file_changes(
    conn: sqlite3.Connection,
    *,
    commit_id: str,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            fc.*,
            c.commit_hash,
            c.message,
            c.committed_at,
            r.name AS repository_name,
            r.root_path AS repository_root
        FROM file_changes fc
        LEFT JOIN commits c ON c.id = fc.commit_id
        LEFT JOIN repositories r ON r.id = fc.repository_id
        WHERE fc.commit_id = ?
        ORDER BY fc.path ASC, fc.id ASC
        LIMIT ? OFFSET ?
        """,
        (commit_id, limit, offset),
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["metadata"] = _json_or_default(item.pop("metadata_json", None), {})
        item["kind"] = "file_change"
        item["title"] = item.get("path") or ""
        item["subtitle"] = " · ".join(
            part
            for part in [
                item.get("change_type"),
                f"+{item.get('lines_added', 0)}",
                f"-{item.get('lines_removed', 0)}",
            ]
            if part
        )
        item["timestamp"] = item.get("committed_at") or ""
        items.append(item)
    return items


def get_commit_detail(
    conn: sqlite3.Connection,
    *,
    commit_hash: str,
    repository: str | None = None,
    related_limit: int = 100,
) -> dict[str, Any]:
    commit = get_commit(conn, commit_hash=commit_hash, repository=repository)
    related_commands = list_commands(
        conn,
        limit=related_limit,
        git_commit_hash=commit_hash,
        repository=repository,
    )
    file_changes = list_file_changes(
        conn,
        commit_id=commit["id"],
    ) if commit is not None else []
    errors = [] if commit is not None else ["commit not found"]
    return {
        "commit": commit,
        "file_changes": file_changes,
        "related_commands": related_commands,
        "errors": errors,
    }


def list_daily_summaries(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
    offset: int = 0,
    query: str | None = None,
    host: str | None = None,
    summary_date_after: str | None = None,
    summary_date_before: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if host:
        clauses.append("d.host = :host")
        params["host"] = host
    _add_range_filter(
        clauses,
        params,
        "d.summary_date",
        after=summary_date_after,
        before=summary_date_before,
        prefix="summary_date",
    )
    _add_query_clause(
        clauses,
        params,
        query,
        fields=("d.summary_text", "d.mistake_text", "d.repositories_json", "d.top_tools_json", "d.summary_date"),
        prefix="summary",
    )
    sql = """
        SELECT d.*
        FROM daily_summaries d
    """
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY d.summary_date DESC, d.created_at DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset
    rows = conn.execute(sql, params).fetchall()
    return [summary_row_to_item(row) for row in rows]


def list_repositories(conn: sqlite3.Connection, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM repositories
        ORDER BY last_seen_at DESC, name ASC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    return [
        {
            **dict(row),
            "metadata": _json_or_default(row["metadata_json"], {}),
        }
        for row in rows
    ]


def list_agents(conn: sqlite3.Connection, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM agents
        ORDER BY last_seen_at DESC, actor_name ASC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    return [
        {
            **dict(row),
            "metadata": _json_or_default(row["metadata_json"], {}),
        }
        for row in rows
    ]


def _dedupe_items(items: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        kind = str(item.get("kind") or "")
        item_id = str(item.get("id") or "")
        key = (kind, item_id)
        if item_id and key in seen:
            continue
        if item_id:
            seen.add(key)
        deduped.append(item)
    return deduped


def _embedding_vectors_for(
    conn: sqlite3.Connection,
    *,
    entity_type: str,
    entity_ids: Sequence[str],
) -> dict[str, list[float]]:
    ids = [entity_id for entity_id in dict.fromkeys(entity_ids) if entity_id]
    if not ids:
        return {}
    placeholders = ", ".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT entity_id, vector_json
        FROM embeddings
        WHERE entity_type = ?
          AND model_name = ?
          AND entity_id IN ({placeholders})
        """,
        (entity_type, EMBEDDING_MODEL_NAME, *ids),
    ).fetchall()
    return {
        str(row["entity_id"]): [float(component) for component in _json_or_default(row["vector_json"], [])]
        for row in rows
    }


def _search_text_for_item(item: dict[str, Any]) -> str:
    kind = item.get("kind")
    if kind == "command":
        return compose_embedding_text(
            [
                item.get("command"),
                item.get("stdout"),
                item.get("stderr"),
                item.get("repository_name"),
                item.get("repository_root"),
                item.get("actor_name"),
                item.get("cwd"),
                item.get("git_branch"),
                item.get("git_commit_hash"),
            ]
        )
    if kind == "commit":
        return compose_embedding_text(
            [
                item.get("message"),
                item.get("diff_summary"),
                item.get("author_name"),
                item.get("repository_name"),
                item.get("repository_root"),
                item.get("commit_hash"),
            ]
        )
    if kind == "daily_summary":
        return compose_embedding_text(
            [
                item.get("summary_text"),
                item.get("mistake_text"),
                item.get("summary_date"),
                item.get("repositories", []),
                item.get("top_tools", []),
            ]
        )
    return compose_embedding_text(
        [
            item.get("title"),
            item.get("subtitle"),
            item.get("timestamp"),
        ]
    )


def _score_search_item(
    query_vector: list[float],
    query: str,
    item: dict[str, Any],
    embedding_vector: list[float] | None,
) -> float:
    text = _search_text_for_item(item)
    lexical_score = score_text(query, text)
    vector_source = embedding_vector if embedding_vector is not None else vectorize_text(text)
    vector_score = max(0.0, cosine_similarity(query_vector, vector_source))
    return round(lexical_score + vector_score, 6)


def search_records(
    conn: sqlite3.Connection,
    *,
    query: str,
    limit: int = 20,
    host: str | None = None,
    repository: str | None = None,
    actor_type: str | None = None,
    shell: str | None = None,
) -> list[dict[str, Any]]:
    if not query.strip():
        return [
            {**item, "score": 0.0}
            for item in list_commands(
                conn,
                limit=limit,
                host=host,
                repository=repository,
                actor_type=actor_type,
                shell=shell,
            )
        ]

    candidate_limit = max(limit * 20, 500)
    command_candidates = _dedupe_items(
        list_commands(
            conn,
            limit=candidate_limit,
            query=query,
            host=host,
            repository=repository,
            actor_type=actor_type,
            shell=shell,
        )
        + list_commands(
            conn,
            limit=candidate_limit,
            host=host,
            repository=repository,
            actor_type=actor_type,
            shell=shell,
        )
    )
    commit_candidates = _dedupe_items(
        list_commits(
            conn,
            limit=candidate_limit,
            query=query,
            repository=repository,
        )
        + list_commits(
            conn,
            limit=candidate_limit,
            repository=repository,
        )
    )
    summary_candidates = _dedupe_items(
        list_daily_summaries(
            conn,
            limit=candidate_limit,
            query=query,
            host=host,
        )
        + list_daily_summaries(
            conn,
            limit=candidate_limit,
            host=host,
        )
    )

    query_vector = vectorize_text(query)
    command_vectors = _embedding_vectors_for(
        conn,
        entity_type="command",
        entity_ids=[str(item.get("id") or "") for item in command_candidates],
    )
    commit_vectors = _embedding_vectors_for(
        conn,
        entity_type="commit",
        entity_ids=[str(item.get("id") or "") for item in commit_candidates],
    )
    summary_vectors = _embedding_vectors_for(
        conn,
        entity_type="daily_summary",
        entity_ids=[str(item.get("id") or "") for item in summary_candidates],
    )

    results: list[dict[str, Any]] = []
    for item in command_candidates:
        embedding_vector = command_vectors.get(str(item.get("id") or ""))
        score = _score_search_item(query_vector, query, item, embedding_vector)
        if score > 0:
            results.append({**item, "score": score})

    for item in commit_candidates:
        embedding_vector = commit_vectors.get(str(item.get("id") or ""))
        score = _score_search_item(query_vector, query, item, embedding_vector)
        if score > 0:
            results.append({**item, "score": score})

    for item in summary_candidates:
        embedding_vector = summary_vectors.get(str(item.get("id") or ""))
        score = _score_search_item(query_vector, query, item, embedding_vector)
        if score > 0:
            results.append({**item, "score": score})

    if not results:
        return []

    unique_results = _dedupe_items(results)
    unique_results.sort(
        key=lambda item: (
            float(item.get("score", 0.0)),
            item.get("timestamp") or item.get("committed_at") or item.get("created_at") or "",
        ),
        reverse=True,
    )
    return unique_results[:limit]
