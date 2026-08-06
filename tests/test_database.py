"""Unit tests for cubrid_mcp_server.database using a fake pycubrid driver.

These exercise the connection lifecycle, cursor error handling, and streaming
fetch logic without a live CUBRID server by monkeypatching ``pycubrid.connect``.
"""

from __future__ import annotations

from typing import Any

import pytest

import pycubrid
from cubrid_mcp_server.config import Config
from cubrid_mcp_server.database import Database, DatabaseError

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

    def get_server_version(self) -> str:
        self.server_version_calls += 1
        if self.version_error:
            raise RuntimeError("stale connection")
        return "11.0"

    def cursor(self) -> FakeCursor:
        cursor = FakeCursor(self._rows)
        self.cursors.append(cursor)
        return cursor

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
    # Reuse path validates the cached connection via get_server_version.
    assert first.server_version_calls == 1


def test_connect_discards_stale_connection(patch_connect: list[FakeConnection]) -> None:
    db = Database(_TEST_CONFIG)
    first = db.connect()
    first.version_error = True  # next reuse attempt fails -> discard + reconnect
    second = db.connect()
    assert second is not first
    assert first.closed is True
    assert len(patch_connect) == 2


def test_discard_connection_swallows_close_error(patch_connect: list[FakeConnection]) -> None:
    db = Database(_TEST_CONFIG)
    first = db.connect()
    first.version_error = True
    first.close_error = True  # close raises during discard; must be swallowed
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
            raise ValueError("boom")
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
