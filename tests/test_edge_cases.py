"""Practical edge-case coverage for safety, rendering, coercion, and identifier quoting.

These tests do not exercise new behavior; they pin down current contracts so
that future refactors don't silently regress them. Organized into sections by
the module/helper under test.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

import pytest

from cubrid_mcp_server import server
from cubrid_mcp_server.config import Config
from cubrid_mcp_server.safety import UnsafeSQLError, ensure_read_only

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
# A. Safety bypass attempts (regression guards for read-only enforcement)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "select 1",
        "  SELECT 1  ;  ",
        "SeLeCt 1",
        "WITH x AS (SELECT 1) SELECT * FROM x",
        "with x as (select 1) select * from x",
        "EXPLAIN SELECT * FROM users WHERE id = 1",
    ],
)
def test_safety_accepts_legitimate_read_variants(sql: str) -> None:
    ensure_read_only(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; UPDATE users SET x=1",
        "SELECT 1;\n DELETE FROM users",
        "SELECT 1 ;DROP TABLE foo",
        "REPLACE INTO users VALUES (1)",
        "RENAME TABLE users TO ex_users",
        "MERGE INTO target USING src ON (1=1) WHEN MATCHED THEN UPDATE SET x=1",
        "CALL my_proc()",
        "WITH x AS (SELECT 1) DELETE FROM users",
        "WITH x AS (SELECT 1) INSERT INTO t SELECT * FROM x",
        "SELECT * FROM users FOR UPDATE",
    ],
)
def test_safety_rejects_bypass_attempts(sql: str) -> None:
    with pytest.raises(UnsafeSQLError):
        ensure_read_only(sql)


def test_safety_rejects_only_comment() -> None:
    with pytest.raises(UnsafeSQLError):
        ensure_read_only("-- just a comment")


def test_safety_rejects_only_block_comment() -> None:
    with pytest.raises(UnsafeSQLError):
        ensure_read_only("/* nothing here */")


# ---------------------------------------------------------------------------
# B. _render_rows truncation behavior
# ---------------------------------------------------------------------------


def test_render_rows_empty_input() -> None:
    assert server._render_rows([], max_chars=100) == {"rows": [], "truncated": False}


def test_render_rows_all_fit_under_limit() -> None:
    rows = [("a",), ("bb",), ("ccc",)]
    out = server._render_rows(rows, max_chars=100)
    assert out == {"rows": [["a"], ["bb"], ["ccc"]], "truncated": False}


def test_render_rows_truncates_after_limit() -> None:
    rows = [("aaaa",), ("bbbb",), ("cccc",)]
    out = server._render_rows(rows, max_chars=5)
    assert out["truncated"] is True
    assert out["rows"] == [["aaaa"]]


def test_render_rows_unicode_length() -> None:
    rows = [("한글두글자",)]
    assert server._render_rows(rows, max_chars=10) == {"rows": [["한글두글자"]], "truncated": False}


# ---------------------------------------------------------------------------
# C. _coerce type handling for real CUBRID column types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        (True, True),
        (False, False),
        (0, 0),
        (1, 1),
        (-42, -42),
        (3.14, 3.14),
        ("hello", "hello"),
        ("", ""),
    ],
)
def test_coerce_passes_primitives_through(value: Any, expected: Any) -> None:
    assert server._coerce(value) == expected


def test_coerce_datetime_to_string() -> None:
    assert server._coerce(datetime.datetime(2026, 5, 14, 12, 30, 45)) == "2026-05-14 12:30:45"


def test_coerce_date_to_string() -> None:
    assert server._coerce(datetime.date(2026, 5, 14)) == "2026-05-14"


def test_coerce_decimal_to_string() -> None:
    assert server._coerce(Decimal("1.50")) == "1.50"


def test_coerce_bytes_returns_string() -> None:
    assert isinstance(server._coerce(b"\x00\x01\x02"), str)


# ---------------------------------------------------------------------------
# D. explain_query keyword acceptance (matches docstring contract)
# ---------------------------------------------------------------------------


class _FakeCursor:
    def __init__(self) -> None:
        self.executed: list[str] = []
        self._fetch: list[tuple[Any, ...]] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        self.executed.append(sql)
        if sql.strip().upper().startswith("SHOW TRACE"):
            self._fetch = [("Trace Statistics: stub",)]
        else:
            self._fetch = []

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._fetch

    def close(self) -> None:
        pass


class _FakeConnDB:
    def __init__(self) -> None:
        self.cursors: list[_FakeCursor] = []
        self.rolled_back = False

    def _make_conn(self) -> Any:
        outer = self

        class _Conn:
            def cursor(self_inner) -> _FakeCursor:
                cur = _FakeCursor()
                outer.cursors.append(cur)
                return cur

            def rollback(self_inner) -> None:
                outer.rolled_back = True

        return _Conn()

    def exclusive(self) -> Any:
        from contextlib import contextmanager

        @contextmanager
        def _cm() -> Any:
            yield self._make_conn()

        return _cm()

    def connect(self) -> Any:
        return self._make_conn()


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "select 1",
        "  SELECT 1  ",
        "SELECT 1;",
        "WITH cte AS (SELECT 1) SELECT * FROM cte",
        "with cte as (select 1) select * from cte",
    ],
)
def test_explain_query_accepts_select_and_with(sql: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_db", lambda: _FakeConnDB())
    monkeypatch.setattr(server, "_config", _TEST_CONFIG)
    result = server.explain_query(sql)
    assert "plan" in result and "sql" in result


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE users",
        "INSERT INTO users VALUES (1)",
        "UPDATE users SET x=1",
        "DELETE FROM users",
    ],
)
def test_explain_query_rejects_writes(sql: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_db", lambda: _FakeConnDB())
    monkeypatch.setattr(server, "_config", _TEST_CONFIG)
    with pytest.raises(ValueError):
        server.explain_query(sql)


# ---------------------------------------------------------------------------
# E. _quote_ident escaping for table_row_counts identifier interpolation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("users", '"users"'),
        ("CamelCase", '"CamelCase"'),
        ('weird"name', '"weird""name"'),
        ('"', '""""'),
        ("a b c", '"a b c"'),
        ("", '""'),
    ],
)
def test_quote_ident_escapes_double_quotes(name: str, expected: str) -> None:
    assert server._quote_ident(name) == expected


def test_quote_ident_blocks_injection_in_count_query() -> None:
    """A malicious table name should remain a single quoted identifier with doubled quotes."""
    quoted = server._quote_ident('users"; DROP TABLE users; --')
    assert quoted.startswith('"') and quoted.endswith('"')
    assert quoted.count('"') >= 4
