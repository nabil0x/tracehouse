from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .db import bootstrap_database, open_database, record_command
from .models import ActorType, CommandEvent
from .privacy import (
    build_export_bundle,
    delete_all_data,
    encrypt_export_bundle,
    privacy_status,
)
from .query import (
    count_commands,
    count_sessions,
    get_commit_detail,
    list_agents,
    list_commands,
    list_commits,
    list_daily_summaries,
    list_repositories,
    list_sessions,
    search_records,
)
from .schema import SCHEMA_VERSION


class CommandIngestRequest(BaseModel):
    command: str
    cwd: str
    timestamp_start: datetime
    timestamp_end: datetime
    duration_ms: int
    exit_code: int
    shell: str
    host: str
    session_id: str
    stdout: str | None = None
    stderr: str | None = None
    actor_type: ActorType = ActorType.HUMAN
    actor_name: str | None = None
    agent_session_id: str = ""
    repository_name: str | None = None
    repository_root: str | None = None
    git_branch: str | None = None
    git_commit_hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_event(self) -> CommandEvent:
        payload = self.model_dump()
        payload["actor_type"] = ActorType(payload["actor_type"])
        return CommandEvent(**payload)


class PrivacyExportRequest(BaseModel):
    passphrase: str | None = None


def _connection_factory(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = open_database(db_path)
    try:
        yield conn
    finally:
        conn.close()


def create_app(db_path: str | Path) -> FastAPI:
    database_path = Path(db_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    bootstrap_database(database_path).close()

    app = FastAPI(title="Tracehouse API", version="0.1.0")
    app.state.database_path = database_path

    def get_db() -> Iterator[sqlite3.Connection]:
        yield from _connection_factory(app.state.database_path)

    @app.get("/healthz")
    def healthz(db: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        def count(table: str) -> int:
            return int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

        stats = {
            "schema_version": SCHEMA_VERSION,
            "commands": count("commands"),
            "repositories": count("repositories"),
            "agents": count("agents"),
            "commits": count("commits"),
            "daily_summaries": count("daily_summaries"),
        }
        return {"status": "ok", "stats": stats}

    @app.get("/privacy")
    def privacy(db: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return privacy_status(db)

    @app.post("/commands")
    def ingest_command(
        payload: CommandIngestRequest,
        db: sqlite3.Connection = Depends(get_db),
    ) -> dict[str, Any]:
        command_id = record_command(db, payload.to_event())
        return {"id": command_id, "status": "stored"}

    @app.get("/timeline")
    def timeline(
        db: sqlite3.Connection = Depends(get_db),
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        q: str | None = Query(default=None, alias="query"),
        host: str | None = None,
        session_key: str | None = None,
        repository: str | None = None,
        shell: str | None = None,
        exit_code: int | None = None,
        actor_type: ActorType | None = None,
        actor_name: str | None = None,
        git_commit_hash: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        items = list_commands(
            db,
            limit=limit,
            offset=offset,
            query=q,
            host=host,
            session_key=session_key,
            repository=repository,
            shell=shell,
            exit_code=exit_code,
            actor_type=actor_type.value if actor_type is not None else None,
            actor_name=actor_name,
            git_commit_hash=git_commit_hash,
            started_after=started_after.isoformat() if started_after else None,
            started_before=started_before.isoformat() if started_before else None,
            cwd=cwd,
        )
        total = count_commands(
            db,
            query=q,
            host=host,
            session_key=session_key,
            repository=repository,
            shell=shell,
            exit_code=exit_code,
            actor_type=actor_type.value if actor_type is not None else None,
            actor_name=actor_name,
            git_commit_hash=git_commit_hash,
            started_after=started_after.isoformat() if started_after else None,
            started_before=started_before.isoformat() if started_before else None,
            cwd=cwd,
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.get("/sessions")
    def sessions(
        db: sqlite3.Connection = Depends(get_db),
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        q: str | None = Query(default=None, alias="query"),
        host: str | None = None,
        shell: str | None = None,
        session_key: str | None = None,
        session_type: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        active: bool | None = None,
    ) -> dict[str, Any]:
        items = list_sessions(
            db,
            limit=limit,
            offset=offset,
            query=q,
            host=host,
            shell=shell,
            session_key=session_key,
            session_type=session_type,
            started_after=started_after.isoformat() if started_after else None,
            started_before=started_before.isoformat() if started_before else None,
            active=active,
        )
        total = count_sessions(
            db,
            query=q,
            host=host,
            shell=shell,
            session_key=session_key,
            session_type=session_type,
            started_after=started_after.isoformat() if started_after else None,
            started_before=started_before.isoformat() if started_before else None,
            active=active,
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.get("/search")
    def search(
        db: sqlite3.Connection = Depends(get_db),
        query: str = Query(..., min_length=1),
        limit: int = Query(default=20, ge=1, le=100),
        host: str | None = None,
        repository: str | None = None,
        shell: str | None = None,
        actor_type: ActorType | None = None,
    ) -> dict[str, Any]:
        items = search_records(
            db,
            query=query,
            limit=limit,
            host=host,
            repository=repository,
            shell=shell,
            actor_type=actor_type.value if actor_type is not None else None,
        )
        return {"query": query, "limit": limit, "total": len(items), "items": items}

    @app.post("/privacy/export")
    def privacy_export(
        payload: PrivacyExportRequest,
        db: sqlite3.Connection = Depends(get_db),
    ) -> JSONResponse:
        bundle = build_export_bundle(db)
        passphrase = (payload.passphrase or "").strip()
        if passphrase:
            bundle = encrypt_export_bundle(bundle, passphrase)
            filename = "tracehouse-encrypted-export.json"
        else:
            filename = "tracehouse-export.json"
        return JSONResponse(
            bundle,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    @app.delete("/privacy/data")
    def privacy_delete(
        confirm: str = Query(..., min_length=1),
        db: sqlite3.Connection = Depends(get_db),
    ) -> dict[str, Any]:
        if confirm.strip() != "DELETE ALL DATA":
            raise HTTPException(status_code=400, detail="confirmation phrase mismatch")
        deleted = delete_all_data(db)
        return {"status": "cleared", "deleted": deleted}

    @app.get("/repositories")
    def repositories(
        db: sqlite3.Connection = Depends(get_db),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = 0,
    ) -> dict[str, Any]:
        items = list_repositories(db, limit=limit, offset=offset)
        return {"items": items, "limit": limit, "offset": offset}

    @app.get("/agents")
    def agents(
        db: sqlite3.Connection = Depends(get_db),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = 0,
    ) -> dict[str, Any]:
        items = list_agents(db, limit=limit, offset=offset)
        return {"items": items, "limit": limit, "offset": offset}

    @app.get("/commits/{commit_hash}")
    def commit_detail(
        commit_hash: str,
        db: sqlite3.Connection = Depends(get_db),
        repository: str | None = None,
        related_limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        return get_commit_detail(
            db,
            commit_hash=commit_hash,
            repository=repository,
            related_limit=related_limit,
        )

    @app.get("/commits")
    def commits(
        db: sqlite3.Connection = Depends(get_db),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        query: str | None = None,
        repository: str | None = None,
        committed_after: datetime | None = None,
        committed_before: datetime | None = None,
    ) -> dict[str, Any]:
        items = list_commits(
            db,
            limit=limit,
            offset=offset,
            query=query,
            repository=repository,
            committed_after=committed_after.isoformat() if committed_after else None,
            committed_before=committed_before.isoformat() if committed_before else None,
        )
        return {"items": items, "limit": limit, "offset": offset}

    @app.get("/daily-summaries")
    def daily_summaries(
        db: sqlite3.Connection = Depends(get_db),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        query: str | None = None,
        host: str | None = None,
        summary_date_after: str | None = None,
        summary_date_before: str | None = None,
    ) -> dict[str, Any]:
        items = list_daily_summaries(
            db,
            limit=limit,
            offset=offset,
            query=query,
            host=host,
            summary_date_after=summary_date_after,
            summary_date_before=summary_date_before,
        )
        return {"items": items, "limit": limit, "offset": offset}

    return app
