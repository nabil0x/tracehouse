from __future__ import annotations

from collections.abc import Mapping
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timezone
import os
import json
import sqlite3
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .schema import SCHEMA_VERSION


EXPORT_MODEL_NAME = "tracehouse-export-v1"
ENCRYPTION_KDF_NAME = "pbkdf2-hmac-sha256"
ENCRYPTION_ITERATIONS = 390000
ENCRYPTION_SALT_BYTES = 16

TABLE_EXPORT_ORDER: tuple[tuple[str, str], ...] = (
    ("schema_migrations", "ORDER BY version ASC"),
    ("sessions", "ORDER BY started_at ASC, id ASC"),
    ("repositories", "ORDER BY last_seen_at DESC, id ASC"),
    ("agents", "ORDER BY last_seen_at DESC, id ASC"),
    ("commands", "ORDER BY timestamp_start ASC, id ASC"),
    ("commits", "ORDER BY committed_at ASC, id ASC"),
    ("file_changes", "ORDER BY repository_id ASC, commit_id ASC, id ASC"),
    ("embeddings", "ORDER BY created_at ASC, id ASC"),
    ("daily_summaries", "ORDER BY created_at ASC, id ASC"),
)

JSON_COLUMN_DEFAULTS: dict[str, Any] = {
    "metadata_json": {},
    "redaction_findings_json": [],
    "repositories_json": [],
    "top_tools_json": [],
    "vector_json": [],
}

DELETION_ORDER: tuple[str, ...] = (
    "file_changes",
    "embeddings",
    "commands",
    "commits",
    "daily_summaries",
    "agents",
    "repositories",
    "sessions",
)


def _json_or_default(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _export_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    for column, default in JSON_COLUMN_DEFAULTS.items():
        if column in item:
            item[column.removesuffix("_json")] = _json_or_default(item.pop(column), default)
    return item


def _fetch_table_rows(conn: sqlite3.Connection, table: str, order_by: str) -> list[dict[str, Any]]:
    rows = conn.execute(f"SELECT * FROM {table} {order_by}").fetchall()
    return [_export_row(row) for row in rows]


def build_export_bundle(conn: sqlite3.Connection) -> dict[str, Any]:
    tables = {
        table_name: _fetch_table_rows(conn, table_name, order_by)
        for table_name, order_by in TABLE_EXPORT_ORDER
    }
    return {
        "format": "tracehouse-export",
        "version": 1,
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "table_counts": {table_name: len(rows) for table_name, rows in tables.items()},
        "tables": tables,
    }


def _derive_fernet_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ENCRYPTION_ITERATIONS,
    )
    return urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt_export_bundle(bundle: Mapping[str, Any], passphrase: str) -> dict[str, Any]:
    normalized_passphrase = passphrase.strip()
    if not normalized_passphrase:
        raise ValueError("passphrase is required for encrypted exports")

    salt = os.urandom(ENCRYPTION_SALT_BYTES)
    key = _derive_fernet_key(normalized_passphrase, salt)
    token = Fernet(key).encrypt(
        json.dumps(bundle, ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")
    )
    return {
        "format": "tracehouse-encrypted-export",
        "version": 1,
        "encrypted": True,
        "schema_version": SCHEMA_VERSION,
        "exported_at": bundle.get("exported_at"),
        "kdf": {
            "name": ENCRYPTION_KDF_NAME,
            "iterations": ENCRYPTION_ITERATIONS,
            "salt": urlsafe_b64encode(salt).decode("ascii"),
        },
        "ciphertext": token.decode("ascii"),
    }


def decrypt_export_bundle(envelope: Mapping[str, Any], passphrase: str) -> dict[str, Any]:
    if envelope.get("format") not in {"absolutely-encrypted-export", "tracehouse-encrypted-export"}:
        raise ValueError("not an encrypted export envelope")
    kdf = envelope.get("kdf")
    ciphertext = envelope.get("ciphertext")
    if not isinstance(kdf, Mapping) or not isinstance(ciphertext, str):
        raise ValueError("invalid encrypted export envelope")
    salt_value = kdf.get("salt")
    if not isinstance(salt_value, str) or not salt_value.strip():
        raise ValueError("encrypted export is missing a salt")
    salt = urlsafe_b64decode(salt_value.encode("ascii"))
    key = _derive_fernet_key(passphrase.strip(), salt)
    try:
        plaintext = Fernet(key).decrypt(ciphertext.encode("ascii"))
    except InvalidToken as error:
        raise ValueError("passphrase is incorrect or export is corrupted") from error
    return json.loads(plaintext.decode("utf-8"))


def delete_all_data(conn: sqlite3.Connection) -> dict[str, int]:
    deleted: dict[str, int] = {}
    for table in DELETION_ORDER:
        deleted[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.execute("VACUUM")
    return deleted


def privacy_status(conn: sqlite3.Connection) -> dict[str, Any]:
    counts = {
        table_name: int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
        for table_name, _ in TABLE_EXPORT_ORDER
        if table_name != "schema_migrations"
    }
    return {
        "counts": counts,
        "export": {
            "supported": True,
            "formats": ["json", "encrypted-json"],
            "encrypted_supported": True,
        },
        "delete": {
            "supported": True,
            "confirmation": "DELETE ALL DATA",
        },
        "encryption": {
            "supported": True,
            "scope": "export-bundles",
            "algorithm": "fernet",
            "kdf": ENCRYPTION_KDF_NAME,
            "iterations": ENCRYPTION_ITERATIONS,
        },
    }
