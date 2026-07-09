from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

import uvicorn

from .app import create_app
from .db import bootstrap_database, record_command
from .models import ActorType, CommandEvent


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tracehouse-api")
    subcommands = parser.add_subparsers(dest="command", required=True)

    init_db = subcommands.add_parser("init-db", help="create or upgrade the local SQLite database")
    init_db.add_argument("path", type=Path)

    serve = subcommands.add_parser("serve", help="run the FastAPI server")
    serve.add_argument("path", type=Path)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=18400)

    demo = subcommands.add_parser("record-demo", help="insert a redacted sample command")
    demo.add_argument("path", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "init-db":
        conn = bootstrap_database(args.path)
        conn.close()
        print(f"Initialized {args.path}")
        return 0

    if args.command == "record-demo":
        conn = bootstrap_database(args.path)
        now = datetime.now(timezone.utc)
        event = CommandEvent(
            command="AWS_SECRET_ACCESS_KEY=supersecret python deploy.py --password hunter2",
            cwd=str(Path.cwd()),
            timestamp_start=now,
            timestamp_end=now,
            duration_ms=1200,
            exit_code=1,
            shell="bash",
            host="localhost",
            session_id="demo-session",
            stdout="Bearer ghp_supersecrettokenvalue1234567890",
            stderr="-----BEGIN OPENSSH PRIVATE KEY-----\nsecret\n-----END OPENSSH PRIVATE KEY-----",
            actor_type=ActorType.AGENT,
            actor_name="Codex CLI",
            agent_session_id="codex-demo",
            repository_name="absolutely",
            repository_root=str(Path.cwd()),
            git_branch="main",
            git_commit_hash="deadbeef",
            metadata={"note": "PASSWORD=hidden"},
        )
        command_id = record_command(conn, event)
        conn.close()
        print(command_id)
        return 0

    if args.command == "serve":
        app = create_app(args.path)
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    parser.print_help(sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
