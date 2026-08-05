"""Coverage for error/edge branches in server and safety modules.

These exercise the defensive paths (lazy init, cleanup-on-error, oversized
binary summaries, startup config failure) that the happy-path tests skip.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest

import cubrid_mcp_server.server as server
from cubrid_mcp_server.config import Config, ConfigError
from cubrid_mcp_server.safety import ensure_read_only

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


def test_db_lazily_initializes_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_config", None)
    monkeypatch.setattr(server, "_database", None)
    monkeypatch.setattr(Config, "from_env", classmethod(lambda cls: _TEST_CONFIG))

    created: list[Any] = []

    class _FakeDatabase:
        def __init__(self, config: Config) -> None:
            created.append(config)

    monkeypatch.setattr(server, "Database", _FakeDatabase)

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

    def fetch_all(self, sql: str, params: tuple[Any, ...] | None = None) -> list[tuple[Any, ...]]:
        return [(n,) for n in self._names]


def test_resolve_table_rejects_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_db", lambda: _NameOnlyDB(["users"]))
    with pytest.raises(ValueError, match="must not be empty"):
        server._resolve_table("   ")


def test_resolve_table_rejects_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_db", lambda: _NameOnlyDB(["users"]))
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
    @contextmanager
    def exclusive(self) -> Any:
        yield _CleanupFailingConn()


def test_explain_query_swallows_cleanup_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """SET TRACE OFF and rollback failures during cleanup are logged, not raised."""
    monkeypatch.setattr(server, "_db", lambda: _CleanupFailingDB())
    monkeypatch.setattr(server, "_config", _TEST_CONFIG)
    result = server.explain_query("SELECT 1")
    assert result["plan"] == "plan text"
    assert result["sql"] == "SELECT 1"


# ---------------------------------------------------------------------------
# table_row_counts limit + per-table error branches
# ---------------------------------------------------------------------------


class _RowCountErrorDB:
    def fetch_all(self, sql: str, params: tuple[Any, ...] | None = None) -> list[tuple[Any, ...]]:
        if "db_class" in sql:
            return [("users",)]
        raise RuntimeError("count failed")


def test_table_row_counts_rejects_too_many_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_db", lambda: _NameOnlyDB(["users"]))
    too_many = [f"t{i}" for i in range(server._MAX_ROW_COUNT_TABLES + 1)]
    with pytest.raises(ValueError, match="too many tables"):
        server.table_row_counts(too_many)


def test_table_row_counts_reports_per_table_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_db", lambda: _RowCountErrorDB())
    result = server.table_row_counts(["users"])
    assert result == [{"table": "users", "row_count": None, "error": "count failed"}]


# ---------------------------------------------------------------------------
# _coerce oversized binary summary
# ---------------------------------------------------------------------------


def test_coerce_oversized_binary_returns_size_summary() -> None:
    data = b"\x00" * (server._MAX_INLINE_BINARY_BYTES + 1)
    assert server._coerce(data) == f"<binary {len(data)} bytes>"


# ---------------------------------------------------------------------------
# main() startup paths
# ---------------------------------------------------------------------------


def test_main_exits_on_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(cls: type[Config]) -> Config:
        raise ConfigError("missing CUBRID_HOST")

    monkeypatch.setattr(Config, "from_env", classmethod(_raise))
    with pytest.raises(SystemExit) as excinfo:
        server.main()
    assert excinfo.value.code == 1


def test_main_runs_server_on_valid_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "from_env", classmethod(lambda cls: _TEST_CONFIG))
    ran: list[bool] = []
    monkeypatch.setattr(server.mcp, "run", lambda: ran.append(True))
    server.main()
    assert ran == [True]


# ---------------------------------------------------------------------------
# safety: leading keyword nested inside a parenthesized group
# ---------------------------------------------------------------------------


def test_safety_accepts_parenthesized_select() -> None:
    # Leading token is a group; _leading_keyword must recurse into it.
    ensure_read_only("(SELECT 1)")
