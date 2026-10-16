"""Evaluator-owned checks for the read-only-side-effect-functions task (#295).

``SELECT`` statements that call INCR/DECR or advance a serial change data that
the rollback after a read does not undo, so the read-only check must reject
them while serial reads stay allowed. Offline: the check itself, no database.
Copied into the worktree by ``agent_eval.py run``.
"""

from __future__ import annotations

import pytest

from cubrid_mcp_server import safety


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT INCR(hits) FROM t WHERE id = 1",
        "SELECT decr(hits) FROM t WHERE id = 1",
        "SELECT /* c */ Incr ( hits ) FROM t",
        "SELECT s1.NEXT_VALUE",
        "SELECT s1.nextval",
        "SELECT SERIAL_NEXT_VALUE(s1, 2)",
    ],
)
def test_side_effecting_reads_are_rejected(sql):
    with pytest.raises(safety.UnsafeSQLError):
        safety.ensure_read_only(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT s1.CURRENT_VALUE",
        "SELECT SERIAL_CURRENT_VALUE(s1)",
        "SELECT incr_count, decr_total FROM t",
        "SELECT 'INCR(x)' AS label FROM t",
    ],
)
def test_plain_reads_stay_allowed(sql):
    safety.ensure_read_only(sql)
