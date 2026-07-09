from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from fastmcp import Client

from absolutely_api.db import bootstrap_database, record_command
from absolutely_api.mcp_server import create_mcp_server
from absolutely_api.models import ActorType, CommandEvent
from absolutely_api.schema import SCHEMA_VERSION


class MCPServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_codex_bridge_exposes_read_only_log_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "absolutely.sqlite3"
            conn = bootstrap_database(db_path)
            try:
                commit_hash = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
                record_command(
                    conn,
                    CommandEvent(
                        command="git commit -m 'Fix auth redirect'",
                        cwd="/work/backend",
                        timestamp_start=datetime(2026, 7, 9, 6, 0, tzinfo=timezone.utc),
                        timestamp_end=datetime(2026, 7, 9, 6, 0, 4, tzinfo=timezone.utc),
                        duration_ms=4000,
                        exit_code=0,
                        shell="bash",
                        host="laptop",
                        session_id="session-mcp",
                        actor_type=ActorType.AGENT,
                        actor_name="Codex CLI",
                        agent_session_id="agent-session-mcp",
                        repository_name="backend",
                        repository_root="/work/backend",
                        git_branch="main",
                        git_commit_hash=commit_hash,
                        metadata={
                            "git_commit_snapshot": {
                                "commit_hash": commit_hash,
                                "message": "Fix auth redirect",
                                "author_name": "Codex CLI",
                                "authored_at": datetime(
                                    2026, 7, 9, 6, 0, tzinfo=timezone.utc
                                ).isoformat(),
                                "committed_at": datetime(
                                    2026, 7, 9, 6, 0, 4, tzinfo=timezone.utc
                                ).isoformat(),
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
                    ),
                )
            finally:
                conn.close()

            server = create_mcp_server(db_path)
            async with Client(server) as client:
                tool_names = {tool.name for tool in await client.list_tools()}
                self.assertTrue(
                    {
                        "database_overview",
                        "search_logs",
                        "get_commit",
                        "get_commit_detail",
                    }.issubset(tool_names)
                )

                overview = await client.call_tool("database_overview")
                self.assertEqual(overview.data["database_path"], str(db_path))
                self.assertEqual(overview.data["schema_version"], SCHEMA_VERSION)
                self.assertTrue(overview.data["privacy"]["export"]["supported"])
                self.assertTrue(overview.data["privacy"]["delete"]["supported"])
                self.assertTrue(overview.data["privacy"]["encryption"]["supported"])

                search = await client.call_tool("search_logs", {"query": "auth", "limit": 5})
                self.assertEqual(search.data["query"], "auth")
                self.assertGreaterEqual(search.data["total"], 1)
                self.assertTrue(
                    any(item["kind"] in {"command", "commit"} for item in search.data["items"])
                )

                commit = await client.call_tool(
                    "get_commit",
                    {"commit_hash": commit_hash, "repository": "/work/backend"},
                )
                self.assertTrue(commit.data["found"])
                self.assertEqual(commit.data["item"]["commit_hash"], commit_hash)

                detail = await client.call_tool(
                    "get_commit_detail",
                    {"commit_hash": commit_hash, "repository": "/work/backend"},
                )
                self.assertTrue(detail.data["found"])
                self.assertEqual(detail.data["commit"]["commit_hash"], commit_hash)
                self.assertEqual(len(detail.data["file_changes"]), 1)
                self.assertEqual(len(detail.data["related_commands"]), 1)


if __name__ == "__main__":
    unittest.main()
