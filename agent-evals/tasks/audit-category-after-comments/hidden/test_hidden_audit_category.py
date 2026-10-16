"""Evaluator-owned checks for the audit-category-after-comments task (#179).

A leading comment must not hide a statement's category from the audit record,
and the record must stay redacted. Offline: the audit logger writes to an
in-memory stream. Copied into the worktree by ``agent_eval.py run``.
"""

from __future__ import annotations

import io
import json

import pytest

from cubrid_mcp_server.audit import AuditLogger


def _record(sql):
    stream = io.StringIO()
    AuditLogger(True, stream=stream).record(tool="execute_write", status="ok", sql=sql)
    return json.loads(stream.getvalue().strip().splitlines()[-1]), stream.getvalue()


@pytest.mark.parametrize(
    ("sql", "category"),
    [
        ("/* evaluator */ DELETE FROM t WHERE id = 1", "DELETE"),
        ("-- evaluator\nUPDATE t SET a = 2 WHERE id = 1", "UPDATE"),
        ("/* a */ /* b */\n  INSERT INTO t VALUES (1)", "INSERT"),
        ("SELECT a FROM t", "SELECT"),
        # A write behind a read keyword in a comment is a write (as recorded in #283).
        ("-- SELECT\nDELETE FROM t", "DELETE"),
        ("// SELECT\nINSERT INTO t VALUES (1)", "INSERT"),
        ("/* SELECT */ -- SELECT\n UPDATE t SET a = 1", "UPDATE"),
        ("-- c\r\nSELECT 1", "SELECT"),
        # CUBRID block comments do not nest: the text after the first */ is SQL.
        ("/* /* SELECT */ DROP TABLE t */", "DROP"),
    ],
)
def test_category_reads_past_leading_comments(sql, category):
    record, _ = _record(sql)
    assert str(record["category"]).upper() == category


def test_comments_and_literals_never_reach_the_record():
    record, raw = _record(
        "/* note evaluator-comment */ DELETE FROM t WHERE k = 'evaluator-literal'"
    )
    assert "evaluator-comment" not in raw and "evaluator-literal" not in raw
    assert "sql" not in record


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM real // JOIN evaluator_hidden\n",
        "SELECT * FROM real /* JOIN evaluator_hidden",
        "SELECT * FROM real WHERE x = 'JOIN evaluator_hidden",
    ],
)
def test_comment_and_literal_text_never_reaches_identifiers(sql):
    record, raw = _record(sql)
    assert "evaluator_hidden" not in raw
