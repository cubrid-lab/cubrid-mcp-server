"""Unit tests for cubrid_mcp_server.context.AppContext."""

from __future__ import annotations

from typing import Any

import pytest

from cubrid_mcp_server import context as context_module
from cubrid_mcp_server.config import Config, ConfigError, ConnectionRegistry
from cubrid_mcp_server.context import AppContext
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

_REPORTING_CONFIG = Config(
    host="reporting-db",
    port=33000,
    user="ru",
    password="",
    database="reports",
    readonly=True,
    max_chars=4000,
    max_rows=1000,
)


def test_from_env_builds_a_database_per_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[Config] = []

    class _FakeDatabase:
        def __init__(self, config: Config) -> None:
            built.append(config)

    registry = ConnectionRegistry(configs={"default": _TEST_CONFIG, "reporting": _REPORTING_CONFIG})
    monkeypatch.setattr(ConnectionRegistry, "from_env", classmethod(lambda cls, env=None: registry))
    monkeypatch.setattr(context_module, "Database", _FakeDatabase)

    ctx = AppContext.from_env()
    assert ctx.config_for() is _TEST_CONFIG
    assert ctx.config_for("reporting") is _REPORTING_CONFIG
    assert built == [_TEST_CONFIG, _REPORTING_CONFIG]


def test_single_builds_a_default_only_context() -> None:
    sentinel: Any = object()
    ctx = single_context(config=_TEST_CONFIG, database=sentinel)
    assert ctx.config_for() is _TEST_CONFIG
    assert ctx.database_for() is sentinel
    assert sorted(ctx.registry.configs) == ["default"]


def test_database_for_selects_named_connection() -> None:
    default_db: Any = object()
    reporting_db: Any = object()
    registry = ConnectionRegistry(configs={"default": _TEST_CONFIG, "reporting": _REPORTING_CONFIG})
    ctx = AppContext(
        registry=registry,
        databases={"default": default_db, "reporting": reporting_db},
    )
    assert ctx.database_for() is default_db
    assert ctx.database_for("reporting") is reporting_db
    # Selection is case-insensitive and whitespace-tolerant.
    assert ctx.database_for("  REPORTING ") is reporting_db
    assert ctx.config_for("reporting") is _REPORTING_CONFIG


def test_database_for_unknown_connection_raises() -> None:
    ctx = single_context(config=_TEST_CONFIG, database=object())  # type: ignore[arg-type]
    with pytest.raises(ConfigError) as excinfo:
        ctx.database_for("nope")
    assert "unknown connection" in str(excinfo.value)
    assert "default" in str(excinfo.value)


def test_close_closes_every_database() -> None:
    closed: list[str] = []

    class _FakeDatabase:
        def __init__(self, label: str) -> None:
            self.label = label

        def close(self) -> None:
            closed.append(self.label)

    registry = ConnectionRegistry(configs={"default": _TEST_CONFIG, "reporting": _REPORTING_CONFIG})
    ctx = AppContext(
        registry=registry,
        databases={"default": _FakeDatabase("default"), "reporting": _FakeDatabase("reporting")},  # type: ignore[dict-item]
    )
    ctx.close()
    assert sorted(closed) == ["default", "reporting"]


def test_close_closes_all_even_when_one_fails() -> None:
    closed: list[str] = []

    class _FailingDatabase:
        def close(self) -> None:
            closed.append("failing")
            raise RuntimeError("boom")

    class _OkDatabase:
        def close(self) -> None:
            closed.append("ok")

    registry = ConnectionRegistry(configs={"default": _TEST_CONFIG, "reporting": _REPORTING_CONFIG})
    ctx = AppContext(
        registry=registry,
        databases={"default": _FailingDatabase(), "reporting": _OkDatabase()},  # type: ignore[dict-item]
    )
    with pytest.raises(RuntimeError, match="boom"):
        ctx.close()
    # The second database is still closed despite the first raising.
    assert sorted(closed) == ["failing", "ok"]


def test_audit_for_is_per_connection() -> None:
    from dataclasses import replace

    default_cfg = replace(_TEST_CONFIG, audit_log=False)
    reporting_cfg = replace(_REPORTING_CONFIG, audit_log=True)
    registry = ConnectionRegistry(configs={"default": default_cfg, "reporting": reporting_cfg})
    ctx = AppContext(
        registry=registry,
        databases={"default": object(), "reporting": object()},  # type: ignore[dict-item]
    )
    # Each connection honours its own MCP_AUDIT_LOG (#137).
    assert ctx.audit_for().enabled is False
    assert ctx.audit_for("reporting").enabled is True
    # Selection is case-insensitive and whitespace-tolerant, matching database_for.
    assert ctx.audit_for("  REPORTING ").enabled is True
    # The default audit attribute points at the default connection's logger.
    assert ctx.audit is ctx.audit_for()


def test_audit_for_unknown_connection_raises() -> None:
    ctx = single_context(config=_TEST_CONFIG, database=object())  # type: ignore[arg-type]
    with pytest.raises(ConfigError) as excinfo:
        ctx.audit_for("nope")
    assert "unknown connection" in str(excinfo.value)


def test_injected_audit_is_reused_for_default_slot() -> None:
    from cubrid_mcp_server.audit import AuditLogger

    injected = AuditLogger(False)
    ctx = single_context(config=_TEST_CONFIG, database=object(), audit=injected)  # type: ignore[arg-type]
    assert ctx.audit is injected
    assert ctx.audit_for() is injected


def test_audit_for_raises_runtime_error_when_audits_is_unset() -> None:
    ctx = single_context(config=_TEST_CONFIG, database=object())  # type: ignore[arg-type]
    object.__setattr__(ctx, "audits", None)
    with pytest.raises(RuntimeError, match=r"AppContext\.audits is not initialized"):
        ctx.audit_for()


def test_close_logs_suppressed_failures_without_secrets(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "s3cret-dsn-password"

    class _FailingDatabase:
        def __init__(self, message: str, error: type[Exception]) -> None:
            self.message = message
            self.error = error

        def close(self) -> None:
            raise self.error(self.message)

    registry = ConnectionRegistry(configs={"default": _TEST_CONFIG, "reporting": _REPORTING_CONFIG})
    first = _FailingDatabase(f"first cubrid://u:{secret}@h/d", RuntimeError)
    ctx = AppContext(
        registry=registry,
        databases={
            "default": first,  # type: ignore[dict-item]
            "reporting": _FailingDatabase(f"second cubrid://u:{secret}@h/d", OSError),  # type: ignore[dict-item]
        },
    )
    with caplog.at_level("WARNING", logger="cubrid_mcp_server.context"):
        with pytest.raises(RuntimeError) as excinfo:
            ctx.close()
    # The first error is raised unchanged.
    assert str(excinfo.value) == f"first cubrid://u:{secret}@h/d"
    records = [r for r in caplog.records if r.name == "cubrid_mcp_server.context"]
    assert len(records) == 1
    assert records[0].levelname == "WARNING"
    assert records[0].exc_info is None
    message = records[0].getMessage()
    assert "reporting" in message
    assert "OSError" in message
    assert secret not in message
    assert "second" not in message
