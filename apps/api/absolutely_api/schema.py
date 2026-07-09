from __future__ import annotations

from datetime import datetime, timezone
import sqlite3


SCHEMA_VERSION = 1

TABLE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        session_key TEXT NOT NULL,
        host TEXT NOT NULL,
        shell TEXT NOT NULL,
        started_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        ended_at TEXT,
        session_type TEXT NOT NULL DEFAULT 'terminal',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(host, session_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS repositories (
        id TEXT PRIMARY KEY,
        host TEXT NOT NULL,
        name TEXT NOT NULL,
        root_path TEXT NOT NULL,
        branch TEXT,
        current_commit_hash TEXT,
        first_seen_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(host, root_path)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agents (
        id TEXT PRIMARY KEY,
        host TEXT NOT NULL,
        actor_type TEXT NOT NULL CHECK (actor_type IN ('human', 'agent')),
        actor_name TEXT NOT NULL,
        agent_session_id TEXT NOT NULL DEFAULT '',
        first_seen_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(host, actor_type, actor_name, agent_session_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS commands (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        session_record_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        repository_id TEXT REFERENCES repositories(id) ON DELETE SET NULL,
        repository_name TEXT,
        repository_root TEXT,
        agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
        command TEXT NOT NULL,
        cwd TEXT NOT NULL,
        timestamp_start TEXT NOT NULL,
        timestamp_end TEXT NOT NULL,
        duration_ms INTEGER NOT NULL,
        exit_code INTEGER NOT NULL,
        stdout TEXT,
        stderr TEXT,
        shell TEXT NOT NULL,
        host TEXT NOT NULL,
        actor_type TEXT NOT NULL CHECK (actor_type IN ('human', 'agent')),
        actor_name TEXT,
        agent_session_id TEXT NOT NULL DEFAULT '',
        git_branch TEXT,
        git_commit_hash TEXT,
        redaction_findings_json TEXT NOT NULL DEFAULT '[]',
        metadata_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS commits (
        id TEXT PRIMARY KEY,
        repository_id TEXT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
        session_record_id TEXT REFERENCES sessions(id) ON DELETE SET NULL,
        commit_hash TEXT NOT NULL,
        message TEXT NOT NULL,
        diff_summary TEXT,
        author_name TEXT,
        authored_at TEXT NOT NULL,
        committed_at TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(repository_id, commit_hash)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS file_changes (
        id TEXT PRIMARY KEY,
        repository_id TEXT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
        commit_id TEXT REFERENCES commits(id) ON DELETE CASCADE,
        path TEXT NOT NULL,
        old_path TEXT,
        change_type TEXT NOT NULL CHECK (change_type IN ('added', 'modified', 'deleted', 'renamed')),
        lines_added INTEGER NOT NULL DEFAULT 0,
        lines_removed INTEGER NOT NULL DEFAULT 0,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS embeddings (
        id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        model_name TEXT NOT NULL,
        dimensions INTEGER NOT NULL,
        vector_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(entity_type, entity_id, model_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_summaries (
        id TEXT PRIMARY KEY,
        summary_date TEXT NOT NULL,
        host TEXT NOT NULL,
        worked_ms INTEGER NOT NULL,
        commands_count INTEGER NOT NULL,
        commits_count INTEGER NOT NULL,
        repositories_json TEXT NOT NULL DEFAULT '[]',
        top_tools_json TEXT NOT NULL DEFAULT '[]',
        summary_text TEXT NOT NULL,
        mistake_text TEXT,
        created_at TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(summary_date, host)
    )
    """,
)

INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_sessions_host_last_seen ON sessions(host, last_seen_at)",
    "CREATE INDEX IF NOT EXISTS idx_repositories_host_last_seen ON repositories(host, last_seen_at)",
    "CREATE INDEX IF NOT EXISTS idx_agents_host_last_seen ON agents(host, last_seen_at)",
    "CREATE INDEX IF NOT EXISTS idx_commands_host_timestamp ON commands(host, timestamp_start)",
    "CREATE INDEX IF NOT EXISTS idx_commands_session ON commands(session_record_id, timestamp_start)",
    "CREATE INDEX IF NOT EXISTS idx_commands_repository ON commands(repository_id, timestamp_start)",
    "CREATE INDEX IF NOT EXISTS idx_commands_exit_code ON commands(exit_code, timestamp_start)",
    "CREATE INDEX IF NOT EXISTS idx_commits_repository ON commits(repository_id, committed_at)",
    "CREATE INDEX IF NOT EXISTS idx_file_changes_commit ON file_changes(commit_id)",
    "CREATE INDEX IF NOT EXISTS idx_embeddings_entity ON embeddings(entity_type, entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_daily_summaries_date ON daily_summaries(summary_date, host)",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    script = ";\n".join(stmt.strip() for stmt in TABLE_STATEMENTS + INDEX_STATEMENTS) + ";"
    conn.executescript(script)
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
        (SCHEMA_VERSION, utc_now_iso()),
    )
    conn.commit()
