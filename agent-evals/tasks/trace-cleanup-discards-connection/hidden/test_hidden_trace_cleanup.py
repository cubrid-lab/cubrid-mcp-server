"""Evaluator-owned checks for the trace-cleanup-discards-connection task (#264).

If cleaning up after a traced statement fails, the shared connection may still
have tracing on or a transaction open; the next call must not reuse it, and the
traced statement's own result must still come back. A fake driver connection is
used; no database. Copied into the worktree by ``agent_eval.py run``.
"""

from __future__ import annotations

from typing import Any

import pycubrid
import pytest

from cubrid_mcp_server.config import Config
from cubrid_mcp_server.database import Database

CONFIG = Config.from_env(
    {"CUBRID_HOST": "h", "CUBRID_USER": "u", "CUBRID_PASSWORD": "p", "CUBRID_DATABASE": "d"}
)


class _Cursor:
    def __init__(self, conn: "_Conn") -> None:
        self.conn = conn

    def execute(self, sql: str, params: Any = ()) -> None:
        self.conn.executed.append(sql)
        if sql == "SET TRACE OFF" and self.conn.fail_at == "trace_off":
            raise pycubrid.OperationalError("evaluator trace-off failure")

    def fetchall(self) -> list[tuple[str]]:
        return [("plan",)]

    def close(self) -> None:
        pass


class _Conn:
    def __init__(self, fail_at: str | None) -> None:
        self.fail_at = fail_at
        self.executed: list[str] = []
        self.cursors = 0

    def cursor(self) -> _Cursor:
        self.cursors += 1
        if self.fail_at == "cursor" and self.cursors == 2:
            raise pycubrid.OperationalError("evaluator cursor failure")
        return _Cursor(self)

    def rollback(self) -> None:
        if self.fail_at == "rollback":
            raise pycubrid.OperationalError("evaluator rollback failure")

    def close(self) -> None:
        pass


def _db(monkeypatch: pytest.MonkeyPatch, fail_at: str | None) -> tuple[Database, list[_Conn]]:
    created: list[_Conn] = []

    def connect(**_: Any) -> _Conn:
        created.append(_Conn(fail_at if not created else None))
        return created[-1]

    monkeypatch.setattr(pycubrid, "connect", connect)
    return Database(CONFIG), created


def _traced(db: Database) -> list[tuple[str]]:
    with db.trace_enabled() as cursor:
        cursor.execute("SELECT 1", ())
        return cursor.fetchall()


@pytest.mark.parametrize("fail_at", ["cursor", "trace_off", "rollback"])
def test_failed_cleanup_retires_the_connection(monkeypatch, fail_at):
    db, created = _db(monkeypatch, fail_at)
    assert _traced(db) == [("plan",)]
    _traced(db)
    assert len(created) == 2, "the connection with a failed cleanup was reused"


def test_healthy_cleanup_keeps_the_connection(monkeypatch):
    db, created = _db(monkeypatch, None)
    _traced(db)
    _traced(db)
    assert len(created) == 1
