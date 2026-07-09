from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True, slots=True)
class RedactionResult:
    redacted_text: str
    findings: tuple[str, ...]

    @property
    def changed(self) -> bool:
        return bool(self.findings)


_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "private_key_block",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        "[REDACTED:PRIVATE_KEY_BLOCK]",
    ),
    (
        "secret_assignment",
        re.compile(
            r"(?i)\b((?:export\s+)?[A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASS|PWD|API_KEY|ACCESS_KEY|PRIVATE_KEY)[A-Z0-9_]*)\s*=\s*([^\s'\"`]+)"
        ),
        r"\1=[REDACTED]",
    ),
    (
        "secret_flag",
        re.compile(
            r"(?i)(--?(?:password|pass|token|secret|api[-_]?key|apikey|client[-_]?secret|access[-_]?key))(\s*=\s*|\s+)([^\s'\"`]+)"
        ),
        r"\1\2[REDACTED]",
    ),
    (
        "aws_access_key_id",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        "[REDACTED:AWS_ACCESS_KEY_ID]",
    ),
    (
        "github_token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
        "[REDACTED:GITHUB_TOKEN]",
    ),
    (
        "openai_key",
        re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
        "[REDACTED:OPENAI_KEY]",
    ),
    (
        "google_api_key",
        re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
        "[REDACTED:GOOGLE_API_KEY]",
    ),
    (
        "bearer_token",
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}\b"),
        "Bearer [REDACTED]",
    ),
    (
        "ssh_private_key",
        re.compile(
            r"-----BEGIN [A-Z ]*OPENSSH PRIVATE KEY-----.*?-----END [A-Z ]*OPENSSH PRIVATE KEY-----",
            re.DOTALL,
        ),
        "[REDACTED:SSH_PRIVATE_KEY]",
    ),
)


def _dedupe(findings: Sequence[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for finding in findings:
        seen.setdefault(finding, None)
    return tuple(seen.keys())


def redact_text(value: str) -> RedactionResult:
    redacted = value
    findings: list[str] = []
    for name, pattern, replacement in _RULES:
        if pattern.search(redacted):
            findings.append(name)
            redacted = pattern.sub(replacement, redacted)
    return RedactionResult(redacted_text=redacted, findings=_dedupe(findings))


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value).redacted_text
    if isinstance(value, Mapping):
        return {key: redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, set):
        return [redact_value(item) for item in value]
    return value
