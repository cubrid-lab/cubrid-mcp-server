"""Offline tests for demos/mcp_demo.py using a fake FastMCP client/transport.

Verifies that the recorded demo fails closed when ``execute_query`` accepts
``DROP TABLE``, fails with an unrelated error, or returns a malformed result,
and when ``all_table_names`` returns an error or non-list-of-strings payload,
without leaking database credentials or executing destructive SQL.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import Client

from cubrid_mcp_server import server

SCRIPT = Path(__file__).resolve().parent.parent / "demos" / "mcp_demo.py"
_spec = importlib.util.spec_from_file_location("_mcp_demo", SCRIPT)
assert _spec is not None and _spec.loader is not None
mcp_demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mcp_demo)

EXPECTED_REJECTION = mcp_demo._expected_drop_rejection()


class _FakeTransport:
    def __init__(self, *, command: str, args: list[str], env: dict[str, str]) -> None:
        self.command, self.args, self.env = command, args, env


class _FakeClient:
    def __init__(self, transport: Any, *, tables_result: Any, drop_result: Any) -> None:
        self.transport = transport
        self.server_info = SimpleNamespace(name="cubrid-mcp-server")
        self._tables_result = tables_result
        self._drop_result = drop_result
        self.calls: list[tuple[str, dict[str, Any], bool]] = []

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def list_tools(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(name="all_table_names"), SimpleNamespace(name="execute_query")]

    async def call_tool(
        self, name: str, arguments: dict[str, Any], *, raise_on_error: bool = True
    ) -> Any:
        self.calls.append((name, arguments, raise_on_error))
        if name == "all_table_names":
            return self._tables_result
        if name == "execute_query":
            return self._drop_result
        raise AssertionError(f"unexpected tool call: {name}")


def _patch_demo_io(
    monkeypatch: pytest.MonkeyPatch, *, tables_result: Any, drop_result: Any
) -> list[_FakeClient]:
    created: list[_FakeClient] = []

    def _make_client(transport: Any) -> _FakeClient:
        client = _FakeClient(transport, tables_result=tables_result, drop_result=drop_result)
        created.append(client)
        return client

    monkeypatch.setattr(mcp_demo, "StdioTransport", _FakeTransport)
    monkeypatch.setattr(mcp_demo, "Client", _make_client)
    monkeypatch.setattr(mcp_demo.time, "sleep", lambda _seconds: None)
    return created


def _tables_ok(tables: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        is_error=False,
        structured_content={"result": ["dba.product"] if tables is None else tables},
        data=None,
    )


def _drop_rejected(
    detail: str = EXPECTED_REJECTION, *, with_prefix: bool = True
) -> SimpleNamespace:
    text = f"Error calling tool 'execute_query': {detail}" if with_prefix else detail
    return SimpleNamespace(is_error=True, content=[SimpleNamespace(text=text)])


async def test_demo_returns_zero_when_drop_table_is_rejected(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret_pw = "super-secret-demo-password-123"
    monkeypatch.setenv("CUBRID_PASSWORD", secret_pw)
    tables = ["product", "dba.product", "제품", "my table", "dba.order-items"]
    clients = _patch_demo_io(
        monkeypatch, tables_result=_tables_ok(tables), drop_result=_drop_rejected()
    )

    rc = await mcp_demo.main()
    captured = capsys.readouterr()

    assert rc == 0
    assert "connected: cubrid-mcp-server (MCP stdio)" in captured.out
    assert "2 tools; execute_write not offered (write mode is off)" in captured.out
    assert json.dumps(tables) in captured.out
    assert f"rejected: {EXPECTED_REJECTION}" in captured.out
    assert captured.err == ""
    assert secret_pw not in captured.out and secret_pw not in captured.err
    assert clients[0].calls == [
        ("all_table_names", {}, False),
        ("execute_query", {"sql": "DROP TABLE product"}, False),
    ]


async def test_demo_accepts_reworded_read_only_rejection_with_stable_prefix(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Matching the stable prefix avoids coupling the demo to exact READ_ONLY_KEYWORDS wording,
    while stdout still emits the fixed local summary rather than raw server text."""
    reworded = "DROP is not permitted in read-only mode (allowed statements: SELECT)"
    _patch_demo_io(
        monkeypatch,
        tables_result=SimpleNamespace(
            is_error=False, structured_content=None, data=["dba.product"]
        ),
        drop_result=_drop_rejected(reworded, with_prefix=False),
    )

    rc = await mcp_demo.main()
    captured = capsys.readouterr()

    assert rc == 0
    assert '["dba.product"]' in captured.out
    assert f"rejected: {EXPECTED_REJECTION}" in captured.out
    assert reworded not in captured.out
    assert captured.err == ""


async def test_demo_fails_nonzero_when_drop_table_is_unexpectedly_accepted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret_pw = "super-secret-demo-password-456"
    monkeypatch.setenv("CUBRID_PASSWORD", secret_pw)
    _patch_demo_io(
        monkeypatch,
        tables_result=_tables_ok(),
        drop_result=SimpleNamespace(
            is_error=False, content=[SimpleNamespace(text=f"ok leaked={secret_pw}")]
        ),
    )

    rc = await mcp_demo.main()
    captured = capsys.readouterr()

    assert rc != 0
    assert "accepted:" not in captured.out and "rejected:" not in captured.out
    assert "unexpectedly accepted DROP TABLE" in captured.err
    assert secret_pw not in captured.out and secret_pw not in captured.err


@pytest.mark.parametrize(
    "error_text",
    [
        "Error calling tool 'execute_query': connection refused (CUBRID_PASSWORD=secret-pw)",
        "Error calling tool 'execute_query': query timed out after 30s",
        "Error calling tool 'execute_query': permission denied for user dba",
        "MCP transport closed unexpectedly",
    ],
)
async def test_demo_fails_nonzero_on_unrelated_is_error_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], error_text: str
) -> None:
    monkeypatch.setenv("CUBRID_PASSWORD", "secret-pw")
    _patch_demo_io(
        monkeypatch,
        tables_result=_tables_ok(),
        drop_result=SimpleNamespace(is_error=True, content=[SimpleNamespace(text=error_text)]),
    )

    rc = await mcp_demo.main()
    captured = capsys.readouterr()

    assert rc != 0
    assert "rejected:" not in captured.out
    assert "without the expected read-only SQL guard rejection" in captured.err
    assert "secret-pw" not in captured.out and "secret-pw" not in captured.err
    assert error_text not in captured.out and error_text not in captured.err


@pytest.mark.parametrize(
    "drop_result",
    [
        None,
        SimpleNamespace(),
        SimpleNamespace(is_error="true", content=[]),
        SimpleNamespace(is_error=True, content=[]),
        SimpleNamespace(is_error=True, content=[SimpleNamespace(text="   ")]),
    ],
)
async def test_demo_fails_nonzero_on_malformed_drop_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], drop_result: Any
) -> None:
    _patch_demo_io(monkeypatch, tables_result=_tables_ok(), drop_result=drop_result)

    rc = await mcp_demo.main()
    captured = capsys.readouterr()

    assert rc != 0
    assert "rejected:" not in captured.out
    assert "malformed" in captured.err


@pytest.mark.parametrize(
    "tables_result",
    [
        None,
        SimpleNamespace(is_error=True, structured_content={"result": ["dba.product"]}, data=None),
        SimpleNamespace(is_error=0, structured_content={"result": ["dba.product"]}, data=None),
        SimpleNamespace(is_error=False, structured_content={"result": None}, data=None),
        SimpleNamespace(is_error=False, structured_content={"other": ["dba.product"]}, data=None),
        SimpleNamespace(is_error=False, structured_content={"result": "dba.product"}, data=None),
        SimpleNamespace(
            is_error=False, structured_content={"result": ["dba.product", 123]}, data=None
        ),
        SimpleNamespace(is_error=False, structured_content=None, data={"secret": "leaked-secret"}),
    ],
)
async def test_demo_fails_nonzero_on_malformed_table_list_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tables_result: Any
) -> None:
    _patch_demo_io(monkeypatch, tables_result=tables_result, drop_result=_drop_rejected())

    rc = await mcp_demo.main()
    captured = capsys.readouterr()

    assert rc != 0
    assert "malformed or error" in captured.err
    assert "leaked-secret" not in captured.out and "leaked-secret" not in captured.err


async def test_demo_validators_match_real_fastmcp_server_responses() -> None:
    """Verify _extract_table_names and _evaluate_drop_result against the real FastMCP server."""
    db = MagicMock()
    db.owner_qualified_names.return_value = True
    db.fetch_all.return_value = [("orders", "DBA"), ("product", "DBA")]
    cfg = MagicMock(readonly=True, max_sql_length=10_000)
    audit = MagicMock()
    audit.track.return_value.__enter__.return_value = MagicMock()
    audit.track.return_value.__exit__.return_value = False

    with (
        patch.object(server, "_db", return_value=db),
        patch.object(server, "_cfg", return_value=cfg),
        patch.object(server, "_audit", return_value=audit),
    ):
        async with Client(server.mcp) as client:
            tables_result = await client.call_tool("all_table_names", {}, raise_on_error=False)
            assert mcp_demo._extract_table_names(tables_result) == (
                True,
                ["dba.orders", "dba.product"],
            )

            drop_result = await client.call_tool(
                "execute_query", {"sql": mcp_demo.DROP_PROBE_SQL}, raise_on_error=False
            )
            assert mcp_demo._evaluate_drop_result(drop_result) == (
                0,
                f"rejected: {EXPECTED_REJECTION}",
            )
