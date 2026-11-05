"""Coverage for error/edge branches in server and safety modules.

These exercise the defensive paths (lazy init, cleanup-on-error, oversized
binary summaries, startup config failure) that the happy-path tests skip.
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
from dataclasses import replace
from typing import Any

import pytest

import cubrid_mcp_server.server as server
from cubrid_mcp_server import context as context_module
from cubrid_mcp_server.config import Config, ConfigError, ConnectionRegistry
from cubrid_mcp_server.database import Database
from cubrid_mcp_server.safety import ensure_read_only
from tests.helpers import single_context

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


# ---------------------------------------------------------------------------
# _db() lazy initialization
# ---------------------------------------------------------------------------


def test_context_lazily_initializes_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_context", None)
    registry = ConnectionRegistry(configs={"default": _TEST_CONFIG})
    monkeypatch.setattr(ConnectionRegistry, "from_env", classmethod(lambda cls, env=None: registry))

    created: list[Any] = []

    class _FakeDatabase:
        def __init__(self, config: Config) -> None:
            created.append(config)

    # from_env() builds the Database via the context module's import.
    monkeypatch.setattr(context_module, "Database", _FakeDatabase)

    first = server._db()
    second = server._db()
    assert first is second
    assert created == [_TEST_CONFIG]  # constructed exactly once


# ---------------------------------------------------------------------------
# _resolve_table error branches
# ---------------------------------------------------------------------------


class _NameOnlyDB:
    """Minimal db exposing fetch_all for _all_table_names lookups."""

    def __init__(self, names: list[str]) -> None:
        self._names = names

    def owner_qualified_names(self) -> bool:
        return False

    def fetch_all(self, sql: str, params: tuple[Any, ...] | None = None) -> list[tuple[Any, ...]]:
        return [(n,) for n in self._names]


def test_resolve_table_rejects_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_db", lambda connection=None: _NameOnlyDB(["users"]))
    with pytest.raises(ValueError, match="must not be empty"):
        server._resolve_table("   ")


def test_resolve_table_rejects_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_db", lambda connection=None: _NameOnlyDB(["users"]))
    with pytest.raises(ValueError, match="unknown table"):
        server._resolve_table("ghost")


# ---------------------------------------------------------------------------
# _reset_trace_state error branches (explain_query cleanup)
# ---------------------------------------------------------------------------


class _FailingCursor:
    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        if sql == "SET TRACE OFF":
            raise RuntimeError("trace off boom")

    def fetchall(self) -> list[tuple[Any, ...]]:
        return [("plan text",)]

    def close(self) -> None:
        pass


class _CleanupFailingConn:
    def cursor(self) -> _FailingCursor:
        return _FailingCursor()

    def rollback(self) -> None:
        raise RuntimeError("rollback boom")


class _CleanupFailingDB:
    def __init__(self) -> None:
        self.discarded = 0

    @contextmanager
    def exclusive(self, **_kwargs: Any) -> Any:
        yield _CleanupFailingConn()

    def _discard_connection(self) -> None:
        self.discarded += 1

    # Reuse the real cleanup logic so this test exercises production code.
    _safe_close_cursor = staticmethod(Database._safe_close_cursor)
    _reset_trace_state = Database._reset_trace_state
    trace_enabled = Database.trace_enabled


def test_explain_query_swallows_cleanup_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cleanup failure is logged and discards the connection, not raised (#264)."""
    db = _CleanupFailingDB()
    monkeypatch.setattr(server, "_context", single_context(config=_TEST_CONFIG, database=db))
    result = server.explain_query("SELECT 1")
    assert result == {"sql": "SELECT 1", "plan": "plan text", "truncated": False}
    assert db.discarded == 1


# ---------------------------------------------------------------------------
# table_row_counts limit + per-table error branches
# ---------------------------------------------------------------------------


class _RowCountErrorDB:
    def owner_qualified_names(self) -> bool:
        return False

    def fetch_all(self, sql: str, params: tuple[Any, ...] | None = None) -> list[tuple[Any, ...]]:
        if "db_class" in sql:
            return [("users",)]
        raise RuntimeError("count failed")


def test_table_row_counts_rejects_too_many_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_db", lambda connection=None: _NameOnlyDB(["users"]))
    monkeypatch.setattr(server, "_cfg", lambda connection=None: _TEST_CONFIG)
    too_many = [f"t{i}" for i in range(_TEST_CONFIG.max_row_count_tables + 1)]
    with pytest.raises(ValueError, match="too many tables"):
        server.table_row_counts(too_many)


def test_table_row_counts_reports_per_table_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_db", lambda connection=None: _RowCountErrorDB())
    monkeypatch.setattr(server, "_cfg", lambda connection=None: _TEST_CONFIG)
    result = server.table_row_counts(["users"])
    # The raw driver message is sanitized to the exception category only.
    assert result["tables"] == [{"table": "users", "row_count": None, "error": "RuntimeError"}]


class _ManyTablesDB:
    """Reports ``count`` user tables and returns 1 for every COUNT(*)."""

    def __init__(self, count: int) -> None:
        self.names = [f"t{i:03d}" for i in range(count)]
        self.counted: list[str] = []

    def owner_qualified_names(self) -> bool:
        return False

    def fetch_all(self, sql: str, params: tuple[Any, ...] | None = None) -> list[tuple[Any, ...]]:
        if "db_class" in sql:
            # Deliberately unordered: the tool must sort before capping.
            return [(name,) for name in reversed(self.names)]
        self.counted.append(sql)
        return [(1,)]


def test_table_row_counts_default_caps_beyond_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _ManyTablesDB(_TEST_CONFIG.max_row_count_tables + 1)
    monkeypatch.setattr(server, "_db", lambda connection=None: db)
    monkeypatch.setattr(server, "_cfg", lambda connection=None: _TEST_CONFIG)
    result = server.table_row_counts()
    assert result["truncated"] is True
    assert result["total_tables"] == 51
    assert [r["table"] for r in result["tables"]] == db.names[:50]
    assert len(db.counted) == 50


def test_table_row_counts_default_at_limit_not_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _ManyTablesDB(_TEST_CONFIG.max_row_count_tables)
    monkeypatch.setattr(server, "_db", lambda connection=None: db)
    monkeypatch.setattr(server, "_cfg", lambda connection=None: _TEST_CONFIG)
    result = server.table_row_counts()
    assert result["truncated"] is False
    assert result["total_tables"] == 50
    assert len(result["tables"]) == 50


def test_table_row_counts_explicit_list_over_limit_still_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _ManyTablesDB(_TEST_CONFIG.max_row_count_tables + 1)
    monkeypatch.setattr(server, "_db", lambda connection=None: db)
    monkeypatch.setattr(server, "_cfg", lambda connection=None: _TEST_CONFIG)
    with pytest.raises(ValueError, match="too many tables requested \\(51\\)"):
        server.table_row_counts(list(db.names))
    assert db.counted == []


def test_table_row_counts_honors_configured_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _ManyTablesDB(5)
    config = replace(_TEST_CONFIG, max_row_count_tables=3)
    monkeypatch.setattr(server, "_db", lambda connection=None: db)
    monkeypatch.setattr(server, "_cfg", lambda connection=None: config)
    result = server.table_row_counts()
    assert result["truncated"] is True
    assert [r["table"] for r in result["tables"]] == db.names[:3]
    with pytest.raises(ValueError, match="too many tables requested \\(4\\); limit is 3 per call"):
        server.table_row_counts(db.names[:4])
    assert len(server.table_row_counts(db.names[:3])["tables"]) == 3


# ---------------------------------------------------------------------------
# _coerce oversized binary summary
# ---------------------------------------------------------------------------


def test_coerce_oversized_binary_returns_size_summary() -> None:
    data = b"\x00" * (_TEST_CONFIG.max_inline_binary_bytes + 1)
    assert server._coerce(data) == f"<binary {len(data)} bytes>"
    assert server._coerce(data[:-1]) == base64.b64encode(data[:-1]).decode("ascii")


@pytest.mark.parametrize(
    ("limit", "data", "expected"),
    [
        (4, b"\x01\x02\x03\x04", "AQIDBA=="),
        (3, b"\x01\x02\x03\x04", "<binary 4 bytes>"),
        (0, b"", ""),
        (0, b"\x01", "<binary 1 bytes>"),
    ],
)
def test_execute_query_honors_configured_inline_binary_limit(
    monkeypatch: pytest.MonkeyPatch, limit: int, data: bytes, expected: str
) -> None:
    class _BinaryDB:
        def fetch_many(
            self, sql: str, params: Any = None, max_rows: int | None = None
        ) -> tuple[list[tuple[Any, ...]], bool]:
            return [(data,)], False

    config = replace(_TEST_CONFIG, max_inline_binary_bytes=limit)
    monkeypatch.setattr(server, "_context", single_context(config=config, database=_BinaryDB()))
    assert server.execute_query("SELECT b FROM t")["rows"] == [[expected]]


# ---------------------------------------------------------------------------
# main() startup paths
# ---------------------------------------------------------------------------


def test_main_exits_on_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(cls: type[ConnectionRegistry], env: Any = None) -> ConnectionRegistry:
        raise ConfigError("missing CUBRID_HOST")

    monkeypatch.setattr(ConnectionRegistry, "from_env", classmethod(_raise))
    with pytest.raises(SystemExit) as excinfo:
        server.main([])
    assert excinfo.value.code == 1


def test_main_runs_server_on_valid_config(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = ConnectionRegistry(configs={"default": _TEST_CONFIG})
    monkeypatch.setattr(ConnectionRegistry, "from_env", classmethod(lambda cls, env=None: registry))
    monkeypatch.setattr(server, "_context", None)
    ran: list[bool] = []
    monkeypatch.setattr(server.mcp, "run", lambda: ran.append(True))
    server.main([])
    assert ran[0] is True


# ---------------------------------------------------------------------------
# safety: leading keyword nested inside a parenthesized group
# ---------------------------------------------------------------------------


def test_safety_accepts_parenthesized_select() -> None:
    # Leading token is a group; _leading_keyword must recurse into it.
    ensure_read_only("(SELECT 1)")
