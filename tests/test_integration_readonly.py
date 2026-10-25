"""Live proof that the default configuration refuses writes through the MCP tools (#451).

Every SQL-accepting tool is called through ``mcp.call_tool`` (the path an MCP client
takes) against the run-owned CUBRID, with the default configuration: no
``CUBRID_MCP_READONLY``, ``CUBRID_MCP_WRITE`` or ``CUBRID_CONNECTIONS``. Each write must
fail with the documented error, and an independent session then shows that the
catalog and the rows are unchanged. One test enables ``CUBRID_MCP_WRITE=1`` and writes
to a uniquely named table that it always drops.

Run with: pytest -m integration
"""

from __future__ import annotations

import asyncio
import importlib
import os
import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

pytestmark = pytest.mark.integration

skipif_no_cubrid = pytest.mark.skipif(
    not all(k in os.environ for k in ("CUBRID_HOST", "CUBRID_USER", "CUBRID_DATABASE")),
    reason="CUBRID env vars not set",
)

# The variables that change the defaults this module proves.
_MODE_VARIABLES = ("CUBRID_MCP_READONLY", "CUBRID_MCP_WRITE", "CUBRID_CONNECTIONS")

_NOT_READ_ONLY = "is not permitted in read-only mode"
_MULTI = "multi-statement SQL is not allowed in read-only mode"
_EXPLAIN_ONLY = "explain_query only accepts SELECT or WITH statements"


def _session() -> Any:
    """Open an independent pycubrid session (not the server's shared one)."""
    import pycubrid

    return pycubrid.connect(
        host=os.environ["CUBRID_HOST"],
        port=int(os.environ.get("CUBRID_PORT", "33000")),
        user=os.environ["CUBRID_USER"],
        password=os.environ.get("CUBRID_PASSWORD", ""),
        database=os.environ["CUBRID_DATABASE"],
        connect_timeout=10,
        read_timeout=30,
    )


def _query(connection: Any, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        rows = [tuple(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
    connection.rollback()
    return rows


def _table_exists(connection: Any, table: str) -> bool:
    rows = _query(connection, "SELECT COUNT(*) FROM db_class WHERE class_name = ?", (table,))
    return bool(rows[0][0])


def _call(tool: str, arguments: dict[str, Any]) -> Any:
    """Call ``tool`` the way an MCP client does, through the registered tool list."""
    from cubrid_mcp_server import server

    return asyncio.run(server.mcp.call_tool(tool, arguments))


def _tool_names() -> set[str]:
    from cubrid_mcp_server import server

    return {tool.name for tool in asyncio.run(server.mcp.list_tools())}


@contextmanager
def _live_server(monkeypatch: pytest.MonkeyPatch, **mode: str) -> Iterator[Any]:
    """Point the server at the live database, with only the given mode variables set.

    The server module is reloaded so ``execute_write`` registration follows the
    environment exactly as at process start, and reloaded again afterwards with the
    original environment. Yields the connection's :class:`Config`.
    """
    from cubrid_mcp_server import server
    from cubrid_mcp_server.config import Config
    from cubrid_mcp_server.database import Database
    from tests.helpers import single_context

    for name in _MODE_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    for name, value in mode.items():
        monkeypatch.setenv(name, value)
    importlib.reload(server)
    config = Config.from_env()
    database = Database(config)
    server._context = single_context(config=config, database=database)
    try:
        yield config
    finally:
        server._context = None
        database.close()
        monkeypatch.undo()
        importlib.reload(server)


@pytest.fixture
def default_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    with _live_server(monkeypatch) as config:
        yield config


@pytest.fixture
def write_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    with _live_server(monkeypatch, CUBRID_MCP_WRITE="1") as config:
        yield config


@pytest.fixture
def target_table() -> Iterator[str]:
    """A uniquely named table with one row, which the rejected writes aim at."""
    table = f"mcp_it_ro_{uuid.uuid4().hex[:12]}"
    connection = _session()
    try:
        cursor = connection.cursor()
        cursor.execute(f"CREATE TABLE {table} (id INT PRIMARY KEY, label VARCHAR(20))")
        cursor.execute(f"INSERT INTO {table} VALUES (1, 'first')")
        cursor.close()
        connection.commit()
        yield table
    finally:
        try:
            cursor = connection.cursor()
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            cursor.close()
            connection.commit()
        finally:
            connection.close()


def _writes(table: str, probe: str) -> list[tuple[str, str, str]]:
    """``(sql, execute_query error, explain_query error)`` for each disallowed write."""
    return [
        (f"CREATE TABLE {probe} (id INT)", "CREATE " + _NOT_READ_ONLY, _EXPLAIN_ONLY),
        (f"INSERT INTO {table} VALUES (2, 'second')", "INSERT " + _NOT_READ_ONLY, _EXPLAIN_ONLY),
        (f"UPDATE {table} SET label = 'changed'", "UPDATE " + _NOT_READ_ONLY, _EXPLAIN_ONLY),
        (f"DELETE FROM {table}", "DELETE " + _NOT_READ_ONLY, _EXPLAIN_ONLY),
        (f"TRUNCATE TABLE {table}", "TRUNCATE " + _NOT_READ_ONLY, _EXPLAIN_ONLY),
        (f"ALTER TABLE {table} ADD COLUMN extra INT", "ALTER " + _NOT_READ_ONLY, _EXPLAIN_ONLY),
        (f"DROP TABLE {table}", "DROP " + _NOT_READ_ONLY, _EXPLAIN_ONLY),
        (f"/* SELECT */ DROP TABLE {table}", "DROP " + _NOT_READ_ONLY, _EXPLAIN_ONLY),
        (f"SELECT 1; DROP TABLE {table}", _MULTI, _MULTI),
        (f"SELECT 1; CREATE TABLE {probe} (id INT)", _MULTI, _MULTI),
        (f"SELECT 1;\nINSERT INTO {table} VALUES (3, 'third');", _MULTI, _MULTI),
        (f"SELECT 1 -- note\n; DELETE FROM {table}", _MULTI, _MULTI),
    ]


@skipif_no_cubrid
def test_default_mode_rejects_writes_through_every_sql_tool(
    target_table: str, default_server: Any
) -> None:
    """CREATE, INSERT, DROP, multi-statement and other writes change nothing (#451)."""
    from fastmcp.exceptions import NotFoundError, ToolError

    config = default_server
    assert config.readonly is True
    assert config.write_enabled is False
    # The write tool is not offered at all in the default configuration.
    assert "execute_write" not in _tool_names()

    probe = f"mcp_it_ro_probe_{uuid.uuid4().hex[:12]}"
    observer = _session()
    try:
        assert not _table_exists(observer, probe)
        for sql, query_error, explain_error in _writes(target_table, probe):
            with pytest.raises(ToolError, match=re.escape(f"'execute_query': {query_error}")):
                _call("execute_query", {"sql": sql})
            with pytest.raises(ToolError, match=re.escape(f"'explain_query': {explain_error}")):
                _call("explain_query", {"sql": sql})
            with pytest.raises(NotFoundError, match="execute_write"):
                _call("execute_write", {"sql": sql})
        # table_row_counts quotes the names it is given; a name carrying SQL is an
        # unknown table, never a statement.
        injected = f'{target_table}"; DROP TABLE {target_table}; --'
        counts = _call("table_row_counts", {"table_names": [injected]}).structured_content
        assert counts["tables"] == [
            {"table": injected, "row_count": None, "error": "unknown table"}
        ]

        # Nothing was created or changed, as another session sees it.
        assert not _table_exists(observer, probe)
        assert _table_exists(observer, target_table)
        assert _query(observer, f"SELECT * FROM {target_table} ORDER BY id") == [(1, "first")]
        columns = _query(
            observer,
            "SELECT attr_name FROM db_attribute WHERE class_name = ? ORDER BY def_order",
            (target_table,),
        )
        assert columns == [("id",), ("label",)]
    finally:
        observer.close()
    # Reads keep working on the same shared session.
    result = _call("execute_query", {"sql": f"SELECT label FROM {target_table}"})
    assert result.structured_content["rows"] == [["first"]]


@skipif_no_cubrid
def test_write_mode_writes_only_dml_to_its_own_table(target_table: str, write_server: Any) -> None:
    """With CUBRID_MCP_WRITE=1, execute_write commits DML and still refuses DDL (#451).

    ``target_table`` is uniquely named for this run and always dropped afterwards.
    """
    from fastmcp.exceptions import ToolError

    config = write_server
    assert config.write_enabled is True
    assert config.readonly is True
    assert "execute_write" in _tool_names()

    observer = _session()
    try:
        result = _call("execute_write", {"sql": f"INSERT INTO {target_table} VALUES (2, 'second')"})
        assert result.structured_content == {"affected_rows": 1}
        rows = _query(observer, f"SELECT * FROM {target_table} ORDER BY id")
        assert rows == [(1, "first"), (2, "second")]

        for sql, error in (
            (f"DROP TABLE {target_table}", "DROP is not permitted in write mode"),
            (
                f"INSERT INTO {target_table} VALUES (3, 'third'); DROP TABLE {target_table}",
                "multi-statement SQL is not allowed in write mode",
            ),
        ):
            with pytest.raises(ToolError, match=re.escape(f"'execute_write': {error}")):
                _call("execute_write", {"sql": sql})
        # execute_query stays read-only in write mode.
        with pytest.raises(ToolError, match=re.escape("'execute_query': INSERT " + _NOT_READ_ONLY)):
            _call("execute_query", {"sql": f"INSERT INTO {target_table} VALUES (4, 'fourth')"})

        assert _table_exists(observer, target_table)
        rows = _query(observer, f"SELECT * FROM {target_table} ORDER BY id")
        assert rows == [(1, "first"), (2, "second")]
    finally:
        observer.close()
