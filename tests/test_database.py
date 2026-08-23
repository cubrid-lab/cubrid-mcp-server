"""Unit tests for cubrid_mcp_server.database using a fake pycubrid driver.

These exercise the connection lifecycle, cursor error handling, and streaming
fetch logic without a live CUBRID server by monkeypatching ``pycubrid.connect``.
"""

from __future__ import annotations

import socket
from typing import Any

import pytest

import pycubrid
from cubrid_mcp_server.config import Config
from cubrid_mcp_server.database import (
    Database,
    DatabaseError,
    QueryTimeoutError,
    _is_timeout_error,
)

_TEST_CONFIG = Config(
    host="h",
    port=33000,
    user="u",
    password="",
    database="d",
    readonly=True,
    max_chars=4000,
    max_rows=1000,
)


def _raise(exc: BaseException) -> None:
    """Raise ``exc`` from inside a block.

    Routing the raise through a helper keeps static analyzers from treating the
    statements after a ``with pytest.raises(...)`` guard as unreachable.
    """
    raise exc


class FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]] | None = None) -> None:
        self._rows = list(rows or [])
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False
        self._fetch_offset = 0

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        self.executed.append((sql, params))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._rows)

    def fetchmany(self, size: int) -> list[tuple[Any, ...]]:
        chunk = self._rows[self._fetch_offset : self._fetch_offset + size]
        self._fetch_offset += size
        return chunk

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, rows: list[tuple[Any, ...]] | None = None) -> None:
        self._rows = rows
        self.closed = False
        self.server_version_calls = 0
        self.version_error = False
        self.close_error = False
        self.cursors: list[FakeCursor] = []
        self.rolled_back = False

    def get_server_version(self) -> str:
        self.server_version_calls += 1
        if self.version_error:
            raise RuntimeError("stale connection")
        return "11.0"

    def cursor(self) -> FakeCursor:
        cursor = FakeCursor(self._rows)
        self.cursors.append(cursor)
        return cursor

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        if self.close_error:
            raise RuntimeError("close failed")
        self.closed = True


@pytest.fixture
def patch_connect(monkeypatch: pytest.MonkeyPatch) -> list[FakeConnection]:
    """Return a list that records every FakeConnection handed out by connect()."""
    created: list[FakeConnection] = []

    def _connect(**_kwargs: Any) -> FakeConnection:
        conn = FakeConnection()
        created.append(conn)
        return conn

    monkeypatch.setattr(pycubrid, "connect", _connect)
    return created


def test_connect_creates_and_caches_connection(patch_connect: list[FakeConnection]) -> None:
    db = Database(_TEST_CONFIG)
    first = db.connect()
    second = db.connect()
    assert first is second
    assert len(patch_connect) == 1
    # connect() no longer issues a per-call liveness ping.
    assert first.server_version_calls == 0


def test_query_failure_triggers_lazy_reconnect(patch_connect: list[FakeConnection]) -> None:
    db = Database(_TEST_CONFIG)
    first = db.connect()
    # A failed query discards the connection so the next request reconnects.
    with pytest.raises(DatabaseError, match="query failed"):
        with db.cursor():
            _raise(ValueError("boom"))
    assert first.closed is True
    second = db.connect()
    assert second is not first
    assert len(patch_connect) == 2


def test_lazy_reconnect_swallows_close_error(patch_connect: list[FakeConnection]) -> None:
    db = Database(_TEST_CONFIG)
    first = db.connect()
    first.close_error = True  # close raises during discard; must be swallowed
    with pytest.raises(DatabaseError, match="query failed"):
        with db.cursor():
            _raise(ValueError("boom"))
    second = db.connect()
    assert second is not first
    assert len(patch_connect) == 2


def test_close_clears_connection(patch_connect: list[FakeConnection]) -> None:
    db = Database(_TEST_CONFIG)
    conn = db.connect()
    db.close()
    assert conn.closed is True
    # A subsequent connect creates a fresh connection.
    db.connect()
    assert len(patch_connect) == 2


def test_close_when_no_connection_is_noop(patch_connect: list[FakeConnection]) -> None:
    db = Database(_TEST_CONFIG)
    db.close()  # should not raise
    assert patch_connect == []


def test_cursor_closes_and_wraps_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = FakeConnection()
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    with pytest.raises(DatabaseError, match="query failed"):
        with db.cursor():
            _raise(ValueError("boom"))
    # Cursor is always closed, even on error.
    assert conn.cursors[0].closed is True


def test_exclusive_yields_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = FakeConnection()
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    with db.exclusive() as active:
        assert active is conn


def test_fetch_all_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = FakeConnection(rows=[(1,), (2,)])
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    assert db.fetch_all("SELECT 1", None) == [(1,), (2,)]
    assert conn.cursors[0].executed == [("SELECT 1", ())]


def test_trace_enabled_runs_and_cleans_up(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = FakeConnection(rows=[("Trace Statistics: stub",)])
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    with db.trace_enabled() as cursor:
        cursor.execute("SELECT 1", ())
        cursor.execute("SHOW TRACE", ())
        assert cursor.fetchall() == [("Trace Statistics: stub",)]
    executed = [sql for cur in conn.cursors for sql, _ in cur.executed]
    assert "SET TRACE ON" in executed
    assert "SET TRACE OFF" in executed
    assert conn.rolled_back is True
    # Every cursor opened during the trace lifecycle is closed.
    assert all(cur.closed for cur in conn.cursors)


def test_trace_enabled_swallows_cleanup_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BoomConn(FakeConnection):
        def rollback(self) -> None:
            raise RuntimeError("rollback boom")

    conn = _BoomConn()
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    # Cleanup failures during __exit__ are logged, not raised.
    with db.trace_enabled() as cursor:
        cursor.execute("SELECT 1", ())


def test_fetch_many_truncates_across_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [(i,) for i in range(250)]
    conn = FakeConnection(rows=rows)
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    result, truncated = db.fetch_many("SELECT x", None, max_rows=150)
    assert truncated is True
    assert result == rows[:150]


def test_fetch_many_no_truncation_when_max_rows_none(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [(i,) for i in range(50)]
    conn = FakeConnection(rows=rows)
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    result, truncated = db.fetch_many("SELECT x", None, max_rows=None)
    assert truncated is False
    assert result == rows


# --- query_timeout enforcement (issue #101) ---


class TimeoutCursor(FakeCursor):
    """Cursor whose ``execute`` raises a socket timeout, simulating a slow query."""

    def __init__(self, error: BaseException) -> None:
        super().__init__()
        self._error = error

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        raise self._error


class TimeoutConnection(FakeConnection):
    def __init__(self, error: BaseException) -> None:
        super().__init__()
        self._error = error

    def cursor(self) -> FakeCursor:
        cursor = TimeoutCursor(self._error)
        self.cursors.append(cursor)
        return cursor


def test_connect_passes_query_timeout_as_read_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _connect(**kwargs: Any) -> FakeConnection:
        captured.update(kwargs)
        return FakeConnection()

    monkeypatch.setattr(pycubrid, "connect", _connect)
    config = Config(
        host="h",
        port=33000,
        user="u",
        password="",
        database="d",
        readonly=True,
        max_chars=4000,
        max_rows=1000,
        query_timeout=12.5,
    )
    Database(config).connect()
    assert captured["read_timeout"] == 12.5


def test_is_timeout_error_detects_raw_and_wrapped() -> None:
    assert _is_timeout_error(TimeoutError("slow")) is True
    assert _is_timeout_error(socket.timeout("slow")) is True
    # pycubrid wraps the socket timeout as another error with __cause__ set.
    wrapped = RuntimeError("socket communication failed")
    wrapped.__cause__ = TimeoutError("timed out")
    assert _is_timeout_error(wrapped) is True
    assert _is_timeout_error(RuntimeError("syntax error")) is False
    assert _is_timeout_error(None) is False


def test_cursor_timeout_raises_and_discards_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = TimeoutConnection(TimeoutError("read timed out"))
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    with pytest.raises(QueryTimeoutError, match="query exceeded timeout"):
        db.fetch_all("SELECT SLEEP(999)")
    # The corrupt connection must be dropped so the next call reconnects.
    assert conn.closed is True
    assert db._connection is None


def test_cursor_timeout_detects_wrapped_operational_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrapped = RuntimeError("socket communication failed")
    wrapped.__cause__ = TimeoutError("timed out")
    conn = TimeoutConnection(wrapped)
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    with pytest.raises(QueryTimeoutError):
        db.fetch_all("SELECT SLEEP(999)")
    assert db._connection is None


def test_non_timeout_error_still_wrapped_as_database_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = TimeoutConnection(ValueError("bad syntax"))
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    with pytest.raises(DatabaseError, match="query failed") as excinfo:
        db.fetch_all("SELECT bogus")
    assert not isinstance(excinfo.value, QueryTimeoutError)
    # Lazy recovery (#106): a query error now discards the connection too.
    assert db._connection is None


def test_exclusive_timeout_raises_and_discards_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = FakeConnection()
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    with pytest.raises(QueryTimeoutError):
        with db.exclusive():
            _raise(TimeoutError("read timed out"))
    assert conn.closed is True
    assert db._connection is None


def test_health_check_reports_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = FakeConnection()
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    status = db.health_check()
    assert status == {"ok": True, "server_version": "11.0"}
    # health_check performs the explicit liveness ping.
    assert conn.server_version_calls == 1


def test_health_check_reports_failure_and_discards(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = FakeConnection()
    conn.version_error = True
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    status = db.health_check()
    assert status["ok"] is False
    assert "stale connection" in status["error"]
    # A failed ping discards the connection for lazy recovery.
    assert conn.closed is True
    assert db._connection is None


def test_exclusive_discards_connection_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = FakeConnection()
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    with pytest.raises(ValueError, match="boom"):
        with db.exclusive():
            _raise(ValueError("boom"))
    # Lazy recovery (#106): a non-timeout error drops the connection too.
    assert conn.closed is True
    assert db._connection is None


def test_cursor_close_error_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = FakeConnection(rows=[(1,)])
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)

    def _boom() -> None:
        raise RuntimeError("close failed")

    # fetch_all succeeds even if cursor.close() raises during cleanup.
    original_cursor = conn.cursor

    def _cursor() -> FakeCursor:
        cur = original_cursor()
        cur.close = _boom  # type: ignore[method-assign]
        return cur

    monkeypatch.setattr(conn, "cursor", _cursor)
    assert db.fetch_all("SELECT 1") == [(1,)]


def test_safe_close_cursor_swallows_close_error() -> None:
    class _BadCursor:
        def close(self) -> None:
            raise RuntimeError("close boom")

    # Logged, not raised.
    Database._safe_close_cursor(_BadCursor())
