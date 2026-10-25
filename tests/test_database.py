"""Unit tests for cubrid_mcp_server.database using a fake pycubrid driver.

These exercise the connection lifecycle, cursor error handling, and streaming
fetch logic without a live CUBRID server by monkeypatching ``pycubrid.connect``.
"""

from __future__ import annotations

import socket
from dataclasses import replace
from typing import Any

import pytest

import pycubrid
from cubrid_mcp_server.config import Config
from cubrid_mcp_server.database import (
    Database,
    DatabaseError,
    NoResultSetError,
    QueryTimeoutError,
    _is_timeout_error,
    sanitize_error,
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
        # Non-None like pycubrid after a statement that returns a result set.
        self.description: tuple[Any, ...] | None = (("x",),)
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False
        self._fetch_offset = 0
        self.fetchmany_calls = 0

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        self.executed.append((sql, params))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._rows)

    def fetchmany(self, size: int) -> list[tuple[Any, ...]]:
        self.fetchmany_calls += 1
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
    with pytest.raises(DatabaseError) as excinfo:
        with db.cursor():
            _raise(ValueError("secret schema detail public.users.ssn"))
    # The raw message is never surfaced; only the error category is.
    message = str(excinfo.value)
    assert message == "query failed: ValueError"
    assert "secret schema detail" not in message
    # Cursor is always closed, even on error.
    assert conn.cursors[0].closed is True


def test_sanitize_error_returns_class_name_only() -> None:
    assert sanitize_error(ValueError("host=db.internal password=hunter2")) == "ValueError"


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


@pytest.mark.parametrize(("overrides", "expected"), [({}, 10.0), ({"connect_timeout": 2.5}, 2.5)])
def test_connect_passes_configured_connect_timeout(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, Any], expected: float
) -> None:
    captured: dict[str, Any] = {}

    def _connect(**kwargs: Any) -> FakeConnection:
        captured.update(kwargs)
        return FakeConnection()

    monkeypatch.setattr(pycubrid, "connect", _connect)
    Database(replace(_TEST_CONFIG, **overrides)).connect()
    assert captured["connect_timeout"] == expected


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
    assert status["error"] == "RuntimeError"
    # A failed ping discards the connection for lazy recovery.
    assert conn.closed is True
    assert db._connection is None


def test_exclusive_discards_connection_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = FakeConnection()
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    with pytest.raises(DatabaseError, match="query failed: ValueError") as info:
        with db.exclusive():
            _raise(ValueError("boom"))
    assert "boom" not in str(info.value)
    # Lazy recovery (#106): a non-timeout error drops the connection too.
    assert conn.closed is True
    assert db._connection is None


def test_exclusive_database_error_passes_through_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = FakeConnection()
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    original = DatabaseError("x")
    with pytest.raises(DatabaseError) as info:
        with db.exclusive():
            _raise(original)
    # Already-sanitized DatabaseErrors are re-raised as the same instance.
    assert info.value is original
    assert str(info.value) == "x"
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


def test_cursor_creation_failure_is_sanitized_and_discards(
    patch_connect: list[FakeConnection], monkeypatch: pytest.MonkeyPatch
) -> None:
    # #180: a failing connection.cursor() must take the same sanitize + discard
    # recovery path as a failed query instead of escaping raw.
    db = Database(_TEST_CONFIG)
    first = db.connect()
    monkeypatch.setattr(
        first, "cursor", lambda: _raise(RuntimeError("host=db.internal closed connection"))
    )
    with pytest.raises(DatabaseError) as excinfo:
        db.fetch_all("SELECT 1")
    assert str(excinfo.value) == "query failed: RuntimeError"
    assert first.closed is True
    # The next call reconnects and succeeds.
    assert db.fetch_all("SELECT 1") == []
    assert len(patch_connect) == 2


def test_cursor_creation_timeout_raises_timeout_error(
    patch_connect: list[FakeConnection], monkeypatch: pytest.MonkeyPatch
) -> None:
    db = Database(_TEST_CONFIG)
    first = db.connect()
    monkeypatch.setattr(first, "cursor", lambda: _raise(socket.timeout()))
    with pytest.raises(QueryTimeoutError):
        db.fetch_all("SELECT 1")
    assert first.closed is True


class _SerialProbeConnection(FakeConnection):
    """Fake connection whose ``db_serial`` exposes only ``column``."""

    def __init__(self, column: str) -> None:
        super().__init__()
        self.column = column

    def cursor(self) -> FakeCursor:
        column = self.column
        cursor = super().cursor()
        original_execute = cursor.execute

        def _execute(sql: str, params: tuple[Any, ...] = ()) -> None:
            original_execute(sql, params)
            if "db_serial" in sql and f'"{column}"' not in sql:
                # What CUBRID 10.2, 11.2 and 11.4 raise for the other spelling.
                raise pycubrid.ProgrammingError("Semantic: Attribute was not found.")

        cursor.execute = _execute  # type: ignore[method-assign]
        return cursor


@pytest.mark.parametrize("reset", ["discard", "close"])
def test_serial_attribute_column_reprobed_after_reconnect(
    monkeypatch: pytest.MonkeyPatch, reset: str
) -> None:
    # #181: first connection reaches 11.2 (att_name); after the connection is
    # dropped the broker fails over to 11.4 (attr_name) and must be re-probed.
    backend = {"column": "att_name"}
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: _SerialProbeConnection(backend["column"]))
    db = Database(_TEST_CONFIG)
    assert db.serial_attribute_column() == "att_name"
    assert db.serial_attribute_column() == "att_name"  # cached while connected
    if reset == "discard":
        db._discard_connection()
    else:
        db.close()
    backend["column"] = "attr_name"
    assert db.serial_attribute_column() == "attr_name"


def test_serial_attribute_column_reset_by_failed_query(monkeypatch: pytest.MonkeyPatch) -> None:
    # A failed query discards the connection through the lazy-recovery path,
    # which must also drop the cached probe result.
    backend = {"column": "att_name"}
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: _SerialProbeConnection(backend["column"]))
    db = Database(_TEST_CONFIG)
    assert db.serial_attribute_column() == "att_name"
    with pytest.raises(DatabaseError):
        with db.cursor():
            _raise(ConnectionResetError("broker restarted"))
    backend["column"] = "attr_name"
    assert db.serial_attribute_column() == "attr_name"


class _SerialFaultConnection(FakeConnection):
    """Fake connection whose ``db_serial`` probes raise the queued errors, in order.

    ``None`` in the queue lets that probe succeed; every probe is recorded.
    """

    def __init__(self, faults: list[BaseException | None], probes: list[tuple[int, str]]) -> None:
        super().__init__()
        self.faults = faults
        self.probes = probes

    def cursor(self) -> FakeCursor:
        cursor = super().cursor()
        original_execute = cursor.execute

        def _execute(sql: str, params: tuple[Any, ...] = ()) -> None:
            original_execute(sql, params)
            if "db_serial" in sql:
                self.probes.append((id(self), sql.split('"')[1]))
                fault = self.faults.pop(0) if self.faults else None
                if fault is not None:
                    raise fault

        cursor.execute = _execute  # type: ignore[method-assign]
        return cursor


def _serial_db(
    monkeypatch: pytest.MonkeyPatch, faults: list[BaseException | None]
) -> tuple[Database, list[_SerialFaultConnection], list[tuple[int, str]]]:
    created: list[_SerialFaultConnection] = []
    probes: list[tuple[int, str]] = []

    def _connect(**_k: Any) -> _SerialFaultConnection:
        created.append(_SerialFaultConnection(faults, probes))
        return created[-1]

    monkeypatch.setattr(pycubrid, "connect", _connect)
    return Database(_TEST_CONFIG), created, probes


def test_serial_probe_timeout_is_not_a_missing_column(monkeypatch: pytest.MonkeyPatch) -> None:
    # #351: a timeout says nothing about the catalog; it must surface as itself,
    # without probing the other spelling or caching anything.
    db, created, probes = _serial_db(monkeypatch, [socket.timeout("timed out")])
    with pytest.raises(QueryTimeoutError) as excinfo:
        db.serial_attribute_column()
    assert _is_timeout_error(excinfo.value)
    assert [column for _, column in probes] == ["att_name"]
    assert db._serial_attribute_column is None
    assert created[0].closed is True  # the timed-out connection was discarded


@pytest.mark.parametrize(
    "fault",
    [ConnectionResetError("broker restarted"), pycubrid.OperationalError("communication error")],
)
def test_serial_probe_transport_failure_is_preserved(
    monkeypatch: pytest.MonkeyPatch, fault: BaseException
) -> None:
    db, _created, probes = _serial_db(monkeypatch, [fault, fault])
    with pytest.raises(DatabaseError) as excinfo:
        db.serial_attribute_column()
    assert str(excinfo.value) == f"query failed: {type(fault).__name__}"
    assert excinfo.value.__cause__ is fault
    assert [column for _, column in probes] == ["att_name"]
    assert db._serial_attribute_column is None


def test_serial_probe_falls_back_only_on_a_server_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rejection = pycubrid.ProgrammingError("Semantic: Attribute was not found.")
    db, created, probes = _serial_db(monkeypatch, [rejection, None])
    assert db.serial_attribute_column() == "attr_name"
    assert db.serial_attribute_column() == "attr_name"  # cached for this connection
    assert len(created) == 1 and created[0].closed is False
    assert probes == [(id(created[0]), "att_name"), (id(created[0]), "attr_name")]


def test_serial_probe_with_both_spellings_rejected_names_neither(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rejection = pycubrid.ProgrammingError("Semantic: Attribute was not found.")
    db, _created, probes = _serial_db(monkeypatch, [rejection, rejection])
    with pytest.raises(DatabaseError, match="neither att_name nor attr_name"):
        db.serial_attribute_column()
    assert len(probes) == 2


@pytest.mark.parametrize("first", [None, "rejected"], ids=["answered", "rejected"])
def test_serial_probe_answer_is_not_kept_when_cleanup_drops_the_connection(
    monkeypatch: pytest.MonkeyPatch, first: str | None
) -> None:
    # #351: the probe's read-transaction rollback fails, which discards the
    # connection. Its answer must not be cached for, or reused on, the next one.
    rejection = pycubrid.ProgrammingError("Semantic: Attribute was not found.")
    faults: list[BaseException | None] = [rejection if first else None]
    db, created, probes = _serial_db(monkeypatch, faults)
    first_conn = db.connect()
    first_conn.rollback = lambda: _raise(RuntimeError("rollback failed"))  # type: ignore[method-assign]

    with pytest.raises(DatabaseError, match="connection was reset"):
        db.serial_attribute_column()
    assert db._connection is None
    assert db._serial_attribute_column is None
    assert probes == [(id(first_conn), "att_name")]  # no probe on another connection

    faults.extend([None])
    assert db.serial_attribute_column() == "att_name"
    assert db.serial_attribute_column() == "att_name"
    second = created[-1]
    assert second is not first_conn and db._connection is second
    assert probes == [(id(first_conn), "att_name"), (id(second), "att_name")]


# --- read transactions end after every fetch (#234) ---


class CountingConnection(FakeConnection):
    """Fake connection that counts rollbacks/commits and can fail on demand."""

    def __init__(
        self,
        rows: list[tuple[Any, ...]] | None = None,
        execute_error: BaseException | None = None,
        rollback_error: BaseException | None = None,
        fetch_error: BaseException | None = None,
        cursor_error: BaseException | None = None,
        no_result_set: bool = False,
    ) -> None:
        super().__init__(rows)
        self._no_result_set = no_result_set
        self.rollbacks = 0
        self.lock_owned_at_rollback: list[bool] = []
        self.cursors_closed_at_rollback: list[bool] = []
        self.lock_probe: Any = None
        self._fetch_error = fetch_error
        self._cursor_error = cursor_error
        self.commits = 0
        self._execute_error = execute_error
        self._rollback_error = rollback_error

    def cursor(self) -> FakeCursor:
        if self._cursor_error is not None:
            raise self._cursor_error
        cursor = super().cursor()
        cursor.rowcount = 1  # type: ignore[attr-defined]
        if self._no_result_set:
            cursor.description = None
        fetch_error = self._fetch_error
        if fetch_error is not None:

            def _fetchmany(size: int) -> list[tuple[Any, ...]]:
                raise fetch_error

            cursor.fetchmany = _fetchmany  # type: ignore[method-assign]
        error = self._execute_error
        if error is not None:

            def _execute(sql: str, params: tuple[Any, ...] = ()) -> None:
                raise error

            cursor.execute = _execute  # type: ignore[method-assign]
        return cursor

    def rollback(self) -> None:
        self.rollbacks += 1
        # Every rollback must happen under the Database lock.
        assert self.lock_probe is not None and self.lock_probe()
        self.lock_owned_at_rollback.append(True)
        self.cursors_closed_at_rollback.append(all(c.closed for c in self.cursors))
        if self._rollback_error is not None:
            raise self._rollback_error

    def commit(self) -> None:
        self.commits += 1


def _counting_db(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> tuple[Database, list[Any]]:
    created: list[CountingConnection] = []

    def _connect(**_k: Any) -> CountingConnection:
        conn = CountingConnection(**kwargs)
        created.append(conn)
        return conn

    monkeypatch.setattr(pycubrid, "connect", _connect)
    db = Database(_TEST_CONFIG)
    _orig = _connect

    def _connect_probed(**k: Any) -> CountingConnection:
        conn = _orig(**k)
        conn.lock_probe = db._lock._is_owned  # type: ignore[attr-defined]
        return conn

    monkeypatch.setattr(pycubrid, "connect", _connect_probed)
    return db, created


def test_fetch_all_rolls_back_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    db, created = _counting_db(monkeypatch, rows=[(1,), (2,)])
    assert db.fetch_all("SELECT x FROM t") == [(1,), (2,)]
    conn = created[0]
    assert conn.rollbacks == 1
    assert conn.commits == 0
    assert conn.cursors_closed_at_rollback == [True]
    # The cursor is closed and the connection is kept for the next call.
    assert conn.cursors[0].closed is True
    assert db._connection is conn


@pytest.mark.parametrize(
    ("row_count", "max_rows", "expected_truncated"),
    [
        (250, 150, True),  # truncated early return mid-batch
        (250, 200, True),  # truncated exactly at a batch boundary
        (50, None, False),  # unbounded
        (50, 50, False),  # exactly max_rows, not truncated
        (0, 10, False),  # empty result
    ],
)
def test_fetch_many_rolls_back_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
    row_count: int,
    max_rows: int | None,
    expected_truncated: bool,
) -> None:
    rows = [(i,) for i in range(row_count)]
    db, created = _counting_db(monkeypatch, rows=rows)
    result, truncated = db.fetch_many("SELECT x FROM t", None, max_rows)
    assert truncated is expected_truncated
    assert result == rows[: max_rows if max_rows is not None else row_count]
    conn = created[0]
    assert conn.rollbacks == 1
    assert conn.cursors_closed_at_rollback == [True]
    assert conn.cursors[0].closed is True
    assert db._connection is conn


@pytest.mark.parametrize(
    ("row_count", "max_rows", "expected_calls"),
    [(250, 150, 2), (250, 200, 3), (50, None, 2), (0, 10, 1)],
)
def test_fetch_many_stops_fetching_once_truncated(
    monkeypatch: pytest.MonkeyPatch, row_count: int, max_rows: int | None, expected_calls: int
) -> None:
    db, created = _counting_db(monkeypatch, rows=[(i,) for i in range(row_count)])
    db.fetch_many("SELECT x FROM t", None, max_rows)
    assert created[0].cursors[0].fetchmany_calls == expected_calls


def test_each_read_ends_its_own_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    db, created = _counting_db(monkeypatch, rows=[(1,)])
    db.fetch_all("SELECT 1")
    db.fetch_many("SELECT 1", None, 10)
    db.fetch_all("SELECT 1")
    assert len(created) == 1
    assert created[0].rollbacks == 3


@pytest.mark.parametrize("method", ["fetch_all", "fetch_many"])
def test_failed_read_rollback_discards_connection(
    monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    db, created = _counting_db(monkeypatch, rows=[(1,)], rollback_error=RuntimeError("gone"))
    # The rows were collected, so the read still succeeds...
    assert getattr(db, method)("SELECT 1") in ([(1,)], ([(1,)], False))
    first = created[0]
    assert first.rollbacks == 1
    # ...but a connection with unknown transaction state is dropped.
    assert first.closed is True
    assert db._connection is None
    db.connect()
    assert len(created) == 2


@pytest.mark.parametrize(
    "error",
    [
        pycubrid.ProgrammingError("Semantic: unknown class t", code=-494, errno=-494),
        pycubrid.IntegrityError("unique constraint", code=-670, errno=-670),
        pycubrid.DataError("type conversion", code=-8, errno=-8),
    ],
)
def test_server_sql_error_rolls_back_and_keeps_connection(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    db, created = _counting_db(monkeypatch, execute_error=error)
    with pytest.raises(DatabaseError) as excinfo:
        db.fetch_all("SELECT bogus FROM t")
    assert str(excinfo.value) == f"query failed: {type(error).__name__}"
    assert not isinstance(excinfo.value, QueryTimeoutError)
    conn = created[0]
    assert conn.rollbacks == 1
    assert conn.closed is False
    assert db._connection is conn
    assert conn.cursors[0].closed is True
    # The next call reuses the same session.
    assert db.connect() is conn
    assert len(created) == 1


def test_server_sql_error_with_failed_rollback_discards(monkeypatch: pytest.MonkeyPatch) -> None:
    db, created = _counting_db(
        monkeypatch,
        execute_error=pycubrid.ProgrammingError("syntax error", code=-493, errno=-493),
        rollback_error=OSError("connection reset"),
    )
    with pytest.raises(DatabaseError, match="query failed: ProgrammingError"):
        db.fetch_many("SELEC 1", None, 10)
    assert created[0].rollbacks == 1
    assert created[0].closed is True
    assert db._connection is None


@pytest.mark.parametrize(
    "error",
    [
        pycubrid.OperationalError("Communication error", code=-4, errno=-4),
        pycubrid.InterfaceError("connection is closed"),
        pycubrid.InternalError("internal error", code=-2, errno=-2),
        pycubrid.DatabaseError("unmapped CAS error", code=-1, errno=-1),
        ConnectionResetError("broker restarted"),
        ValueError("decode failure"),
    ],
)
def test_transport_and_unclassified_errors_still_discard(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    db, created = _counting_db(monkeypatch, execute_error=error)
    with pytest.raises(DatabaseError, match="query failed"):
        db.fetch_all("SELECT 1")
    conn = created[0]
    # No rollback is attempted on a possibly broken session; it is dropped.
    assert conn.rollbacks == 0
    assert conn.closed is True
    assert db._connection is None


def test_timeout_wrapped_in_sql_error_class_still_discards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A timeout is classified first, whatever class the driver wraps it in.
    wrapped = pycubrid.ProgrammingError("socket communication failed")
    wrapped.__cause__ = TimeoutError("timed out")
    db, created = _counting_db(monkeypatch, execute_error=wrapped)
    with pytest.raises(QueryTimeoutError):
        db.fetch_many("SELECT SLEEP(999)", None, 10)
    assert created[0].rollbacks == 0
    assert db._connection is None


def test_read_timeout_path_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    db, created = _counting_db(monkeypatch, execute_error=TimeoutError("read timed out"))
    with pytest.raises(QueryTimeoutError, match="query exceeded timeout"):
        db.fetch_all("SELECT SLEEP(999)")
    conn = created[0]
    # No rollback on the dead socket, and the cursor is not closed either.
    assert conn.rollbacks == 0
    assert conn.cursors[0].closed is False
    assert conn.closed is True
    assert db._connection is None


def test_execute_write_still_commits_without_extra_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, created = _counting_db(monkeypatch)
    db.execute_write("UPDATE t SET x = 1")
    assert created[0].commits == 1
    assert created[0].rollbacks == 0


def test_trace_cleanup_rolls_back_once(monkeypatch: pytest.MonkeyPatch) -> None:
    db, created = _counting_db(monkeypatch, rows=[("Trace Statistics: stub",)])
    with db.trace_enabled() as cursor:
        cursor.execute("SELECT 1", ())
    assert created[0].rollbacks == 1
    assert db._connection is created[0]


class _TraceCleanupConnection(FakeConnection):
    """Fake connection whose trace cleanup fails at one chosen step (#264).

    ``fail_at`` is ``"cursor"`` (opening the cleanup cursor, the second
    ``cursor()`` call), ``"trace_off"`` (``SET TRACE OFF``) or ``"rollback"``.
    Every driver call records whether the ``Database`` lock was held.
    """

    def __init__(self, fail_at: str | None, lock_probe: Any) -> None:
        super().__init__(rows=[("Trace Statistics: stub",)])
        self._fail_at = fail_at
        self._lock_probe = lock_probe
        self.lock_owned: list[bool] = []
        self.rollbacks = 0
        self.executed: list[str] = []

    def cursor(self) -> FakeCursor:
        self.lock_owned.append(self._lock_probe())
        if self._fail_at == "cursor" and len(self.cursors) == 1:
            raise pycubrid.OperationalError("cursor boom")
        cursor = super().cursor()
        plain_execute = cursor.execute

        def _execute(sql: str, params: tuple[Any, ...] = ()) -> None:
            self.lock_owned.append(self._lock_probe())
            self.executed.append(sql)
            if self._fail_at == "trace_off" and sql == "SET TRACE OFF":
                raise pycubrid.OperationalError("trace off boom")
            plain_execute(sql, params)

        cursor.execute = _execute  # type: ignore[method-assign]
        return cursor

    def rollback(self) -> None:
        self.lock_owned.append(self._lock_probe())
        self.rollbacks += 1
        if self._fail_at == "rollback":
            raise pycubrid.OperationalError("rollback boom")


def _trace_cleanup_db(
    monkeypatch: pytest.MonkeyPatch, fail_at: str | None
) -> tuple[Database, list[_TraceCleanupConnection]]:
    """Return a Database whose first connection fails cleanup at ``fail_at``.

    Later connections are healthy, so the next call shows whether it reconnected.
    """
    created: list[_TraceCleanupConnection] = []
    db = Database(_TEST_CONFIG)
    probe = db._lock._is_owned  # type: ignore[attr-defined]

    def _connect(**_k: Any) -> _TraceCleanupConnection:
        conn = _TraceCleanupConnection(fail_at if not created else None, probe)
        created.append(conn)
        return conn

    monkeypatch.setattr(pycubrid, "connect", _connect)
    return db, created


def _run_explain(db: Database) -> list[tuple[Any, ...]]:
    with db.trace_enabled() as cursor:
        cursor.execute("SELECT 1", ())
        cursor.execute("SHOW TRACE", ())
        return list(cursor.fetchall())


@pytest.mark.parametrize("fail_at", ["cursor", "trace_off", "rollback"])
def test_trace_cleanup_failure_discards_connection(
    monkeypatch: pytest.MonkeyPatch, fail_at: str
) -> None:
    db, created = _trace_cleanup_db(monkeypatch, fail_at)
    # The successful query keeps its result; the cleanup failure is not raised.
    assert _run_explain(db) == [("Trace Statistics: stub",)]
    failed = created[0]
    assert db._connection is None
    assert failed.closed is True
    # Cleanup ran entirely under the lock.
    assert failed.lock_owned and all(failed.lock_owned)
    # Cleanup stops at the first failure: no rollback after a cursor or
    # SET TRACE OFF failure.
    assert failed.rollbacks == (1 if fail_at == "rollback" else 0)
    # The user statement ran once and is not replayed on the new connection.
    assert failed.executed.count("SELECT 1") == 1
    assert db.fetch_all("SELECT 2") == [("Trace Statistics: stub",)]
    assert len(created) == 2
    assert db._connection is created[1]
    assert "SELECT 1" not in created[1].executed


def test_trace_cleanup_failure_keeps_original_query_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, created = _trace_cleanup_db(monkeypatch, "trace_off")
    original = pycubrid.ProgrammingError("bad sql")
    with pytest.raises(DatabaseError, match=r"^query failed: ProgrammingError$") as info:
        with db.trace_enabled():
            _raise(original)
    # The query error, not the cleanup error, is the one reported.
    assert info.value.__cause__ is original
    assert db._connection is None
    assert created[0].closed is True
    db.fetch_all("SELECT 2")
    assert db._connection is created[1]


def test_trace_timeout_skips_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    db, created = _trace_cleanup_db(monkeypatch, None)
    with pytest.raises(QueryTimeoutError):
        with db.trace_enabled():
            _raise(socket.timeout("timed out"))
    conn = created[0]
    # The socket is dead: no cursor close, SET TRACE OFF or rollback is sent.
    assert conn.executed == ["SET TRACE ON"]
    assert conn.rollbacks == 0
    assert conn.cursors[0].closed is False
    assert db._connection is None


def test_trace_cleanup_success_keeps_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    db, created = _trace_cleanup_db(monkeypatch, None)
    _run_explain(db)
    _run_explain(db)
    assert len(created) == 1
    conn = created[0]
    assert db._connection is conn
    assert conn.closed is False
    assert conn.rollbacks == 2
    assert conn.executed.count("SET TRACE OFF") == 2
    assert all(conn.lock_owned)


def test_data_error_from_fetchmany_rolls_back_and_keeps_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = pycubrid.DataError("type conversion", code=-8, errno=-8)
    db, created = _counting_db(monkeypatch, rows=[(1,)], fetch_error=error)
    with pytest.raises(DatabaseError, match="query failed: DataError"):
        db.fetch_many("SELECT x FROM t", None, 10)
    conn = created[0]
    assert conn.rollbacks == 1
    assert conn.closed is False
    assert db._connection is conn


def test_cursor_creation_server_error_discards_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = pycubrid.ProgrammingError("cannot open cursor", code=-493, errno=-493)
    db, created = _counting_db(monkeypatch, cursor_error=error)
    with pytest.raises(DatabaseError, match="query failed: ProgrammingError"):
        db.fetch_all("SELECT 1")
    conn = created[0]
    # No cursor exists, so the session state is unknown: no rollback, just discard.
    assert conn.rollbacks == 0
    assert conn.closed is True
    assert db._connection is None


_LEAKY_CONFIG = Config(
    host="db.internal",
    port=33000,
    user="app_user",
    password="hunter2-secret",
    database="secretdb",
    readonly=True,
    max_chars=4000,
    max_rows=1000,
)
_LEAKY_MESSAGE = (
    "cannot reach db.internal:33000 db=secretdb user=app_user "
    "password=hunter2-secret while running SELECT ssn FROM payroll"
)
_SECRETS = ("db.internal", "secretdb", "hunter2-secret", "app_user", "payroll")


def _assert_no_secrets(text: str) -> None:
    for secret in _SECRETS:
        assert secret not in text


def _connect_raises(**_k: Any) -> Any:
    raise pycubrid.OperationalError(_LEAKY_MESSAGE)


def test_connect_failure_is_sanitized_and_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(pycubrid, "connect", _connect_raises)
    db = Database(_LEAKY_CONFIG)
    with caplog.at_level("ERROR", logger="cubrid_mcp_server.database"):
        with pytest.raises(DatabaseError) as info:
            db.connect()
    assert str(info.value) == "failed to connect to CUBRID"
    assert "db.internal" in caplog.text
    assert "secretdb" in caplog.text
    assert "hunter2-secret" in caplog.text  # cause preserved via exc_info


@pytest.mark.parametrize("entry", ["fetch_all", "execute_write", "exclusive"])
def test_connect_failure_sanitized_on_every_entry_point(
    monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    monkeypatch.setattr(pycubrid, "connect", _connect_raises)
    db = Database(_LEAKY_CONFIG)
    with pytest.raises(DatabaseError) as info:
        if entry == "fetch_all":
            db.fetch_all("SELECT 1")
        elif entry == "execute_write":
            db.execute_write("DELETE FROM t")
        else:
            with db.exclusive():
                pass
    _assert_no_secrets(str(info.value))


def test_health_check_connect_failure_is_sanitized_and_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(pycubrid, "connect", _connect_raises)
    db = Database(_LEAKY_CONFIG)
    with caplog.at_level("ERROR", logger="cubrid_mcp_server.database"):
        status = db.health_check()
    assert status == {"ok": False, "error": "DatabaseError"}
    _assert_no_secrets(str(status))
    assert "db.internal" in caplog.text
    assert "hunter2-secret" in caplog.text


def test_health_check_ping_failure_is_sanitized_and_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    conn = FakeConnection()

    def _boom() -> str:
        raise pycubrid.OperationalError(_LEAKY_MESSAGE)

    conn.get_server_version = _boom  # type: ignore[method-assign]
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_LEAKY_CONFIG)
    with caplog.at_level("ERROR", logger="cubrid_mcp_server.database"):
        status = db.health_check()
    assert status == {"ok": False, "error": "OperationalError"}
    _assert_no_secrets(str(status))
    assert "db.internal" in caplog.text
    assert "hunter2-secret" in caplog.text
    assert "payroll" in caplog.text


def test_exclusive_driver_error_is_sanitized_and_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: FakeConnection())
    db = Database(_LEAKY_CONFIG)
    with caplog.at_level("ERROR", logger="cubrid_mcp_server.database"):
        with pytest.raises(DatabaseError) as info:
            with db.exclusive():
                _raise(pycubrid.ProgrammingError(_LEAKY_MESSAGE))
    _assert_no_secrets(str(info.value))
    assert "payroll" in caplog.text


# --- execute_query is result-set reads only (#235) ---


@pytest.mark.parametrize("method", ["fetch_all", "fetch_many"])
def test_no_result_set_rolls_back_and_keeps_connection(
    monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    db, created = _counting_db(monkeypatch, no_result_set=True)
    with pytest.raises(NoResultSetError, match="no result set.*use execute_write"):
        getattr(db, method)("INSERT INTO t VALUES (1)")
    conn = created[0]
    # Rolled back exactly once (no extra read-transaction rollback), never committed.
    assert conn.rollbacks == 1
    assert conn.commits == 0
    assert conn.cursors[0].fetchmany_calls == 0
    assert conn.cursors[0].closed is True
    # The session is intact, so the connection is kept.
    assert conn.closed is False
    assert db._connection is conn
    assert db.connect() is conn


def test_no_result_set_error_is_a_value_error() -> None:
    assert issubclass(NoResultSetError, ValueError)
    assert not issubclass(NoResultSetError, DatabaseError)


def test_no_result_set_with_failed_rollback_discards(monkeypatch: pytest.MonkeyPatch) -> None:
    db, created = _counting_db(monkeypatch, no_result_set=True, rollback_error=RuntimeError("gone"))
    with pytest.raises(NoResultSetError):
        db.fetch_many("DELETE FROM t", None, 10)
    assert created[0].rollbacks == 1
    assert created[0].closed is True
    assert db._connection is None


# --- owner-qualified catalog probe (#296) ---


class _OwnerProbeConnection(FakeConnection):
    """Fake connection whose ``db_attribute`` has ``owner_name`` only when ``owners``."""

    def __init__(self, backend: dict[str, Any]) -> None:
        super().__init__()
        self.backend = backend

    def cursor(self) -> FakeCursor:
        backend = self.backend
        cursor = super().cursor()
        original_execute = cursor.execute

        def _execute(sql: str, params: tuple[Any, ...] = ()) -> None:
            original_execute(sql, params)
            if '"owner_name" FROM db_attribute' in sql:
                if backend.get("lost"):
                    raise ConnectionResetError("broker restarted")
                if not backend["owners"]:
                    raise pycubrid.ProgrammingError("Semantic: owner_name is not defined")

        cursor.execute = _execute  # type: ignore[method-assign]
        return cursor


def test_owner_qualified_names_probed_and_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    backend: dict[str, Any] = {"owners": True}
    created: list[_OwnerProbeConnection] = []

    def _connect(**_k: Any) -> _OwnerProbeConnection:
        created.append(_OwnerProbeConnection(backend))
        return created[-1]

    monkeypatch.setattr(pycubrid, "connect", _connect)
    db = Database(_TEST_CONFIG)
    assert db.owner_qualified_names() is True
    assert db.owner_qualified_names() is True
    probes = [sql for conn in created for c in conn.cursors for sql, _ in c.executed]
    assert len(probes) == 1  # cached while connected
    db._discard_connection()
    backend["owners"] = False
    assert db.owner_qualified_names() is False  # re-probed on the next connection
    # The server rejecting the column keeps the session.
    assert created[-1].closed is False


def test_owner_qualified_names_not_cached_after_a_lost_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend: dict[str, Any] = {"owners": True, "lost": True}
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: _OwnerProbeConnection(backend))
    db = Database(_TEST_CONFIG)
    with pytest.raises(DatabaseError):
        db.owner_qualified_names()
    backend["lost"] = False
    assert db.owner_qualified_names() is True


@pytest.mark.parametrize("owners", [True, False])
def test_owner_qualified_names_not_cached_when_the_probe_drops_the_connection(
    monkeypatch: pytest.MonkeyPatch, owners: bool
) -> None:
    # The rollback after the probe fails, so the probed connection is discarded;
    # the answer is returned but re-probed on the next connection.
    backend: dict[str, Any] = {"owners": owners}
    created: list[_OwnerProbeConnection] = []

    def _connect(**_k: Any) -> _OwnerProbeConnection:
        conn = _OwnerProbeConnection(backend)
        if not created:
            conn.rollback = lambda: _raise(RuntimeError("rollback failed"))  # type: ignore[method-assign]
        created.append(conn)
        return conn

    monkeypatch.setattr(pycubrid, "connect", _connect)
    db = Database(_TEST_CONFIG)
    assert db.owner_qualified_names() is owners
    assert db._connection is None
    backend["owners"] = not owners
    assert db.owner_qualified_names() is (not owners)
    assert db.owner_qualified_names() is (not owners)
    assert sum(len(c.cursors) for c in created) == 2


# --- exclusive() keeps the session after a server-side SQL error (#299) ---


@pytest.mark.parametrize(
    "error", [pycubrid.ProgrammingError, pycubrid.IntegrityError, pycubrid.DataError]
)
def test_exclusive_keeps_connection_after_server_sql_error(
    monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> None:
    conn = FakeConnection()
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    with pytest.raises(DatabaseError, match=f"^query failed: {error.__name__}$"):
        with db.exclusive():
            _raise(error("Semantic: bad column"))
    assert conn.rolled_back is True
    assert conn.closed is False
    assert db._connection is conn


def test_exclusive_discards_when_rollback_after_sql_error_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = FakeConnection()
    conn.rollback = lambda: _raise(RuntimeError("rollback failed"))  # type: ignore[method-assign]
    monkeypatch.setattr(pycubrid, "connect", lambda **_k: conn)
    db = Database(_TEST_CONFIG)
    with pytest.raises(DatabaseError, match="ProgrammingError"):
        with db.exclusive():
            _raise(pycubrid.ProgrammingError("Semantic: bad column"))
    assert db._connection is None


def test_trace_enabled_keeps_connection_after_server_sql_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, created = _trace_cleanup_db(monkeypatch, None)
    with pytest.raises(DatabaseError, match="ProgrammingError"):
        with db.trace_enabled():
            _raise(pycubrid.ProgrammingError("Semantic: bad column"))
    # SET TRACE OFF and exactly one rollback ran, and the session is reused.
    assert created[0].rollbacks == 1
    assert db._connection is created[0]
    db.fetch_all("SELECT 2")
    assert db._connection is created[0]


def test_exclusive_skips_rollback_when_the_block_discarded_the_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, created = _trace_cleanup_db(monkeypatch, "trace_off")
    with pytest.raises(DatabaseError, match="ProgrammingError"):
        with db.trace_enabled():
            _raise(pycubrid.ProgrammingError("bad sql"))
    # Trace cleanup failed and discarded the session; no rollback is sent to it.
    assert db._connection is None
    assert created[0].rollbacks == 0
