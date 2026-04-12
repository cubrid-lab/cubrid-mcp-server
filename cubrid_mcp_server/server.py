"""FastMCP server exposing read-only CUBRID tools."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP  # type: ignore[import-not-found]

from cubrid_mcp_server.config import Config
from cubrid_mcp_server.database import Database  # type: ignore[import-not-found]
from cubrid_mcp_server.safety import ensure_read_only  # type: ignore[import-not-found]

mcp = FastMCP("cubrid-mcp-server")

_config: Config | None = None
_database: Database | None = None


def _db() -> Database:
    global _config, _database
    if _database is None:
        _config = Config.from_env()
        _database = Database(_config)
    return _database


@mcp.tool  # type: ignore[misc]
def all_table_names() -> list[str]:
    """Return every user table in the connected CUBRID database."""
    rows = _db().fetch_all(
        "SELECT class_name FROM db_class WHERE is_system_class='NO' ORDER BY class_name"
    )
    return [row[0] for row in rows]


@mcp.tool  # type: ignore[misc]
def filter_table_names(substring: str) -> list[str]:
    """Return user tables whose name contains ``substring`` (case-insensitive)."""
    needle = substring.strip().lower()
    if not needle:
        return []
    return [name for name in all_table_names() if needle in name.lower()]


@mcp.tool  # type: ignore[misc]
def schema_definitions(table_name: str) -> list[dict[str, Any]]:
    """Return column metadata for ``table_name``: name, type, nullability, default, PK flag."""
    rows = _db().fetch_all(
        """
        SELECT attr_name, data_type, is_nullable, default_value, key_type
        FROM db_attribute
        WHERE class_name = ?
        ORDER BY def_order
        """,
        (table_name,),
    )
    return [
        {
            "name": row[0],
            "type": row[1],
            "nullable": row[2] == "YES",
            "default": row[3],
            "primary_key": row[4] == "PRI",
        }
        for row in rows
    ]


@mcp.tool  # type: ignore[misc]
def execute_query(sql: str) -> dict[str, Any]:
    """Execute a read-only SQL statement and return rows, truncated if large."""
    config = _config or Config.from_env()
    if config.readonly:
        ensure_read_only(sql)

    rows = _db().fetch_all(sql)
    rendered = _render_rows(rows, config.max_chars)
    return {
        "row_count": len(rows),
        "truncated": rendered["truncated"],
        "rows": rendered["rows"],
    }


def _render_rows(rows: list[tuple[Any, ...]], max_chars: int) -> dict[str, Any]:
    output: list[list[Any]] = []
    used = 0
    for row in rows:
        serialized = [_coerce(value) for value in row]
        used += sum(len(str(value)) for value in serialized)
        if used > max_chars:
            return {"rows": output, "truncated": True}
        output.append(serialized)
    return {"rows": output, "truncated": False}


def _coerce(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def main() -> None:
    mcp.run()
