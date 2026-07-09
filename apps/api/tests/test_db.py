from __future__ import annotations

from datetime import datetime, timezone
import unittest

from absolutely_api.db import bootstrap_database, record_command
from absolutely_api.models import ActorType, CommandEvent
from absolutely_api.query import list_commands, list_sessions


class DatabaseTests(unittest.TestCase):
    def test_record_command_redacts_and_creates_context(self) -> None:
        conn = bootstrap_database(":memory:")
        event = CommandEvent(
            command="AWS_SECRET_ACCESS_KEY=supersecret python deploy.py --password hunter2",
            cwd="/tmp/project",
            timestamp_start=datetime(2026, 7, 9, 3, 0, tzinfo=timezone.utc),
            timestamp_end=datetime(2026, 7, 9, 3, 0, 10, tzinfo=timezone.utc),
            duration_ms=10000,
            exit_code=1,
            shell="bash",
            host="laptop",
            session_id="session-1",
            stdout="Bearer ghp_supersecretvalue1234567890",
            stderr="-----BEGIN OPENSSH PRIVATE KEY-----\nsecret\n-----END OPENSSH PRIVATE KEY-----",
            actor_type=ActorType.AGENT,
            actor_name="Codex CLI",
            agent_session_id="agent-session-1",
            repository_name="project",
            repository_root="/tmp/project",
            git_branch="main",
            git_commit_hash="abc123",
            metadata={"extra": "PASSWORD=secret"},
        )
        command_id = record_command(conn, event)

        command_row = conn.execute(
            "SELECT * FROM commands WHERE id = ?",
            (command_id,),
        ).fetchone()
        self.assertIsNotNone(command_row)
        assert command_row is not None
        self.assertIn("[REDACTED", command_row["command"])
        self.assertIn("[REDACTED", command_row["stdout"])
        self.assertIn("[REDACTED", command_row["stderr"])

        session_row = conn.execute(
            "SELECT * FROM sessions WHERE session_key = ?",
            ("session-1",),
        ).fetchone()
        self.assertIsNotNone(session_row)
        assert session_row is not None
        self.assertEqual(session_row["shell"], "bash")

        repository_row = conn.execute(
            "SELECT * FROM repositories WHERE root_path = ?",
            ("/tmp/project",),
        ).fetchone()
        self.assertIsNotNone(repository_row)

        agent_row = conn.execute(
            "SELECT * FROM agents WHERE actor_name = ?",
            ("Codex CLI",),
        ).fetchone()
        self.assertIsNotNone(agent_row)

        self.assertIn("secret_flag", command_row["redaction_findings_json"])

    def test_list_sessions_reconstructs_aggregate_metrics(self) -> None:
        conn = bootstrap_database(":memory:")
        first = CommandEvent(
            command="pytest -k auth",
            cwd="/tmp/project",
            timestamp_start=datetime(2026, 7, 9, 3, 0, tzinfo=timezone.utc),
            timestamp_end=datetime(2026, 7, 9, 3, 0, 3, tzinfo=timezone.utc),
            duration_ms=3000,
            exit_code=1,
            shell="bash",
            host="laptop",
            session_id="session-1",
            actor_type=ActorType.AGENT,
            actor_name="Codex CLI",
            agent_session_id="agent-session-1",
            repository_name="project",
            repository_root="/tmp/project",
            git_branch="main",
            git_commit_hash="abc123",
        )
        second = CommandEvent(
            command="pytest tests/test_auth.py",
            cwd="/tmp/project",
            timestamp_start=datetime(2026, 7, 9, 3, 5, tzinfo=timezone.utc),
            timestamp_end=datetime(2026, 7, 9, 3, 5, 5, tzinfo=timezone.utc),
            duration_ms=5000,
            exit_code=0,
            shell="bash",
            host="laptop",
            session_id="session-1",
            actor_type=ActorType.AGENT,
            actor_name="Codex CLI",
            agent_session_id="agent-session-1",
            repository_name="project",
            repository_root="/tmp/project",
            git_branch="main",
            git_commit_hash="def456",
        )
        record_command(conn, first)
        record_command(conn, second)

        sessions = list_sessions(conn, host="laptop", session_key="session-1")
        self.assertEqual(len(sessions), 1)
        session = sessions[0]
        self.assertEqual(session["session_key"], "session-1")
        self.assertEqual(session["commands_count"], 2)
        self.assertEqual(session["worked_ms"], 8000)
        self.assertEqual(session["repositories_count"], 1)
        self.assertEqual(session["first_command_at"], first.timestamp_start.isoformat())
        self.assertEqual(session["last_command_at"], second.timestamp_end.isoformat())
        self.assertEqual(session["kind"], "session")

    def test_list_commands_filters_by_session_key(self) -> None:
        conn = bootstrap_database(":memory:")
        shared = {
            "cwd": "/tmp/project",
            "shell": "bash",
            "host": "laptop",
            "actor_type": ActorType.HUMAN,
        }
        record_command(
            conn,
            CommandEvent(
                command="echo one",
                timestamp_start=datetime(2026, 7, 9, 3, 0, tzinfo=timezone.utc),
                timestamp_end=datetime(2026, 7, 9, 3, 0, 1, tzinfo=timezone.utc),
                duration_ms=1000,
                exit_code=0,
                session_id="session-1",
                **shared,
            ),
        )
        record_command(
            conn,
            CommandEvent(
                command="echo two",
                timestamp_start=datetime(2026, 7, 9, 3, 1, tzinfo=timezone.utc),
                timestamp_end=datetime(2026, 7, 9, 3, 1, 2, tzinfo=timezone.utc),
                duration_ms=2000,
                exit_code=0,
                session_id="session-1",
                **shared,
            ),
        )
        record_command(
            conn,
            CommandEvent(
                command="echo other",
                timestamp_start=datetime(2026, 7, 9, 4, 0, tzinfo=timezone.utc),
                timestamp_end=datetime(2026, 7, 9, 4, 0, 1, tzinfo=timezone.utc),
                duration_ms=1000,
                exit_code=0,
                session_id="session-2",
                **shared,
            ),
        )

        commands = list_commands(conn, session_key="session-1")
        self.assertEqual(len(commands), 2)
        self.assertTrue(all(command["session_key"] == "session-1" for command in commands))

    def test_record_command_persists_embeddings_for_command_and_commit(self) -> None:
        conn = bootstrap_database(":memory:")
        event = CommandEvent(
            command="git commit -m 'Fix auth redirect'",
            cwd="/tmp/project",
            timestamp_start=datetime(2026, 7, 9, 6, 0, tzinfo=timezone.utc),
            timestamp_end=datetime(2026, 7, 9, 6, 0, 4, tzinfo=timezone.utc),
            duration_ms=4000,
            exit_code=0,
            shell="bash",
            host="laptop",
            session_id="session-commit",
            actor_type=ActorType.AGENT,
            actor_name="Codex CLI",
            agent_session_id="agent-session-commit",
            repository_name="project",
            repository_root="/tmp/project",
            git_branch="main",
            git_commit_hash="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            metadata={
                "git_commit_snapshot": {
                    "commit_hash": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
                    "message": "Fix auth redirect",
                    "author_name": "Codex CLI",
                    "authored_at": datetime(2026, 7, 9, 6, 0, tzinfo=timezone.utc).isoformat(),
                    "committed_at": datetime(2026, 7, 9, 6, 0, 4, tzinfo=timezone.utc).isoformat(),
                    "diff_summary": " apps/auth.ts | 15 +++++++++++++--",
                    "file_changes": [
                        {
                            "path": "apps/auth.ts",
                            "old_path": None,
                            "change_type": "modified",
                            "lines_added": 12,
                            "lines_removed": 3,
                            "status": "M",
                            "raw": "M\tapps/auth.ts",
                        }
                    ],
                }
            },
        )
        record_command(conn, event)

        embeddings = conn.execute(
            "SELECT entity_type, model_name, dimensions FROM embeddings ORDER BY entity_type"
        ).fetchall()
        self.assertEqual([row["entity_type"] for row in embeddings], ["command", "commit"])
        self.assertTrue(all(row["model_name"] == "local-concept-embedding-v1" for row in embeddings))
        self.assertTrue(all(row["dimensions"] == 256 for row in embeddings))


if __name__ == "__main__":
    unittest.main()
