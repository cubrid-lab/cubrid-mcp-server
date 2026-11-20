"""Offline tests for demos/mcp_demo.py using a fake FastMCP client/transport.

These tests verify that the recorded demo fails closed when ``execute_query``
unexpectedly accepts ``DROP TABLE`` or returns a malformed tool result, while
preserving the normal read-only rejection flow and never leaking database
credentials. No real CUBRID server or destructive SQL execution is involved.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "demos" / "mcp_demo.py"

_spec = importlib.util.spec_from_file_location("_mcp_demo", SCRIPT)
assert _spec is not None and _spec.loader is not None
mcp_demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mcp_demo)


class _FakeTransport:
    """Capture StdioTransport arguments without spawning a subprocess."""

    def __init__(self, *, command: str, args: list[str], env: dict[str, str]) -> None:
        self.command = command
        self.args = args
        self.env = env


class _FakeClient:
    """Minimal async FastMCP Client double for offline demo verification."""

    def __init__(
        self,
        transport: Any,
        *,
        tables_result: Any,
        drop_result: Any,
        tool_names: list[str] | None = None,
    ) -> None:
        self.transport = transport
        self.server_info = SimpleNamespace(name="cubrid-mcp-server")
        self._tables_result = tables_result
        self._drop_result = drop_result
        self._tool_names = tool_names or ["all_table_names", "execute_query"]
        self.calls: list[tuple[str, dict[str, Any], bool]] = []

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def list_tools(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(name=name) for name in self._tool_names]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        raise_on_error: bool = True,
    ) -> Any:
        self.calls.append((name, arguments, raise_on_error))
        if name == "all_table_names":
            return self._tables_result
        if name == "execute_query":
            return self._drop_result
        raise AssertionError(f"unexpected tool call: {name}")


def _patch_demo_io(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tables_result: Any,
    drop_result: Any,
    tool_names: list[str] | None = None,
) -> list[_FakeClient]:
    created_clients: list[_FakeClient] = []

    def _make_client(transport: Any) -> _FakeClient:
        client = _FakeClient(
            transport,
            tables_result=tables_result,
            drop_result=drop_result,
            tool_names=tool_names,
        )
        created_clients.append(client)
        return client

    monkeypatch.setattr(mcp_demo, "StdioTransport", _FakeTransport)
    monkeypatch.setattr(mcp_demo, "Client", _make_client)
    monkeypatch.setattr(mcp_demo.time, "sleep", lambda _seconds: None)
    return created_clients


async def test_demo_returns_zero_when_drop_table_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret_pw = "super-secret-demo-password-123"
    monkeypatch.setenv("CUBRID_PASSWORD", secret_pw)

    tables_result = SimpleNamespace(
        structured_content={"result": ["dba.product", "dba.orders"]},
        data=None,
    )
    drop_result = SimpleNamespace(
        is_error=True,
        content=[
            SimpleNamespace(
                text="Error calling tool 'execute_query': DROP is not permitted in read-only mode"
            )
        ],
    )
    clients = _patch_demo_io(
        monkeypatch,
        tables_result=tables_result,
        drop_result=drop_result,
    )

    rc = await mcp_demo.main()
    captured = capsys.readouterr()

    assert rc == 0
    assert "connected: cubrid-mcp-server (MCP stdio)" in captured.out
    assert "2 tools; execute_write not offered (write mode is off)" in captured.out
    assert '["dba.product", "dba.orders"]' in captured.out
    assert "rejected: DROP is not permitted in read-only mode" in captured.out
    assert captured.err == ""
    assert secret_pw not in captured.out
    assert secret_pw not in captured.err
    assert clients[0].calls == [
        ("all_table_names", {}, True),
        ("execute_query", {"sql": "DROP TABLE product"}, False),
    ]


async def test_demo_fails_nonzero_when_drop_table_is_unexpectedly_accepted(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret_pw = "super-secret-demo-password-456"
    monkeypatch.setenv("CUBRID_PASSWORD", secret_pw)

    tables_result = SimpleNamespace(
        structured_content={"result": ["dba.product"]},
        data=None,
    )
    drop_result = SimpleNamespace(
        is_error=False,
        content=[SimpleNamespace(text=f"ok leaked={secret_pw}")],
    )
    _patch_demo_io(
        monkeypatch,
        tables_result=tables_result,
        drop_result=drop_result,
    )

    rc = await mcp_demo.main()
    captured = capsys.readouterr()

    assert rc != 0
    assert "accepted:" not in captured.out
    assert "unexpectedly accepted DROP TABLE" in captured.err
    assert secret_pw not in captured.out
    assert secret_pw not in captured.err


@pytest.mark.parametrize(
    "drop_result",
    [
        pytest.param(None, id="none-result"),
        pytest.param(SimpleNamespace(), id="missing-is-error"),
        pytest.param(SimpleNamespace(is_error="true", content=[]), id="non-bool-is-error"),
        pytest.param(SimpleNamespace(is_error=1, content=[]), id="int-is-error"),
        pytest.param(SimpleNamespace(is_error=True, content=None), id="none-content"),
        pytest.param(SimpleNamespace(is_error=True, content=[]), id="empty-content"),
        pytest.param(
            SimpleNamespace(is_error=True, content=[SimpleNamespace()]),
            id="missing-text-attr",
        ),
        pytest.param(
            SimpleNamespace(is_error=True, content=[SimpleNamespace(text=123)]),
            id="non-str-text",
        ),
        pytest.param(
            SimpleNamespace(is_error=True, content=[SimpleNamespace(text="   ")]),
            id="blank-text",
        ),
        pytest.param(
            SimpleNamespace(is_error=True, content=[SimpleNamespace(text="error:   ")]),
            id="empty-detail-after-colon",
        ),
    ],
)
async def test_demo_fails_nonzero_on_malformed_drop_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    drop_result: Any,
) -> None:
    secret_pw = "super-secret-demo-password-789"
    monkeypatch.setenv("CUBRID_PASSWORD", secret_pw)

    tables_result = SimpleNamespace(
        structured_content={"result": ["dba.product"]},
        data=None,
    )
    _patch_demo_io(
        monkeypatch,
        tables_result=tables_result,
        drop_result=drop_result,
    )

    rc = await mcp_demo.main()
    captured = capsys.readouterr()

    assert rc != 0
    assert "accepted:" not in captured.out
    assert "rejected:" not in captured.out
    assert "malformed" in captured.err
    assert secret_pw not in captured.out
    assert secret_pw not in captured.err


async def test_demo_fails_nonzero_on_malformed_table_list_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tables_result = SimpleNamespace(structured_content=None, data=None)
    drop_result = SimpleNamespace(
        is_error=True,
        content=[SimpleNamespace(text="DROP is not permitted in read-only mode")],
    )
    _patch_demo_io(
        monkeypatch,
        tables_result=tables_result,
        drop_result=drop_result,
    )

    rc = await mcp_demo.main()
    captured = capsys.readouterr()

    assert rc != 0
    assert "malformed" in captured.err


async def test_demo_falls_back_to_data_when_structured_content_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tables_result = SimpleNamespace(structured_content=None, data=["dba.product"])
    drop_result = SimpleNamespace(
        is_error=True,
        content=[SimpleNamespace(text="DROP is not permitted in read-only mode")],
    )
    _patch_demo_io(
        monkeypatch,
        tables_result=tables_result,
        drop_result=drop_result,
    )

    rc = await mcp_demo.main()
    captured = capsys.readouterr()

    assert rc == 0
    assert '["dba.product"]' in captured.out
    assert "rejected: DROP is not permitted in read-only mode" in captured.out
    assert captured.err == ""
