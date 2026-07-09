from __future__ import annotations

import sqlite3
import unittest

from absolutely_api.schema import create_schema


class SchemaTests(unittest.TestCase):
    def test_creates_core_tables(self) -> None:
        conn = sqlite3.connect(":memory:")
        create_schema(conn)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        }
        self.assertTrue(
            {
                "schema_migrations",
                "sessions",
                "repositories",
                "agents",
                "commands",
                "commits",
                "file_changes",
                "embeddings",
                "daily_summaries",
            }.issubset(tables)
        )

    def test_commands_table_has_core_fields(self) -> None:
        conn = sqlite3.connect(":memory:")
        create_schema(conn)
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(commands)")
        }
        self.assertIn("redaction_findings_json", columns)
        self.assertIn("git_commit_hash", columns)
        self.assertIn("session_record_id", columns)


if __name__ == "__main__":
    unittest.main()

