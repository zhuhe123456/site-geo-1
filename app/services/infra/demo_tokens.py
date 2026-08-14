from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_hint(token: str) -> str:
    if len(token) <= 10:
        return f"{token[:2]}…{token[-2:]}"
    return f"{token[:6]}…{token[-4:]}"


class DemoTokenStore:
    """SQLite-backed API token and usage log store."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path

    @property
    def db_path(self) -> Path:
        return Path(self._db_path or settings.demo_token_db_path)

    def _connect(self) -> sqlite3.Connection:
        path = self.db_path
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        self._initialize(connection)
        return connection

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS demo_access_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                token_value TEXT,
                token_hint TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                max_calls INTEGER CHECK (max_calls IS NULL OR max_calls > 0),
                used_calls INTEGER NOT NULL DEFAULT 0 CHECK (used_calls >= 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_used_at TEXT
            )
            """
        )
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(demo_access_tokens)").fetchall()
        }
        if "token_value" not in columns:
            connection.execute("ALTER TABLE demo_access_tokens ADD COLUMN token_value TEXT")
        if "max_calls" not in columns:
            connection.execute("ALTER TABLE demo_access_tokens ADD COLUMN max_calls INTEGER")
        if "used_calls" not in columns:
            connection.execute("ALTER TABLE demo_access_tokens ADD COLUMN used_calls INTEGER NOT NULL DEFAULT 0")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_demo_access_tokens_enabled ON demo_access_tokens(enabled)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS api_token_usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                token_id INTEGER,
                token_name TEXT,
                token_hint TEXT,
                auth_source TEXT NOT NULL,
                auth_outcome TEXT NOT NULL,
                credential_transport TEXT NOT NULL,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                route_name TEXT,
                query_string TEXT,
                client_ip TEXT,
                forwarded_for TEXT,
                user_agent TEXT,
                referer TEXT,
                content_type TEXT,
                request_bytes INTEGER,
                status_code INTEGER NOT NULL,
                response_bytes INTEGER,
                duration_ms REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (token_id) REFERENCES demo_access_tokens(id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_token_logs_created ON api_token_usage_logs(created_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_token_logs_token ON api_token_usage_logs(token_id, created_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_token_logs_outcome ON api_token_usage_logs(auth_outcome, created_at DESC)"
        )
        connection.commit()

    @staticmethod
    def _serialize(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "token_hint": row["token_hint"],
            "token": row["token_value"] if "token_value" in row.keys() else None,
            "enabled": bool(row["enabled"]),
            "max_calls": row["max_calls"],
            "used_calls": row["used_calls"],
            "remaining_calls": (
                max(0, row["max_calls"] - row["used_calls"])
                if row["max_calls"] is not None
                else None
            ),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_used_at": row["last_used_at"],
            "usage_count": row["usage_count"] if "usage_count" in row.keys() else 0,
        }

    def list_tokens(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT t.id, t.name, t.token_value, t.token_hint, t.enabled,
                       t.max_calls, t.used_calls, t.created_at, t.updated_at,
                       t.last_used_at, COUNT(l.id) AS usage_count
                FROM demo_access_tokens AS t
                LEFT JOIN api_token_usage_logs AS l ON l.token_id = t.id
                GROUP BY t.id
                ORDER BY t.id DESC
                """
            ).fetchall()
        return [self._serialize(row) for row in rows]

    def has_enabled_tokens(self) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM demo_access_tokens WHERE enabled = 1 LIMIT 1"
            ).fetchone()
        return row is not None

    def has_tokens(self) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM demo_access_tokens LIMIT 1"
            ).fetchone()
        return row is not None

    def create_token(
        self, name: str, token: str | None = None, max_calls: int | None = None
    ) -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("token name is required")
        if len(clean_name) > 80:
            raise ValueError("token name must not exceed 80 characters")

        clear_token = (token or "").strip() or f"geo_{secrets.token_urlsafe(24)}"
        if len(clear_token) < 12:
            raise ValueError("token must contain at least 12 characters")
        if len(clear_token) > 256:
            raise ValueError("token must not exceed 256 characters")
        if max_calls is not None and max_calls < 1:
            raise ValueError("max calls must be at least 1")

        now = _utc_now()
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO demo_access_tokens
                        (name, token_hash, token_value, token_hint, enabled, max_calls,
                         used_calls, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, 0, ?, ?)
                    """,
                    (
                        clean_name, _token_hash(clear_token), clear_token,
                        _token_hint(clear_token), max_calls, now, now,
                    ),
                )
                row = connection.execute(
                    """
                    SELECT id, name, token_value, token_hint, enabled, max_calls, used_calls,
                           created_at, updated_at, last_used_at,
                           0 AS usage_count
                    FROM demo_access_tokens WHERE id = ?
                    """,
                    (cursor.lastrowid,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ValueError("token already exists") from exc

        result = self._serialize(row)
        result["token"] = clear_token
        return result

    def set_enabled(self, token_id: int, enabled: bool) -> dict[str, Any] | None:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE demo_access_tokens SET enabled = ?, updated_at = ? WHERE id = ?",
                (int(enabled), _utc_now(), token_id),
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute(
                """
                SELECT id, name, token_value, token_hint, enabled, max_calls, used_calls,
                       created_at, updated_at, last_used_at,
                       (SELECT COUNT(*) FROM api_token_usage_logs WHERE token_id = demo_access_tokens.id) AS usage_count
                FROM demo_access_tokens WHERE id = ?
                """,
                (token_id,),
            ).fetchone()
        return self._serialize(row)

    def set_limit(self, token_id: int, max_calls: int | None) -> dict[str, Any] | None:
        if max_calls is not None and max_calls < 1:
            raise ValueError("max calls must be at least 1")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE demo_access_tokens SET max_calls = ?, updated_at = ? WHERE id = ?",
                (max_calls, _utc_now(), token_id),
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute(
                """
                SELECT id, name, token_value, token_hint, enabled, max_calls, used_calls,
                       created_at, updated_at, last_used_at,
                       (SELECT COUNT(*) FROM api_token_usage_logs WHERE token_id = demo_access_tokens.id) AS usage_count
                FROM demo_access_tokens WHERE id = ?
                """,
                (token_id,),
            ).fetchone()
        return self._serialize(row)

    def reset_usage(self, token_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE demo_access_tokens SET used_calls = 0, updated_at = ? WHERE id = ?",
                (_utc_now(), token_id),
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute(
                """
                SELECT id, name, token_value, token_hint, enabled, max_calls, used_calls,
                       created_at, updated_at, last_used_at,
                       (SELECT COUNT(*) FROM api_token_usage_logs WHERE token_id = demo_access_tokens.id) AS usage_count
                FROM demo_access_tokens WHERE id = ?
                """,
                (token_id,),
            ).fetchone()
        return self._serialize(row)

    def delete_token(self, token_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM demo_access_tokens WHERE id = ?", (token_id,)
            )
        return cursor.rowcount > 0

    def resolve_token(self, token: str, *, consume: bool = True) -> dict[str, Any] | None:
        provided = token.strip()
        if not provided:
            return None
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT id, name, token_hint, enabled, max_calls, used_calls
                FROM demo_access_tokens WHERE token_hash = ? LIMIT 1
                """,
                (_token_hash(provided),),
            ).fetchone()
            if row is None:
                return None
            quota_exceeded = (
                row["max_calls"] is not None and row["used_calls"] >= row["max_calls"]
            )
            used_calls = row["used_calls"]
            if bool(row["enabled"]) and not quota_exceeded and consume:
                used_calls += 1
                connection.execute(
                    "UPDATE demo_access_tokens SET used_calls = ?, last_used_at = ? WHERE id = ?",
                    (used_calls, _utc_now(), row["id"]),
                )
        return {
            "id": row["id"],
            "name": row["name"],
            "token_hint": row["token_hint"],
            "enabled": bool(row["enabled"]),
            "max_calls": row["max_calls"],
            "used_calls": used_calls,
            "quota_exceeded": quota_exceeded,
        }

    def verify(self, token: str) -> bool:
        resolved = self.resolve_token(token, consume=False)
        return bool(resolved and resolved["enabled"] and not resolved["quota_exceeded"])

    def log_usage(self, entry: dict[str, Any]) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=settings.token_log_retention_days)).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO api_token_usage_logs (
                    request_id, token_id, token_name, token_hint, auth_source, auth_outcome,
                    credential_transport, method, path, route_name, query_string, client_ip,
                    forwarded_for, user_agent, referer, content_type, request_bytes,
                    status_code, response_bytes, duration_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry["request_id"], entry.get("token_id"), entry.get("token_name"),
                    entry.get("token_hint"), entry["auth_source"], entry["auth_outcome"],
                    entry["credential_transport"], entry["method"], entry["path"],
                    entry.get("route_name"), entry.get("query_string"), entry.get("client_ip"),
                    entry.get("forwarded_for"), entry.get("user_agent"), entry.get("referer"),
                    entry.get("content_type"), entry.get("request_bytes"), entry["status_code"],
                    entry.get("response_bytes"), entry["duration_ms"], entry.get("created_at", _utc_now()),
                ),
            )
            connection.execute(
                "DELETE FROM api_token_usage_logs WHERE created_at < ?", (cutoff,)
            )

    def list_usage_logs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        token_id: int | None = None,
        auth_outcome: str | None = None,
    ) -> dict[str, Any]:
        filters: list[str] = []
        params: list[Any] = []
        if token_id is not None:
            filters.append("token_id = ?")
            params.append(token_id)
        if auth_outcome:
            filters.append("auth_outcome = ?")
            params.append(auth_outcome)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        with self._connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM api_token_usage_logs {where}", params
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT id, request_id, token_id, token_name, token_hint, auth_source,
                       auth_outcome, credential_transport, method, path, route_name,
                       query_string, client_ip, forwarded_for, user_agent, referer,
                       content_type, request_bytes, status_code, response_bytes,
                       duration_ms, created_at
                FROM api_token_usage_logs
                {where}
                ORDER BY id DESC LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    def clear_usage_logs(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM api_token_usage_logs")
        return cursor.rowcount


demo_token_store = DemoTokenStore()
