from __future__ import annotations

from collections.abc import Iterable, Mapping
from hashlib import sha256
import json
import math
import re
from typing import Any


EMBEDDING_MODEL_NAME = "local-concept-embedding-v1"
EMBEDDING_DIMENSIONS = 256

TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]+")

SEMANTIC_GROUPS: dict[str, tuple[str, ...]] = {
    "auth": (
        "auth",
        "authentication",
        "authenticate",
        "login",
        "signin",
        "session",
        "token",
        "jwt",
        "password",
        "credential",
    ),
    "docker": (
        "docker",
        "container",
        "containers",
        "compose",
        "dockerfile",
        "dockerd",
        "image",
        "images",
        "kubernetes",
    ),
    "network": (
        "network",
        "networking",
        "bridge",
        "dns",
        "proxy",
        "port",
        "ports",
        "socket",
        "sockets",
    ),
    "ssl": ("ssl", "tls", "certificate", "cert", "certs", "https"),
    "cuda": ("cuda", "gpu", "nvidia", "cudnn", "pytorch", "torch"),
    "build": ("build", "compile", "compiler", "link", "linker", "ci", "pipeline", "artifact"),
    "test": ("test", "tests", "testing", "pytest", "unittest", "integration"),
    "deploy": ("deploy", "deployment", "release", "rollout", "ship"),
    "error": ("error", "errors", "failed", "failure", "fail", "exception", "traceback", "crash"),
    "git": ("git", "commit", "commits", "branch", "merge", "rebase", "diff", "repository", "repo"),
}


def tokenize(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(value) if token]


def semantic_concept(token: str) -> str:
    normalized = token.lower()
    candidate_forms = {
        normalized,
        normalized.replace("-", ""),
        normalized.replace("_", ""),
        normalized.replace("-", "").replace("_", ""),
    }
    for concept, aliases in SEMANTIC_GROUPS.items():
        for alias in aliases:
            alias_forms = {
                alias,
                alias.replace("-", ""),
                alias.replace("_", ""),
                alias.replace("-", "").replace("_", ""),
            }
            if candidate_forms & alias_forms:
                return concept
            for candidate in candidate_forms:
                if candidate.startswith(alias) or alias.startswith(candidate):
                    return concept
    return normalized


def semantic_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for token in tokenize(value):
        for candidate in (token, semantic_concept(token)):
            if candidate not in seen:
                seen.add(candidate)
                tokens.append(candidate)
    return tokens


def compose_embedding_text(parts: Iterable[Any]) -> str:
    values: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, str):
            candidate = part.strip()
            if candidate:
                values.append(candidate)
            continue
        if isinstance(part, Mapping):
            candidate = json.dumps(part, ensure_ascii=True, sort_keys=True, default=str)
        elif isinstance(part, Iterable) and not isinstance(part, (bytes, bytearray)):
            candidate = " ".join(str(value) for value in part if value is not None)
        else:
            candidate = str(part)
        candidate = candidate.strip()
        if candidate:
            values.append(candidate)
    return "\n".join(values)


def vectorize_text(value: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in semantic_tokens(value):
        digest = sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        magnitude = 1.0 + (digest[5] / 255.0)
        vector[index] += sign * magnitude
    norm = math.sqrt(sum(component * component for component in vector))
    if norm > 0:
        vector = [round(component / norm, 8) for component in vector]
    return vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    return sum(lhs * rhs for lhs, rhs in zip(left, right))
