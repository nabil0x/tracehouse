from __future__ import annotations

import unittest

from absolutely_api.redaction import redact_text, redact_value


class RedactionTests(unittest.TestCase):
    def test_redacts_multiple_secret_forms(self) -> None:
        result = redact_text(
            "AWS_SECRET_ACCESS_KEY=abc123 --password hunter2 Bearer ghp_supersecretvalue1234567890"
        )
        self.assertTrue(result.changed)
        self.assertIn("[REDACTED]", result.redacted_text)
        self.assertIn("secret_assignment", result.findings)
        self.assertIn("secret_flag", result.findings)
        self.assertIn("github_token", result.findings)

    def test_redacts_nested_values(self) -> None:
        value = {"token": "sk-abcdefghijklmnopqrstuvwx", "items": ["password=secret"]}
        redacted = redact_value(value)
        self.assertEqual(redacted["items"][0], "password=[REDACTED]")
        self.assertTrue(redacted["token"].startswith("[REDACTED"))


if __name__ == "__main__":
    unittest.main()

