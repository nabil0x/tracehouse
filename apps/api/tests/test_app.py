from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from absolutely_api.app import create_app
from absolutely_api.privacy import decrypt_export_bundle


class AppTests(unittest.TestCase):
    def test_ingest_and_search_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "absolutely.sqlite3"
            app = create_app(db_path)
            client = TestClient(app)

            response = client.post(
                "/commands",
                json={
                    "command": "AWS_SECRET_ACCESS_KEY=supersecret pytest -k auth",
                    "cwd": "/work/backend",
                    "timestamp_start": datetime(2026, 7, 9, 3, 0, tzinfo=timezone.utc).isoformat(),
                    "timestamp_end": datetime(2026, 7, 9, 3, 0, 5, tzinfo=timezone.utc).isoformat(),
                    "duration_ms": 5000,
                    "exit_code": 1,
                    "shell": "bash",
                    "host": "laptop",
                    "session_id": "session-1",
                    "stdout": "Bearer ghp_supersecretvalue1234567890",
                    "stderr": "pytest failed",
                    "actor_type": "agent",
                    "actor_name": "Codex CLI",
                    "agent_session_id": "agent-session-1",
                    "repository_name": "backend",
                    "repository_root": "/work/backend",
                    "git_branch": "main",
                    "git_commit_hash": "abc123",
                    "metadata": {"note": "PASSWORD=secret"},
                },
            )
            self.assertEqual(response.status_code, 200)
            command_id = response.json()["id"]
            self.assertTrue(command_id)

            timeline = client.get("/timeline")
            self.assertEqual(timeline.status_code, 200)
            timeline_body = timeline.json()
            self.assertEqual(timeline_body["total"], 1)
            self.assertEqual(timeline_body["items"][0]["actor_name"], "Codex CLI")
            self.assertIn("[REDACTED", timeline_body["items"][0]["command"])

            search = client.get("/search", params={"query": "auth"})
            self.assertEqual(search.status_code, 200)
            search_body = search.json()
            self.assertGreaterEqual(len(search_body["items"]), 1)
            self.assertEqual(search_body["items"][0]["kind"], "command")

            healthz = client.get("/healthz")
            self.assertEqual(healthz.status_code, 200)
            self.assertEqual(healthz.json()["status"], "ok")

    def test_sessions_endpoint_reconstructs_command_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "absolutely.sqlite3"
            app = create_app(db_path)
            client = TestClient(app)

            base_payload = {
                "cwd": "/work/backend",
                "shell": "bash",
                "host": "laptop",
                "session_id": "session-1",
                "actor_type": "agent",
                "actor_name": "Codex CLI",
                "agent_session_id": "agent-session-1",
                "repository_name": "backend",
                "repository_root": "/work/backend",
                "git_branch": "main",
                "git_commit_hash": "abc123",
            }

            first = client.post(
                "/commands",
                json={
                    **base_payload,
                    "command": "pytest -k auth",
                    "timestamp_start": datetime(2026, 7, 9, 3, 0, tzinfo=timezone.utc).isoformat(),
                    "timestamp_end": datetime(2026, 7, 9, 3, 0, 3, tzinfo=timezone.utc).isoformat(),
                    "duration_ms": 3000,
                    "exit_code": 1,
                },
            )
            self.assertEqual(first.status_code, 200)

            second = client.post(
                "/commands",
                json={
                    **base_payload,
                    "command": "pytest tests/test_auth.py",
                    "timestamp_start": datetime(2026, 7, 9, 3, 5, tzinfo=timezone.utc).isoformat(),
                    "timestamp_end": datetime(2026, 7, 9, 3, 5, 5, tzinfo=timezone.utc).isoformat(),
                    "duration_ms": 5000,
                    "exit_code": 0,
                },
            )
            self.assertEqual(second.status_code, 200)

            sessions = client.get("/sessions", params={"session_key": "session-1"})
            self.assertEqual(sessions.status_code, 200)
            body = sessions.json()
            self.assertEqual(body["total"], 1)
            self.assertEqual(body["items"][0]["session_key"], "session-1")
            self.assertEqual(body["items"][0]["commands_count"], 2)
            self.assertEqual(body["items"][0]["worked_ms"], 8000)
            self.assertEqual(body["items"][0]["repositories_count"], 1)

            timeline_for_session = client.get("/timeline", params={"session_key": "session-1"})
            self.assertEqual(timeline_for_session.status_code, 200)
            timeline_body = timeline_for_session.json()
            self.assertEqual(timeline_body["total"], 2)
            self.assertTrue(
                all(item["session_key"] == "session-1" for item in timeline_body["items"])
            )

    def test_search_expands_semantic_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "absolutely.sqlite3"
            app = create_app(db_path)
            client = TestClient(app)

            response = client.post(
                "/commands",
                json={
                    "command": "npm run login",
                    "cwd": "/work/backend",
                    "timestamp_start": datetime(2026, 7, 9, 5, 0, tzinfo=timezone.utc).isoformat(),
                    "timestamp_end": datetime(2026, 7, 9, 5, 0, 2, tzinfo=timezone.utc).isoformat(),
                    "duration_ms": 2000,
                    "exit_code": 0,
                    "shell": "bash",
                    "host": "laptop",
                    "session_id": "session-semantic",
                    "actor_type": "agent",
                    "actor_name": "Codex CLI",
                    "agent_session_id": "agent-session-semantic",
                    "repository_name": "backend",
                    "repository_root": "/work/backend",
                    "git_branch": "main",
                    "git_commit_hash": "semantic-commit-0001",
                },
            )
            self.assertEqual(response.status_code, 200)

            search = client.get("/search", params={"query": "authentication"})
            self.assertEqual(search.status_code, 200)
            body = search.json()
            self.assertGreaterEqual(body["total"], 1)
            self.assertTrue(any(item["command"] == "npm run login" for item in body["items"]))

    def test_commit_detail_includes_files_commands_and_timeline_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "absolutely.sqlite3"
            app = create_app(db_path)
            client = TestClient(app)

            commit_hash = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
            command_response = client.post(
                "/commands",
                json={
                    "command": "git commit -m 'Fix auth redirect'",
                    "cwd": "/work/backend",
                    "timestamp_start": datetime(2026, 7, 9, 6, 0, tzinfo=timezone.utc).isoformat(),
                    "timestamp_end": datetime(2026, 7, 9, 6, 0, 4, tzinfo=timezone.utc).isoformat(),
                    "duration_ms": 4000,
                    "exit_code": 0,
                    "shell": "bash",
                    "host": "laptop",
                    "session_id": "session-commit",
                    "actor_type": "agent",
                    "actor_name": "Codex CLI",
                    "agent_session_id": "agent-session-commit",
                    "repository_name": "backend",
                    "repository_root": "/work/backend",
                    "git_branch": "main",
                    "git_commit_hash": commit_hash,
                    "metadata": {
                        "git_commit_snapshot": {
                            "commit_hash": commit_hash,
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
                },
            )
            self.assertEqual(command_response.status_code, 200)

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                embeddings = conn.execute(
                    "SELECT entity_type, model_name, dimensions FROM embeddings ORDER BY entity_type"
                ).fetchall()
                self.assertEqual([row["entity_type"] for row in embeddings], ["command", "commit"])
                self.assertTrue(all(row["model_name"] == "local-concept-embedding-v1" for row in embeddings))
                self.assertTrue(all(row["dimensions"] == 256 for row in embeddings))

            detail = client.get(f"/commits/{commit_hash}", params={"repository": "/work/backend"})
            self.assertEqual(detail.status_code, 200)
            detail_body = detail.json()
            self.assertIsNotNone(detail_body["commit"])
            self.assertEqual(detail_body["commit"]["commit_hash"], commit_hash)
            self.assertEqual(len(detail_body["file_changes"]), 1)
            self.assertEqual(len(detail_body["related_commands"]), 1)
            self.assertEqual(detail_body["commit"]["message"], "Fix auth redirect")
            self.assertEqual(detail_body["file_changes"][0]["path"], "apps/auth.ts")

            timeline = client.get("/timeline", params={"git_commit_hash": commit_hash})
            self.assertEqual(timeline.status_code, 200)
            timeline_body = timeline.json()
            self.assertEqual(timeline_body["total"], 1)
            self.assertEqual(timeline_body["items"][0]["git_commit_hash"], commit_hash)

    def test_privacy_status_export_encryption_and_delete_all_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "absolutely.sqlite3"
            app = create_app(db_path)
            client = TestClient(app)

            response = client.post(
                "/commands",
                json={
                    "command": "echo privacy",
                    "cwd": "/work/backend",
                    "timestamp_start": datetime(2026, 7, 9, 7, 0, tzinfo=timezone.utc).isoformat(),
                    "timestamp_end": datetime(2026, 7, 9, 7, 0, 1, tzinfo=timezone.utc).isoformat(),
                    "duration_ms": 1000,
                    "exit_code": 0,
                    "shell": "bash",
                    "host": "laptop",
                    "session_id": "session-privacy",
                    "actor_type": "human",
                    "repository_name": "backend",
                    "repository_root": "/work/backend",
                    "git_branch": "main",
                    "git_commit_hash": "privacy-commit-1",
                },
            )
            self.assertEqual(response.status_code, 200)

            status = client.get("/privacy")
            self.assertEqual(status.status_code, 200)
            status_body = status.json()
            self.assertEqual(status_body["counts"]["commands"], 1)
            self.assertTrue(status_body["export"]["supported"])
            self.assertTrue(status_body["encryption"]["supported"])

            plain_export = client.post("/privacy/export", json={})
            self.assertEqual(plain_export.status_code, 200)
            self.assertIn('filename="tracehouse-export.json"', plain_export.headers["content-disposition"])
            plain_body = plain_export.json()
            self.assertEqual(plain_body["format"], "tracehouse-export")
            self.assertEqual(plain_body["table_counts"]["commands"], 1)
            self.assertEqual(len(plain_body["tables"]["commands"]), 1)

            encrypted_export = client.post("/privacy/export", json={"passphrase": "swordfish"})
            self.assertEqual(encrypted_export.status_code, 200)
            self.assertIn(
                'filename="tracehouse-encrypted-export.json"',
                encrypted_export.headers["content-disposition"],
            )
            encrypted_body = encrypted_export.json()
            self.assertEqual(encrypted_body["format"], "tracehouse-encrypted-export")
            decrypted = decrypt_export_bundle(encrypted_body, "swordfish")
            self.assertEqual(decrypted["tables"]["commands"][0]["command"], "echo privacy")

            delete = client.delete(
                "/privacy/data",
                params={"confirm": "DELETE ALL DATA"},
            )
            self.assertEqual(delete.status_code, 200)
            self.assertEqual(delete.json()["status"], "cleared")
            self.assertEqual(delete.json()["deleted"]["commands"], 1)

            after = client.get("/privacy")
            self.assertEqual(after.status_code, 200)
            self.assertEqual(after.json()["counts"]["commands"], 0)


if __name__ == "__main__":
    unittest.main()
