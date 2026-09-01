"""Unit tests for opt-in write mode + transaction management (issue #123).

Covers the security invariant (read-only stays the default; the write path is
unreachable unless explicitly enabled), the DML-only write whitelist, the
atomic-transaction semantics of ``Database.execute_write`` (commit on success,
rollback on failure, connection discard when rollback itself fails), and the
conditional registration of the ``execute_write`` MCP tool.
"""

from __future__ import annotations

import asyncio
import importlib
import socket
from dataclasses import replace
from typing import Any

import pytest

import pycubrid
from cubrid_mcp_server import server
from cubrid_mcp_server.config import Config, ConfigError, ConnectionRegistry, DEFAULT_CONNECTION
from cubrid_mcp_server.context import AppContext
from cubrid_mcp_server.database import Database, DatabaseError, QueryTimeoutError
from cubrid_mcp_server.safety import UnsafeSQLError, ensure_read_only, ensure_write_allowed

_BASE = Config(
    host="h",
    port=33000,
    user="u",
    password="",
    database="d",
    readonly=True,
    max_chars=4000,
    max_rows=1000,
)


def _env(**extra: str) -> dict[str, str]:
    base = {
        "CUBRID_HOST": "h",
        "CUBRID_USER": "u",
        "CUBRID_PASSWORD": "p",
        "CUBRID_DATABASE": "d",
    }
    base.update(extra)
    return base


# --------------------------------------------------------------------------- #
# Config parsing
# --------------------------------------------------------------------------- #


def test_write_disabled_by_default() -> None:
    assert Config.from_env(_env()).write_enabled is False


@pytest.mark.parametrize("value", ["1", "true", "on", "yes", "TRUE"])
def test_write_enabled_via_env(value: str) -> None:
    assert Config.from_env(_env(CUBRID_MCP_WRITE=value)).write_enabled is True


def test_write_invalid_value_raises() -> None:
    with pytest.raises(ConfigError):
        Config.from_env(_env(CUBRID_MCP_WRITE="maybe"))


# --------------------------------------------------------------------------- #
# safety.ensure_write_allowed — DML whitelist
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET a = 1 WHERE id = 2",
        "DELETE FROM t WHERE id = 1",
        "  insert into t values (1)  ",
        "/* leading comment */ UPDATE t SET a = 1",
    ],
)
def test_write_allows_single_dml(sql: str) -> None:
    ensure_write_allowed(sql)  # must not raise


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "WITH c AS (SELECT 1) SELECT * FROM c",
        "EXPLAIN SELECT 1",
        "SHOW TABLES",
        "CREATE TABLE t (a int)",
        "ALTER TABLE t ADD b int",
        "DROP TABLE t",
        "TRUNCATE TABLE t",
        "REPLACE INTO t VALUES (1)",
        "MERGE INTO t USING s ON (t.id = s.id) WHEN MATCHED THEN UPDATE SET t.a = s.a",
        "CALL some_proc()",
        "COMMIT",
        "ROLLBACK",
        "GRANT SELECT ON t TO u",
    ],
)
def test_write_blocks_non_dml(sql: str) -> None:
    with pytest.raises(UnsafeSQLError):
        ensure_write_allowed(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "   ",
        "-- just a comment",
        "/* only a block comment */",
        "INSERT INTO t VALUES (1); DELETE FROM t",
    ],
)
def test_write_blocks_empty_and_multi_statement(sql: str) -> None:
    with pytest.raises(UnsafeSQLError):
        ensure_write_allowed(sql)


def test_read_only_path_unchanged_still_blocks_dml() -> None:
    # The default security path is untouched: DML is still rejected there.
    with pytest.raises(UnsafeSQLError):
        ensure_read_only("INSERT INTO t VALUES (1)")


def test_write_path_blocks_reads() -> None:
    with pytest.raises(UnsafeSQLError):
        ensure_write_allowed("SELECT * FROM t")


# --------------------------------------------------------------------------- #
# Database.execute_write — atomic transaction semantics
# --------------------------------------------------------------------------- #


class _WCursor:
    def __init__(self, rowcount: int, execute_error: BaseException | None) -> None:
        self.rowcount = rowcount
        self._execute_error = execute_error
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        self.executed.append((sql, params))
        if self._execute_error is not None:
            raise self._execute_error

    def close(self) -> None:
        self.closed = True


class _WConnection:
    def __init__(
        self,
        *,
        rowcount: int = 1,
        execute_error: BaseException | None = None,
        commit_error: BaseException | None = None,
        rollback_error: BaseException | None = None,
    ) -> None:
        self._rowcount = rowcount
        self._execute_error = execute_error
        self._commit_error = commit_error
        self._rollback_error = rollback_error
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.cursors: list[_WCursor] = []

    def cursor(self) -> _WCursor:
        cur = _WCursor(self._rowcount, self._execute_error)
        self.cursors.append(cur)
        return cur

    def commit(self) -> None:
        if self._commit_error is not None:
            raise self._commit_error
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True
        if self._rollback_error is not None:
            raise self._rollback_error

    def close(self) -> None:
        self.closed = True


def _db_with(
    monkeypatch: pytest.MonkeyPatch, **conn_kwargs: Any
) -> tuple[Database, list[_WConnection]]:
    conns: list[_WConnection] = []

    def _connect(**_kwargs: Any) -> _WConnection:
        conn = _WConnection(**conn_kwargs)
        conns.append(conn)
        return conn

    monkeypatch.setattr(pycubrid, "connect", _connect)
    return Database(_BASE), conns


def test_execute_write_commits_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    db, conns = _db_with(monkeypatch, rowcount=5)
    assert db.execute_write("INSERT INTO t VALUES (1)") == 5
    assert conns[0].committed is True
    assert conns[0].rolled_back is False
    assert conns[0].cursors[0].closed is True


def test_execute_write_rolls_back_on_execute_error(monkeypatch: pytest.MonkeyPatch) -> None:
    db, conns = _db_with(monkeypatch, execute_error=ValueError("boom"))
    with pytest.raises(DatabaseError, match="write failed"):
        db.execute_write("INSERT INTO t VALUES (1)")
    assert conns[0].rolled_back is True
    assert conns[0].committed is False


def test_execute_write_rolls_back_on_commit_error(monkeypatch: pytest.MonkeyPatch) -> None:
    db, conns = _db_with(monkeypatch, commit_error=RuntimeError("commit fail"))
    with pytest.raises(DatabaseError, match="write failed"):
        db.execute_write("UPDATE t SET a = 1")
    assert conns[0].rolled_back is True
    assert conns[0].committed is False


def test_execute_write_discards_connection_on_rollback_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, conns = _db_with(
        monkeypatch,
        execute_error=ValueError("boom"),
        rollback_error=RuntimeError("rollback fail"),
    )
    with pytest.raises(DatabaseError):
        db.execute_write("DELETE FROM t WHERE id = 1")
    # Rollback failed, so the poisoned connection is discarded (closed)...
    assert conns[0].closed is True
    # ...and the next call transparently reconnects.
    db.connect()
    assert len(conns) == 2


def test_execute_write_timeout_discards_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    db, conns = _db_with(monkeypatch, execute_error=socket.timeout())
    with pytest.raises(QueryTimeoutError):
        db.execute_write("INSERT INTO t VALUES (1)")
    assert conns[0].closed is True


# --------------------------------------------------------------------------- #
# server.execute_write tool behaviour
# --------------------------------------------------------------------------- #


class _FakeWriteDB:
    def __init__(self, affected: int = 1) -> None:
        self.affected = affected
        self.writes: list[str] = []

    def execute_write(self, sql: str, params: tuple[Any, ...] | None = None) -> int:
        self.writes.append(sql)
        return self.affected

    def fetch_many(
        self,
        sql: str,
        params: tuple[Any, ...] | None = None,
        max_rows: int | None = None,
    ) -> tuple[list[tuple[Any, ...]], bool]:
        return [], False


def _inject(monkeypatch: pytest.MonkeyPatch, db: _FakeWriteDB, **cfg: Any) -> None:
    config = replace(_BASE, **cfg)
    monkeypatch.setattr(server, "_context", AppContext.single(config=config, database=db))


def test_execute_write_refuses_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeWriteDB()
    _inject(monkeypatch, db)  # write_enabled defaults False
    with pytest.raises(ValueError, match="write mode is disabled"):
        server.execute_write("INSERT INTO t VALUES (1)")
    assert db.writes == []


def test_execute_write_runs_dml_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeWriteDB(affected=3)
    _inject(monkeypatch, db, write_enabled=True)
    assert server.execute_write("INSERT INTO t VALUES (1)") == {"affected_rows": 3}
    assert db.writes == ["INSERT INTO t VALUES (1)"]


def test_execute_write_blocks_non_dml_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeWriteDB()
    _inject(monkeypatch, db, write_enabled=True)
    with pytest.raises(UnsafeSQLError):
        server.execute_write("SELECT * FROM t")
    assert db.writes == []


def test_execute_write_rejects_over_length(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeWriteDB()
    _inject(monkeypatch, db, write_enabled=True, max_sql_length=10)
    with pytest.raises(ValueError, match="exceeds maximum length"):
        server.execute_write("INSERT INTO t VALUES (1234567890)")
    assert db.writes == []


def test_execute_query_stays_read_only_in_write_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    # Enabling write mode must NOT open a write path through execute_query.
    db = _FakeWriteDB()
    _inject(monkeypatch, db, write_enabled=True, readonly=True)
    with pytest.raises(UnsafeSQLError):
        server.execute_query("INSERT INTO t VALUES (1)")


# --------------------------------------------------------------------------- #
# Conditional tool registration (security invariant)
# --------------------------------------------------------------------------- #


def _tool_names(module: Any) -> set[str]:
    return {tool.name for tool in asyncio.run(module.mcp.list_tools())}


def test_write_tool_absent_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CUBRID_MCP_WRITE", raising=False)
    module = importlib.reload(server)
    try:
        names = _tool_names(module)
        assert "execute_write" not in names
        assert len(names) == 11
    finally:
        monkeypatch.delenv("CUBRID_MCP_WRITE", raising=False)
        importlib.reload(server)


def test_write_tool_registered_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CUBRID_MCP_WRITE", "1")
    module = importlib.reload(server)
    try:
        names = _tool_names(module)
        assert "execute_write" in names
        assert len(names) == 12
    finally:
        monkeypatch.delenv("CUBRID_MCP_WRITE", raising=False)
        importlib.reload(server)


def test_write_tool_absent_on_invalid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # An invalid CUBRID_MCP_WRITE must not raise at import time (which would
    # bypass main()'s clean ConfigError handling); it fails closed instead.
    monkeypatch.setenv("CUBRID_MCP_WRITE", "maybe")
    module = importlib.reload(server)
    try:
        names = _tool_names(module)
        assert "execute_write" not in names
        assert len(names) == 11
    finally:
        monkeypatch.delenv("CUBRID_MCP_WRITE", raising=False)
        importlib.reload(server)


# --------------------------------------------------------------------------- #
# Multi-connection write routing + per-connection enablement (#136, #137)
# --------------------------------------------------------------------------- #


def _multi_inject(
    monkeypatch: pytest.MonkeyPatch,
    *,
    default_cfg: Config,
    default_db: _FakeWriteDB,
    named_cfg: Config,
    named_db: _FakeWriteDB,
    named: str = "reporting",
) -> None:
    registry = ConnectionRegistry(
        configs={DEFAULT_CONNECTION: default_cfg, named: named_cfg},
        default_name=DEFAULT_CONNECTION,
    )
    ctx = AppContext(
        registry=registry,
        databases={DEFAULT_CONNECTION: default_db, named: named_db},  # type: ignore[dict-item]
    )
    monkeypatch.setattr(server, "_context", ctx)


def test_execute_write_routes_to_selected_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    # #136: execute_write must honour the per-call ``connection`` argument
    # instead of always using the default connection.
    default_db = _FakeWriteDB(affected=1)
    named_db = _FakeWriteDB(affected=7)
    _multi_inject(
        monkeypatch,
        default_cfg=replace(_BASE, write_enabled=True),
        default_db=default_db,
        named_cfg=replace(_BASE, write_enabled=True),
        named_db=named_db,
    )
    result = server.execute_write("INSERT INTO t VALUES (1)", connection="reporting")
    assert result == {"affected_rows": 7}
    assert named_db.writes == ["INSERT INTO t VALUES (1)"]
    assert default_db.writes == []


def test_execute_write_refuses_when_target_connection_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # #137: write-enablement is enforced per connection. The default may enable
    # writes while a named connection keeps them off (and vice versa).
    default_db = _FakeWriteDB()
    named_db = _FakeWriteDB()
    _multi_inject(
        monkeypatch,
        default_cfg=replace(_BASE, write_enabled=True),
        default_db=default_db,
        named_cfg=replace(_BASE, write_enabled=False),
        named_db=named_db,
    )
    with pytest.raises(ValueError, match="write mode is disabled"):
        server.execute_write("INSERT INTO t VALUES (1)", connection="reporting")
    assert named_db.writes == []
    # The default connection, which does enable writes, still works.
    assert server.execute_write("INSERT INTO t VALUES (1)") == {"affected_rows": 1}
    assert default_db.writes == ["INSERT INTO t VALUES (1)"]


def test_write_mode_requested_true_for_named_connection_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # #137: the write tool must be registered when a *named* connection enables
    # writes, even if the default connection does not.
    monkeypatch.delenv("CUBRID_MCP_WRITE", raising=False)
    monkeypatch.setenv("CUBRID_CONNECTIONS", "reporting")
    monkeypatch.setenv("CUBRID_REPORTING_MCP_WRITE", "1")
    assert server._write_mode_requested() is True


def test_write_mode_requested_false_when_none_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CUBRID_MCP_WRITE", raising=False)
    monkeypatch.setenv("CUBRID_CONNECTIONS", "reporting")
    monkeypatch.delenv("CUBRID_REPORTING_MCP_WRITE", raising=False)
    assert server._write_mode_requested() is False


def test_write_mode_requested_fails_closed_on_invalid_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An invalid named write value must not raise at import time; it fails closed.
    monkeypatch.delenv("CUBRID_MCP_WRITE", raising=False)
    monkeypatch.setenv("CUBRID_CONNECTIONS", "reporting")
    monkeypatch.setenv("CUBRID_REPORTING_MCP_WRITE", "maybe")
    assert server._write_mode_requested() is False
    # An invalid CUBRID_MCP_WRITE must not raise at import time (which would
    # bypass main()'s clean ConfigError handling); it fails closed instead.
    monkeypatch.setenv("CUBRID_MCP_WRITE", "maybe")
    module = importlib.reload(server)
    try:
        names = _tool_names(module)
        assert "execute_write" not in names
        assert len(names) == 11
    finally:
        monkeypatch.delenv("CUBRID_MCP_WRITE", raising=False)
        importlib.reload(server)
