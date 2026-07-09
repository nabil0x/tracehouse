from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import argparse
import os
import sqlite3
from typing import Any

from fastmcp import FastMCP

from .db import bootstrap_database, open_database
from .privacy import privacy_status
from .query import (
    command_row_to_item,
    count_commands,
    count_sessions,
    get_commit as query_get_commit,
    get_commit_detail as query_get_commit_detail,
    list_agents as query_list_agents,
    list_commands as query_list_commands,
    list_commits as query_list_commits,
    list_daily_summaries as query_list_daily_summaries,
    list_repositories as query_list_repositories,
    list_sessions as query_list_sessions,
    search_records,
)
from .schema import SCHEMA_VERSION


DEFAULT_DATABASE_PATH = Path.home() / ".local/share/tracehouse/tracehouse.db"
MAX_SEARCH_LIMIT = 50
MAX_LIST_LIMIT = 100
MAX_DETAIL_LIMIT = 100


def resolve_database_path(db_path: str | Path | None) -> Path:
    if db_path is not None:
        return Path(db_path).expanduser()
    env_value = os.environ.get("ABSOLUTELY_DATABASE_PATH", "").strip()
    if env_value:
        return Path(env_value).expanduser()
    return DEFAULT_DATABASE_PATH


def _prepare_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    bootstrap_database(database_path).close()


@contextmanager
def _connection(database_path: Path) -> sqlite3.Connection:
    conn = open_database(database_path)
    try:
        yield conn
    finally:
        conn.close()


def _clamp_limit(value: int, maximum: int) -> int:
    return max(1, min(int(value), maximum))


def _fetch_command(conn: sqlite3.Connection, command_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT
            c.*,
            r.name AS repository_name_resolved,
            r.root_path AS repository_root_resolved
        FROM commands c
        LEFT JOIN repositories r ON r.id = c.repository_id
        WHERE c.id = ?
        LIMIT 1
        """,
        (command_id,),
    ).fetchone()
    return command_row_to_item(row) if row is not None else None


def _fetch_session(
    conn: sqlite3.Connection,
    *,
    session_key: str,
    host: str | None = None,
) -> dict[str, Any] | None:
    items = query_list_sessions(
        conn,
        limit=1,
        offset=0,
        session_key=session_key,
        host=host,
    )
    return items[0] if items else None


def _fetch_repository(conn: sqlite3.Connection, repository: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT *
        FROM repositories
        WHERE id = ? OR name = ? OR root_path = ?
        ORDER BY last_seen_at DESC, name ASC
        LIMIT 1
        """,
        (repository, repository, repository),
    ).fetchone()
    return dict(row) if row is not None else None


def _fetch_agent(
    conn: sqlite3.Connection,
    *,
    actor_name: str,
    host: str | None = None,
    actor_type: str | None = None,
    agent_session_id: str | None = None,
) -> dict[str, Any] | None:
    clauses = ["actor_name = ?"]
    params: list[Any] = [actor_name]
    if host is not None:
        clauses.append("host = ?")
        params.append(host)
    if actor_type is not None:
        clauses.append("actor_type = ?")
        params.append(actor_type)
    if agent_session_id is not None:
        clauses.append("agent_session_id = ?")
        params.append(agent_session_id)
    sql = """
        SELECT *
        FROM agents
    """
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY last_seen_at DESC, actor_name ASC LIMIT 1"
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row is not None else None


def create_mcp_server(db_path: str | Path | None = None) -> FastMCP:
    database_path = resolve_database_path(db_path)
    _prepare_database(database_path)

    mcp = FastMCP(
        "Tracehouse Logs",
        instructions=(
            "Read-only MCP bridge over the local Tracehouse SQLite database. "
            "Use search_logs for discovery, then drill down with the list/get tools."
        ),
        version="0.1.0",
    )

    @mcp.tool
    def database_overview() -> dict[str, Any]:
        """Return the database path, schema version, and privacy posture."""
        with _connection(database_path) as conn:
            return {
                "status": "ok",
                "database_path": str(database_path),
                "schema_version": SCHEMA_VERSION,
                "privacy": privacy_status(conn),
            }

    @mcp.tool
    def search_logs(
        query: str,
        limit: int = 20,
        host: str | None = None,
        repository: str | None = None,
        shell: str | None = None,
        actor_type: str | None = None,
    ) -> dict[str, Any]:
        """Run semantic and lexical search across commands, commits, and daily summaries."""
        if not query.strip():
            raise ValueError("query is required")
        if actor_type is not None and actor_type not in {"human", "agent"}:
            raise ValueError("actor_type must be human or agent")
        limit = _clamp_limit(limit, MAX_SEARCH_LIMIT)
        with _connection(database_path) as conn:
            items = search_records(
                conn,
                query=query,
                limit=limit,
                host=host,
                repository=repository,
                shell=shell,
                actor_type=actor_type,
            )
            return {
                "query": query,
                "limit": limit,
                "total": len(items),
                "items": items,
            }

    @mcp.tool
    def list_commands(
        limit: int = 50,
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
    ) -> dict[str, Any]:
        """List commands with structured filters."""
        limit = _clamp_limit(limit, MAX_LIST_LIMIT)
        offset = max(0, int(offset))
        if actor_type is not None and actor_type not in {"human", "agent"}:
            raise ValueError("actor_type must be human or agent")
        with _connection(database_path) as conn:
            items = query_list_commands(
                conn,
                limit=limit,
                offset=offset,
                query=query,
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
            total = count_commands(
                conn,
                query=query,
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
            return {"items": items, "total": total, "limit": limit, "offset": offset}

    @mcp.tool
    def get_command(command_id: str) -> dict[str, Any]:
        """Fetch a single command row by its command ID."""
        with _connection(database_path) as conn:
            item = _fetch_command(conn, command_id)
            return {"found": item is not None, "item": item}

    @mcp.tool
    def list_sessions(
        limit: int = 50,
        offset: int = 0,
        query: str | None = None,
        host: str | None = None,
        shell: str | None = None,
        session_key: str | None = None,
        session_type: str | None = None,
        started_after: str | None = None,
        started_before: str | None = None,
        active: bool | None = None,
    ) -> dict[str, Any]:
        """List sessions with aggregate command counts and worked time."""
        limit = _clamp_limit(limit, MAX_LIST_LIMIT)
        offset = max(0, int(offset))
        with _connection(database_path) as conn:
            items = query_list_sessions(
                conn,
                limit=limit,
                offset=offset,
                query=query,
                host=host,
                shell=shell,
                session_key=session_key,
                session_type=session_type,
                started_after=started_after,
                started_before=started_before,
                active=active,
            )
            total = count_sessions(
                conn,
                query=query,
                host=host,
                shell=shell,
                session_key=session_key,
                session_type=session_type,
                started_after=started_after,
                started_before=started_before,
                active=active,
            )
            return {"items": items, "total": total, "limit": limit, "offset": offset}

    @mcp.tool
    def get_session(session_key: str, host: str | None = None) -> dict[str, Any]:
        """Fetch a single session by session key, optionally scoped by host."""
        with _connection(database_path) as conn:
            item = _fetch_session(conn, session_key=session_key, host=host)
            return {"found": item is not None, "item": item}

    @mcp.tool
    def list_repositories(limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List repositories seen in the local logs."""
        limit = _clamp_limit(limit, MAX_LIST_LIMIT)
        offset = max(0, int(offset))
        with _connection(database_path) as conn:
            items = query_list_repositories(conn, limit=limit, offset=offset)
            return {"items": items, "total": len(items), "limit": limit, "offset": offset}

    @mcp.tool
    def get_repository(repository: str) -> dict[str, Any]:
        """Fetch a repository by name, root path, or repository ID."""
        with _connection(database_path) as conn:
            item = _fetch_repository(conn, repository)
            return {"found": item is not None, "item": item}

    @mcp.tool
    def list_agents(limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List detected human and agent actors."""
        limit = _clamp_limit(limit, MAX_LIST_LIMIT)
        offset = max(0, int(offset))
        with _connection(database_path) as conn:
            items = query_list_agents(conn, limit=limit, offset=offset)
            return {"items": items, "total": len(items), "limit": limit, "offset": offset}

    @mcp.tool
    def get_agent(
        actor_name: str,
        host: str | None = None,
        actor_type: str | None = None,
        agent_session_id: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a single agent record by actor name and optional filters."""
        if actor_type is not None and actor_type not in {"human", "agent"}:
            raise ValueError("actor_type must be human or agent")
        with _connection(database_path) as conn:
            item = _fetch_agent(
                conn,
                actor_name=actor_name,
                host=host,
                actor_type=actor_type,
                agent_session_id=agent_session_id,
            )
            return {"found": item is not None, "item": item}

    @mcp.tool
    def list_commits(
        limit: int = 50,
        offset: int = 0,
        query: str | None = None,
        repository: str | None = None,
        committed_after: str | None = None,
        committed_before: str | None = None,
    ) -> dict[str, Any]:
        """List commits and their diff summaries."""
        limit = _clamp_limit(limit, MAX_LIST_LIMIT)
        offset = max(0, int(offset))
        with _connection(database_path) as conn:
            items = query_list_commits(
                conn,
                limit=limit,
                offset=offset,
                query=query,
                repository=repository,
                committed_after=committed_after,
                committed_before=committed_before,
            )
            return {"items": items, "total": len(items), "limit": limit, "offset": offset}

    @mcp.tool
    def get_commit(commit_hash: str, repository: str | None = None) -> dict[str, Any]:
        """Fetch a single commit by hash."""
        with _connection(database_path) as conn:
            item = query_get_commit(conn, commit_hash=commit_hash, repository=repository)
            return {"found": item is not None, "item": item}

    @mcp.tool
    def get_commit_detail(
        commit_hash: str,
        repository: str | None = None,
        related_limit: int = 100,
    ) -> dict[str, Any]:
        """Fetch commit metadata, file changes, and related commands."""
        related_limit = _clamp_limit(related_limit, MAX_DETAIL_LIMIT)
        with _connection(database_path) as conn:
            detail = query_get_commit_detail(
                conn,
                commit_hash=commit_hash,
                repository=repository,
                related_limit=related_limit,
            )
            detail["found"] = detail.get("commit") is not None
            detail["related_limit"] = related_limit
            return detail

    @mcp.tool
    def list_daily_summaries(
        limit: int = 50,
        offset: int = 0,
        query: str | None = None,
        host: str | None = None,
        summary_date_after: str | None = None,
        summary_date_before: str | None = None,
    ) -> dict[str, Any]:
        """List generated daily work summaries."""
        limit = _clamp_limit(limit, MAX_LIST_LIMIT)
        offset = max(0, int(offset))
        with _connection(database_path) as conn:
            items = query_list_daily_summaries(
                conn,
                limit=limit,
                offset=offset,
                query=query,
                host=host,
                summary_date_after=summary_date_after,
                summary_date_before=summary_date_before,
            )
            return {"items": items, "total": len(items), "limit": limit, "offset": offset}

    return mcp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tracehouse-mcp")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=(
            "SQLite database path; defaults to ABSOLUTELY_DATABASE_PATH or "
            "~/.local/share/tracehouse/tracehouse.db"
        ),
    )
    args = parser.parse_args(argv)
    server = create_mcp_server(args.db)
    server.run(show_banner=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
