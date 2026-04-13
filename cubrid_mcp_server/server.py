"""FastMCP server exposing read-only CUBRID tools."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from cubrid_mcp_server.config import Config
from cubrid_mcp_server.database import Database
from cubrid_mcp_server.safety import ensure_read_only

mcp = FastMCP("cubrid-mcp-server")

_config: Config | None = None
_database: Database | None = None


def _db() -> Database:
    global _config, _database
    if _database is None:
        _config = Config.from_env()
        _database = Database(_config)
    return _database


@mcp.tool
def all_table_names() -> list[str]:
    """Return every user table in the connected CUBRID database."""
    rows = _db().fetch_all(
        "SELECT class_name FROM db_class WHERE is_system_class='NO' ORDER BY class_name"
    )
    return [row[0] for row in rows]


@mcp.tool
def filter_table_names(substring: str) -> list[str]:
    """Return user tables whose name contains ``substring`` (case-insensitive)."""
    needle = substring.strip().lower()
    if not needle:
        return []
    return [name for name in all_table_names() if needle in name.lower()]


@mcp.tool
def schema_definitions(table_name: str) -> list[dict[str, Any]]:
    """Return column metadata for ``table_name``: name, type, nullability, default, PK flag."""
    rows = _db().fetch_all(
        """
        SELECT a.attr_name, a.data_type, a.is_nullable, a.default_value
        FROM db_attribute a
        WHERE a.class_name = ?
        ORDER BY a.def_order
        """,
        (table_name,),
    )
    pk_rows = _db().fetch_all(
        """
        SELECT k.key_attr_name
        FROM db_index i, db_index_key k
        WHERE i.class_name = ?
          AND i.is_primary_key = 'YES'
          AND i.index_name = k.index_name
          AND i.class_name = k.class_name
        """,
        (table_name,),
    )
    pk_columns: set[str] = {r[0] for r in pk_rows}
    return [
        {
            "name": row[0],
            "type": row[1],
            "nullable": row[2] == "YES",
            "default": row[3],
            "primary_key": row[0] in pk_columns,
        }
        for row in rows
    ]


@mcp.tool
def describe_table(table_name: str) -> dict[str, Any]:
    """Return full metadata for ``table_name``: columns, primary key, and indexes."""
    columns = schema_definitions(table_name)
    indexes = list_indexes(table_name)
    primary_key = [col["name"] for col in columns if col["primary_key"]]
    return {
        "table": table_name,
        "columns": columns,
        "primary_key": primary_key,
        "indexes": indexes,
    }


@mcp.tool
def list_indexes(table_name: str) -> list[dict[str, Any]]:
    """Return indexes for ``table_name`` with their key columns and flags."""
    rows = _db().fetch_all(
        """
        SELECT i.index_name, i.is_unique, i.is_primary_key, i.is_foreign_key,
               i.is_reverse, i.key_count, k.key_attr_name, k.key_order, k.asc_desc
        FROM db_index i, db_index_key k
        WHERE i.class_name = ?
          AND i.index_name = k.index_name
          AND i.class_name = k.class_name
        ORDER BY i.index_name, k.key_order
        """,
        (table_name,),
    )
    indexes: dict[str, dict[str, Any]] = {}
    for r in rows:
        name = r[0]
        entry = indexes.setdefault(
            name,
            {
                "name": name,
                "unique": r[1] == "YES",
                "primary_key": r[2] == "YES",
                "foreign_key": r[3] == "YES",
                "reverse": r[4] == "YES",
                "key_count": r[5],
                "columns": [],
            },
        )
        entry["columns"].append({"name": r[6], "order": r[7], "asc_desc": r[8]})
    return list(indexes.values())


@mcp.tool
def explain_query(sql: str) -> dict[str, Any]:
    """Return CUBRID's execution plan/trace for a ``SELECT`` or ``WITH`` statement."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise ValueError("empty SQL statement")
    leading = cleaned.split(None, 1)[0].upper()
    if leading not in {"SELECT", "WITH"}:
        raise ValueError("explain_query only accepts SELECT or WITH statements")

    db = _db()
    plan = ""
    try:
        with db.cursor() as cur:
            cur.execute("SET TRACE ON", ())
            cur.execute(cleaned, ())
            cur.fetchall()
            cur.execute("SHOW TRACE", ())
            trace_rows = cur.fetchall()
            if trace_rows and trace_rows[0]:
                plan = str(trace_rows[0][0] or "").strip()
    finally:
        try:
            with db.cursor() as cur:
                cur.execute("SET TRACE OFF", ())
        except Exception:
            pass
        try:
            db.connect().rollback()
        except Exception:
            pass

    return {"sql": cleaned, "plan": plan}


@mcp.tool
def table_row_counts(table_names: list[str] | None = None) -> list[dict[str, Any]]:
    """Return ``COUNT(*)`` for each table (all user tables by default)."""
    targets = table_names if table_names else all_table_names()
    results: list[dict[str, Any]] = []
    for name in targets:
        try:
            rows = _db().fetch_all(f'SELECT COUNT(*) FROM "{name}"')
            results.append({"table": name, "row_count": int(rows[0][0]) if rows else 0})
        except Exception as exc:
            results.append({"table": name, "row_count": None, "error": str(exc)})
    return results


@mcp.tool
def list_serials() -> list[dict[str, Any]]:
    """Return CUBRID SERIAL sequences with current value, increment, and bounds."""
    rows = _db().fetch_all(
        """
        SELECT name, current_val, increment_val, max_val, min_val,
               cyclic, started, class_name, att_name, cached_num, comment
        FROM db_serial
        ORDER BY name
        """
    )
    return [
        {
            "name": r[0],
            "current_value": _coerce(r[1]),
            "increment": _coerce(r[2]),
            "max_value": _coerce(r[3]),
            "min_value": _coerce(r[4]),
            "cyclic": r[5] == 1 or r[5] == "1",
            "started": r[6] == 1 or r[6] == "1",
            "class_name": r[7],
            "attribute_name": r[8],
            "cached_num": r[9],
            "comment": r[10],
        }
        for r in rows
    ]


@mcp.tool
def list_class_hierarchy(table_name: str | None = None) -> list[dict[str, Any]]:
    """Return CUBRID CLASS inheritance relationships (all classes or one class)."""
    if table_name:
        rows = _db().fetch_all(
            "SELECT class_name, super_class_name FROM db_direct_super_class "
            "WHERE class_name = ? ORDER BY super_class_name",
            (table_name,),
        )
    else:
        rows = _db().fetch_all(
            "SELECT class_name, super_class_name FROM db_direct_super_class "
            "ORDER BY class_name, super_class_name"
        )
    hierarchy: dict[str, list[str]] = {}
    for child, parent in rows:
        hierarchy.setdefault(child, []).append(parent)
    return [{"class_name": k, "super_classes": v} for k, v in hierarchy.items()]


@mcp.tool
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
