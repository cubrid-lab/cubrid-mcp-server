"""Unit tests for opt-in audit logging (issue #127).

Covers the redaction invariants (no raw SQL / no literal values leak), the
stderr-only guarantee, off-by-default behaviour, and identifier/category
extraction.
"""

from __future__ import annotations

import io
import json
from dataclasses import replace
from typing import Any

import pytest

from cubrid_mcp_server import server
from cubrid_mcp_server.audit import AuditLogger, _category, _identifiers
from cubrid_mcp_server.config import Config
from cubrid_mcp_server.context import AppContext

_SECRET = "p@ssw0rd-should-never-appear"

_BASE_CONFIG = Config(
    host="h",
    port=33000,
    user="u",
    password="",
    database="d",
    readonly=True,
    max_chars=4000,
    max_rows=1000,
)


class FakeDatabase:
    """Minimal Database stand-in returning canned rows."""

    def __init__(self, rows: list[tuple[Any, ...]] | None = None) -> None:
        self._rows = rows or []

    def fetch_many(
        self,
        sql: str,
        params: tuple[Any, ...] | None = None,
        max_rows: int | None = None,
    ) -> tuple[list[tuple[Any, ...]], bool]:
        return self._rows, False


def _records(buf: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]


# --------------------------------------------------------------------------- #
# Config parsing
# --------------------------------------------------------------------------- #


def test_audit_log_off_by_default() -> None:
    cfg = Config.from_env(
        {
            "CUBRID_HOST": "h",
            "CUBRID_USER": "u",
            "CUBRID_PASSWORD": "p",
            "CUBRID_DATABASE": "d",
        }
    )
    assert cfg.audit_log is False


def test_audit_log_enabled_via_env() -> None:
    cfg = Config.from_env(
        {
            "CUBRID_HOST": "h",
            "CUBRID_USER": "u",
            "CUBRID_PASSWORD": "p",
            "CUBRID_DATABASE": "d",
            "CUBRID_MCP_AUDIT_LOG": "1",
        }
    )
    assert cfg.audit_log is True


# --------------------------------------------------------------------------- #
# Extraction helpers
# --------------------------------------------------------------------------- #


def test_category_is_leading_keyword_only() -> None:
    assert _category("  select * from users") == "SELECT"
    assert _category("WITH t AS (SELECT 1) SELECT * FROM t") == "WITH"
    assert _category("") is None
    assert _category("123 select") is None
    assert _category(None) is None


def test_identifiers_strict_and_deduplicated() -> None:
    sql = "SELECT * FROM orders o JOIN customers c ON o.cid = c.id JOIN orders x"
    assert _identifiers(sql) == ["orders", "customers"]
    assert _identifiers("") == []
    assert _identifiers(None) == []


def test_identifiers_ignore_literals_and_subqueries() -> None:
    sql = f"SELECT * FROM users WHERE note = '{_SECRET}'"
    ids = _identifiers(sql)
    assert ids == ["users"]
    assert _SECRET not in "".join(ids)


def test_identifiers_ignore_join_inside_literals_and_comments() -> None:
    # A FROM/JOIN appearing inside a string literal or comment must never be
    # surfaced as an identifier (blocker: literal/comment leakage).
    assert _identifiers(f"SELECT * FROM real WHERE x = 'JOIN {_SECRET}'") == ["real"]
    assert _identifiers("SELECT * FROM real -- JOIN commented_out\n") == ["real"]
    assert _identifiers("SELECT * FROM real /* JOIN blocked */ WHERE 1=1") == ["real"]
    assert _SECRET not in "".join(_identifiers(f"SELECT 1 FROM t WHERE note = 'FROM {_SECRET}'"))


# --------------------------------------------------------------------------- #
# AuditLogger behaviour
# --------------------------------------------------------------------------- #


def test_disabled_logger_emits_nothing() -> None:
    buf = io.StringIO()
    audit = AuditLogger(False, stream=buf)
    with audit.track("execute_query", f"SELECT '{_SECRET}'") as outcome:
        outcome.row_count = 1
    audit.record(tool="execute_query", status="ok", sql="SELECT 1")
    assert buf.getvalue() == ""


def test_success_record_shape_and_redaction() -> None:
    buf = io.StringIO()
    audit = AuditLogger(True, stream=buf)
    sql = f"SELECT id FROM users WHERE pw = '{_SECRET}'"
    with audit.track("execute_query", sql) as outcome:
        outcome.row_count = 3
        outcome.truncated = False

    records = _records(buf)
    assert len(records) == 1
    rec = records[0]
    assert rec["tool"] == "execute_query"
    assert rec["status"] == "ok"
    assert rec["category"] == "SELECT"
    assert rec["identifiers"] == ["users"]
    assert rec["row_count"] == 3
    assert rec["truncated"] is False
    assert rec["sql_length"] == len(sql)
    assert isinstance(rec["duration_ms"], int)
    # Redaction: neither the secret literal nor the raw SQL text appears.
    assert _SECRET not in buf.getvalue()
    assert sql not in buf.getvalue()


def test_error_path_is_audited_and_redacted() -> None:
    buf = io.StringIO()
    audit = AuditLogger(True, stream=buf)
    sql = f"DELETE FROM users WHERE pw = '{_SECRET}'"

    with pytest.raises(ValueError):
        with audit.track("execute_query", sql):
            raise ValueError(f"boom {_SECRET}")

    records = _records(buf)
    assert len(records) == 1
    rec = records[0]
    assert rec["status"] == "error"
    assert rec["category"] == "DELETE"
    assert rec["error_type"] == "ValueError"  # sanitized: class name only
    # The exception message embedded the secret; it must not be logged.
    assert _SECRET not in buf.getvalue()


def test_repeated_construction_does_not_double_log() -> None:
    buf1 = io.StringIO()
    AuditLogger(True, stream=buf1)
    buf2 = io.StringIO()
    audit = AuditLogger(True, stream=buf2)
    audit.record(tool="execute_query", status="ok", sql="SELECT 1")
    # The first logger's handler was replaced, so only buf2 receives the record.
    assert buf1.getvalue() == ""
    assert len(_records(buf2)) == 1


def test_preexisting_handler_is_removed_for_stderr_only() -> None:
    # A handler an embedder may have installed (e.g. pointed at stdout) on the
    # dedicated audit logger must be removed so audit output stays stderr-only.
    import logging

    from cubrid_mcp_server.audit import _AUDIT_LOGGER_NAME

    stray = io.StringIO()
    logger = logging.getLogger(_AUDIT_LOGGER_NAME)
    rogue = logging.StreamHandler(stray)
    logger.addHandler(rogue)
    try:
        buf = io.StringIO()
        audit = AuditLogger(True, stream=buf)
        audit.record(tool="execute_query", status="ok", sql="SELECT 1")
        assert stray.getvalue() == ""  # rogue handler was removed
        assert len(_records(buf)) == 1
    finally:
        logger.removeHandler(rogue)


# --------------------------------------------------------------------------- #
# Server integration: stderr-only guarantee
# --------------------------------------------------------------------------- #


def test_execute_query_audits_without_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    buf = io.StringIO()
    config = replace(_BASE_CONFIG, audit_log=True)
    fake = FakeDatabase(rows=[(1,), (2,)])
    monkeypatch.setattr(
        server,
        "_context",
        AppContext.single(config=config, database=fake, audit=AuditLogger(True, stream=buf)),
    )

    sql = f"SELECT id FROM accounts WHERE token = '{_SECRET}'"
    result = server.execute_query(sql)
    assert result["row_count"] == 2

    captured = capsys.readouterr()
    assert captured.out == ""  # stdout is the MCP protocol stream — must stay clean

    records = _records(buf)
    assert len(records) == 1
    assert records[0]["tool"] == "execute_query"
    assert records[0]["identifiers"] == ["accounts"]
    assert _SECRET not in buf.getvalue()


def test_execute_query_no_audit_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.StringIO()
    fake = FakeDatabase(rows=[(1,)])
    # audit_log defaults False; injected logger is disabled and must emit nothing.
    monkeypatch.setattr(
        server,
        "_context",
        AppContext.single(config=_BASE_CONFIG, database=fake, audit=AuditLogger(False, stream=buf)),
    )
    server.execute_query("SELECT 1")
    assert buf.getvalue() == ""
