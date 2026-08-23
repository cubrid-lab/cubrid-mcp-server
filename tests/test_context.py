"""Unit tests for cubrid_mcp_server.context.AppContext."""

from __future__ import annotations

from typing import Any

import pytest

from cubrid_mcp_server import context as context_module
from cubrid_mcp_server.config import Config
from cubrid_mcp_server.context import AppContext

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


def test_from_env_builds_config_and_database(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[Config] = []

    class _FakeDatabase:
        def __init__(self, config: Config) -> None:
            built.append(config)

    monkeypatch.setattr(Config, "from_env", classmethod(lambda cls: _TEST_CONFIG))
    monkeypatch.setattr(context_module, "Database", _FakeDatabase)

    ctx = AppContext.from_env()
    assert ctx.config is _TEST_CONFIG
    assert built == [_TEST_CONFIG]


def test_close_delegates_to_database() -> None:
    closed: list[bool] = []

    class _FakeDatabase:
        def close(self) -> None:
            closed.append(True)

    ctx = AppContext(config=_TEST_CONFIG, database=_FakeDatabase())  # type: ignore[arg-type]
    ctx.close()
    assert closed == [True]


def test_appcontext_holds_injected_instances() -> None:
    sentinel: Any = object()
    ctx = AppContext(config=_TEST_CONFIG, database=sentinel)
    assert ctx.database is sentinel
    assert ctx.config is _TEST_CONFIG
