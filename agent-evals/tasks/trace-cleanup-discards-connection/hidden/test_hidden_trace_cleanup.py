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
        if sql == "SELECT 1" and self.conn.fail_at == "timeout":
            raise TimeoutError("evaluator query timeout")
        if sql == "SELECT 1" and self.conn.fail_at == "query_and_trace_off":
            raise pycubrid.ProgrammingError("evaluator query error")
        if sql == "SET TRACE OFF" and self.conn.fail_at == "query_and_trace_off":
            raise pycubrid.OperationalError("evaluator trace-off failure")
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
        self.rollbacks = 0

    def cursor(self) -> _Cursor:
        self.cursors += 1
        if self.fail_at == "cursor" and self.cursors == 2:
            raise pycubrid.OperationalError("evaluator cursor failure")
        return _Cursor(self)

    def rollback(self) -> None:
        self.rollbacks += 1
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
    # Cleanup stops at the first failure and does not reconnect by itself.
    assert len(created) == 1, "cleanup opened a new connection"
    if fail_at in ("cursor", "trace_off"):
        assert created[0].rollbacks == 0, "cleanup went on after the first failure"
    _traced(db)
    assert len(created) == 2, "the connection with a failed cleanup was reused"


def test_a_query_timeout_sends_no_cleanup_and_retires_the_connection(monkeypatch):
    db, created = _db(monkeypatch, "timeout")
    with pytest.raises(Exception) as raised:
        _traced(db)
    # The timeout still reaches the caller, as the server's timeout error or the raw one.
    assert "timeout" in type(raised.value).__name__.lower() or isinstance(
        raised.value.__cause__, TimeoutError
    )
    dead = created[0]
    assert "SET TRACE OFF" not in dead.executed and dead.rollbacks == 0
    assert dead.cursors == 1, "a cleanup cursor was opened on the dead socket"
    _traced(db)
    assert len(created) == 2


def test_healthy_cleanup_keeps_the_connection(monkeypatch):
    db, created = _db(monkeypatch, None)
    _traced(db)
    _traced(db)
    assert len(created) == 1


def test_a_query_error_survives_a_failed_cleanup(monkeypatch):
    db, created = _db(monkeypatch, "query_and_trace_off")
    with pytest.raises(Exception) as raised:
        _traced(db)
    # The client sees the query's error (or a sanitized wrapper of it), never the
    # cleanup failure, and the failed session is retired.
    chain, exc = [], raised.value
    while exc is not None and len(chain) < 10:
        chain.append(exc)
        exc = exc.__cause__
    assert any(isinstance(e, pycubrid.ProgrammingError) for e in chain), chain
    assert not any("trace-off" in str(e) for e in chain)
    _traced(db)
    assert len(created) == 2
