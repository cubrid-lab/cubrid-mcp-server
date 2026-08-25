"""FastMCP server exposing read-only CUBRID tools."""

from __future__ import annotations

import base64
import logging
import sys
import threading
from typing import Any

from fastmcp import FastMCP

from cubrid_mcp_server.config import Config, ConfigError
from cubrid_mcp_server.context import AppContext
from cubrid_mcp_server.database import Database, sanitize_error
from cubrid_mcp_server.safety import ensure_read_only

logger = logging.getLogger(__name__)

mcp = FastMCP("cubrid-mcp-server")

# Cap on how many tables ``table_row_counts`` will scan in a single call, to avoid
# accidentally issuing hundreds of COUNT(*) queries against a large database.
_MAX_ROW_COUNT_TABLES = 50

# Binary values up to this size are returned base64-encoded; larger blobs are summarized.
_MAX_INLINE_BINARY_BYTES = 256

_context: AppContext | None = None
_context_lock = threading.Lock()


def _get_context() -> AppContext:
    """Return the process-wide :class:`AppContext`, building it lazily from env.

    Guarded by a lock with a double-checked pattern so that two concurrent
    first tool calls cannot each build a separate context (and leak a
    ``Database`` connection); exactly one context is published.
    """
    global _context
    if _context is None:
        with _context_lock:
            if _context is None:
                _context = AppContext.from_env()
    return _context


def _db() -> Database:
    return _get_context().database


def _cfg() -> Config:
    return _get_context().config


def _all_table_names() -> list[str]:
    """Internal helper: list every user table (excludes system classes and views)."""
    rows = _db().fetch_all(
        "SELECT class_name FROM db_class "
        "WHERE is_system_class='NO' AND class_type='CLASS' "
        "ORDER BY class_name"
    )
    return [row[0] for row in rows]


def _resolve_table(table_name: str) -> str:
    """Resolve ``table_name`` to its canonical stored name (case-insensitive).

    Raises :class:`ValueError` if no matching user table exists. This both prevents
    lookups against system classes/views and gives callers a clear error instead of
    silently returning empty metadata.
    """
    needle = table_name.strip().lower()
    if not needle:
        raise ValueError("table name must not be empty")
    for name in _all_table_names():
        if name.lower() == needle:
            return name
    raise ValueError(f"unknown table: {table_name!r}")


@mcp.tool
def all_table_names() -> list[str]:
    """Return every user table in the connected CUBRID database."""
    return _all_table_names()


@mcp.tool
def filter_table_names(substring: str) -> list[str]:
    """Return user tables whose name contains ``substring`` (case-insensitive)."""
    needle = substring.strip().lower()
    if not needle:
        return []
    return [name for name in _all_table_names() if needle in name.lower()]


def _schema_definitions(table_name: str) -> list[dict[str, Any]]:
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
def schema_definitions(table_name: str) -> list[dict[str, Any]]:
    """Return column metadata for ``table_name``: name, type, nullability, default, PK flag."""
    return _schema_definitions(_resolve_table(table_name))


@mcp.tool
def describe_table(table_name: str) -> dict[str, Any]:
    """Return full metadata for ``table_name``: columns, primary key, and indexes."""
    resolved = _resolve_table(table_name)
    columns = _schema_definitions(resolved)
    indexes = _list_indexes(resolved)
    primary_key = [col["name"] for col in columns if col["primary_key"]]
    return {
        "table": resolved,
        "columns": columns,
        "primary_key": primary_key,
        "indexes": indexes,
    }


def _list_indexes(table_name: str) -> list[dict[str, Any]]:
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
def list_indexes(table_name: str) -> list[dict[str, Any]]:
    """Return indexes for ``table_name`` with their key columns and flags."""
    return _list_indexes(_resolve_table(table_name))


@mcp.tool
def explain_query(sql: str) -> dict[str, Any]:
    """Return CUBRID's execution plan/trace for a ``SELECT`` or ``WITH`` statement."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise ValueError("empty SQL statement")
    config = _cfg()
    if len(cleaned) > config.max_sql_length:
        raise ValueError(
            f"SQL exceeds maximum length of {config.max_sql_length} characters "
            f"(CUBRID_MCP_MAX_SQL_LENGTH)"
        )
    leading = cleaned.split(None, 1)[0].upper()
    if leading not in {"SELECT", "WITH"}:
        raise ValueError("explain_query only accepts SELECT or WITH statements")
    # explain_query is *intentionally* always read-only, regardless of
    # ``config.readonly``: it can only ever produce a plan for a SELECT/WITH query,
    # so there is no meaningful write-mode behavior to gate. This differs from
    # execute_query, which honors CUBRID_MCP_READONLY. ensure_read_only also rejects
    # embedded second statements (e.g. "SELECT 1; DROP TABLE x") as defense in depth.
    ensure_read_only(cleaned)

    plan = ""
    with _db().trace_enabled() as cursor:
        cursor.execute(cleaned, ())
        cursor.execute("SHOW TRACE", ())
        trace_rows = cursor.fetchall()
        if trace_rows and trace_rows[0]:
            plan = str(trace_rows[0][0] or "").strip()

    return {"sql": cleaned, "plan": plan}


@mcp.tool
def table_row_counts(table_names: list[str] | None = None) -> list[dict[str, Any]]:
    """Return ``COUNT(*)`` for each table (all user tables by default, capped)."""
    known = _all_table_names()
    known_lower = {name.lower(): name for name in known}
    targets = table_names if table_names else sorted(known)
    if len(targets) > _MAX_ROW_COUNT_TABLES:
        raise ValueError(
            f"too many tables requested ({len(targets)}); limit is {_MAX_ROW_COUNT_TABLES} per call"
        )
    results: list[dict[str, Any]] = []
    for name in targets:
        resolved = known_lower.get(name.strip().lower())
        if resolved is None:
            results.append({"table": name, "row_count": None, "error": "unknown table"})
            continue
        try:
            rows = _db().fetch_all("SELECT COUNT(*) FROM " + _quote_ident(resolved))
            results.append({"table": resolved, "row_count": int(rows[0][0]) if rows else 0})
        except Exception as exc:
            logger.error("row count failed for table %s", resolved, exc_info=exc)
            results.append({"table": resolved, "row_count": None, "error": sanitize_error(exc)})
    return results


def _quote_ident(name: str) -> str:
    """Escape and double-quote a SQL identifier (ANSI style)."""
    return '"' + name.replace('"', '""') + '"'


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
    db = _db()
    config = _cfg()
    if len(sql) > config.max_sql_length:
        raise ValueError(
            f"SQL exceeds maximum length of {config.max_sql_length} characters "
            f"(CUBRID_MCP_MAX_SQL_LENGTH)"
        )
    if config.readonly:
        ensure_read_only(sql)

    rows, row_truncated = db.fetch_many(sql, None, config.max_rows)
    rendered = _render_rows(rows, config.max_chars)
    return {
        "row_count": len(rendered["rows"]),
        "truncated": bool(rendered["truncated"] or row_truncated),
        "rows": rendered["rows"],
    }


@mcp.tool
def health_check() -> dict[str, Any]:
    """Check database connectivity on demand and report server status."""
    return _db().health_check()


def _render_rows(rows: list[tuple[Any, ...]], max_chars: int) -> dict[str, Any]:
    output: list[list[Any]] = []
    used = 0
    truncated = False
    for row in rows:
        serialized = [_truncate_value(_coerce(value), max_chars) for value in row]
        used += sum(len(str(value)) for value in serialized)
        # Always include at least one row, even when it alone exceeds max_chars,
        # so callers see *something* instead of an empty truncated result.
        if used > max_chars and output:
            truncated = True
            break
        output.append(serialized)
    return {"rows": output, "truncated": truncated}


def _truncate_value(value: Any, limit: int) -> Any:
    """Truncate an individual string value that alone exceeds ``limit`` characters."""
    if isinstance(value, str) and limit > 0 and len(value) > limit:
        return value[: limit - 1] + "\u2026"
    return value


def _coerce(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (bytes, bytearray)):
        data = bytes(value)
        if len(data) <= _MAX_INLINE_BINARY_BYTES:
            return base64.b64encode(data).decode("ascii")
        return f"<binary {len(data)} bytes>"
    return str(value)


def main() -> None:
    # The MCP stdio transport uses stdout as the protocol channel, so ALL logging
    # must go to stderr — a stray log line on stdout corrupts the JSON-RPC stream.
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Fail fast with a clear message if configuration is missing/invalid, rather than
    # surfacing the error on the first tool call. Reuse a context already built by the
    # lazy path instead of replacing (and leaking) it.
    try:
        global _context
        with _context_lock:
            if _context is None:
                _context = AppContext.from_env()
            context = _context
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    import atexit

    def _cleanup() -> None:
        # Close the context we actually initialized here, not whatever the
        # mutable global happens to hold at shutdown.
        context.close()

    atexit.register(_cleanup)
    mcp.run()
