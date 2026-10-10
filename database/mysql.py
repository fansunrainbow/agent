from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any

from .config import DatabaseConfig


FORBIDDEN_PRIVILEGES = {"INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "TRUNCATE", "ALL PRIVILEGES"}


@dataclass
class DatabaseCapability:
    connected: bool
    select_allowed: bool
    readonly_verified: bool
    grants: list[str]
    forbidden_privileges: list[str]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class _CursorAdapter:
    def __init__(self, cursor: Any):
        self._cursor = cursor

    @property
    def description(self):
        return self._cursor.description

    @staticmethod
    def _bind(sql: str) -> str:
        return re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"%(\1)s", sql)

    def execute(self, sql: str, params: dict[str, Any] | None = None):
        return self._cursor.execute(self._bind(sql), params or {})

    def fetchmany(self, count: int):
        return self._cursor.fetchmany(count)

    def fetchall(self):
        return self._cursor.fetchall()


class MySQLReadOnlyConnection:
    """Small DB-API adapter with an explicit read-only contract."""

    read_only = True

    def __init__(self, raw_connection: Any, config: DatabaseConfig):
        self.raw_connection = raw_connection
        self.config = config

    def set_session(self, readonly: bool = False) -> None:
        if not readonly:
            raise PermissionError("只允许只读会话")
        cursor = self.raw_connection.cursor()
        cursor.execute("SET SESSION TRANSACTION READ ONLY")
        cursor.close()

    def set_statement_timeout(self, seconds: int) -> None:
        timeout_ms = max(1, int(seconds)) * 1000
        cursor = self.raw_connection.cursor()
        cursor.execute("SET SESSION MAX_EXECUTION_TIME = %s", (timeout_ms,))
        cursor.close()

    def cursor(self) -> _CursorAdapter:
        return _CursorAdapter(self.raw_connection.cursor())

    def explain(self, sql: str, params: dict[str, Any]) -> dict[str, Any]:
        cursor = self.cursor()
        cursor.execute("EXPLAIN FORMAT=JSON " + sql, params)
        row = cursor.fetchall()[0]
        raw = row[0] if not isinstance(row, dict) else next(iter(row.values()))
        plan = json.loads(raw) if isinstance(raw, str) else raw
        estimates: list[float] = []
        access_types: list[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"rows_examined_per_scan", "rows_produced_per_join"} and isinstance(item, (int, float)):
                        estimates.append(float(item))
                    if key == "access_type":
                        access_types.append(str(item))
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(plan)
        return {
            "format": "json", "estimated_rows": int(sum(estimates)),
            "max_estimated_rows": int(max(estimates, default=0)),
            "access_types": sorted(set(access_types)), "plan": plan,
        }

    def capability_check(self) -> DatabaseCapability:
        try:
            cursor = self.raw_connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.execute("SHOW GRANTS FOR CURRENT_USER")
            grants = [str(row[0]) for row in cursor.fetchall()]
            upper = "\n".join(grants).upper()
            forbidden = sorted(item for item in FORBIDDEN_PRIVILEGES if re.search(rf"\b{re.escape(item)}\b", upper))
            select_allowed = bool(re.search(r"\bSELECT\b", upper))
            return DatabaseCapability(True, select_allowed, select_allowed and not forbidden, grants, forbidden)
        except Exception as exc:
            return DatabaseCapability(False, False, False, [], [], f"{type(exc).__name__}: {exc}")

    def close(self) -> None:
        self.raw_connection.close()


def create_readonly_connection(config: DatabaseConfig | None = None) -> MySQLReadOnlyConnection:
    from sqlalchemy import create_engine

    value = config or DatabaseConfig.from_env()
    engine = create_engine(
        value.url, pool_size=value.pool_size, pool_recycle=value.pool_recycle,
        pool_pre_ping=True, connect_args={"connect_timeout": value.connect_timeout},
    )
    return MySQLReadOnlyConnection(engine.raw_connection(), value)
