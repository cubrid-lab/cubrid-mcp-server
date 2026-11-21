"""Offline tests for demos/mcp_demo.py using a fake FastMCP client/transport.

These tests verify that the recorded demo fails closed when ``execute_query``
unexpectedly accepts ``DROP TABLE``, fails with an unrelated error, or returns
a malformed tool result, and when ``all_table_names`` returns an error or
malformed/secret-bearing payload, while preserving the normal read-only
rejection flow and never leaking database credentials. No real CUBRID server or
destructive SQL execution is involved.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import Client

from cubrid_mcp_server import server

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "demos" / "mcp_demo.py"

_spec = importlib.util.spec_from_file_location("_mcp_demo", SCRIPT)
assert _spec is not None and _spec.loader is not None
mcp_demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mcp_demo)

EXPECTED_REJECTION = mcp_demo._expected_drop_rejection()


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


def _valid_tables_result(tables: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        is_error=False,
        structured_content={"result": ["dba.product"] if tables is None else tables},
        data=None,
    )


def _valid_drop_rejection(*, with_prefix: bool = True) -> SimpleNamespace:
    text = (
        f"Error calling tool 'execute_query': {EXPECTED_REJECTION}"
        if with_prefix
        else EXPECTED_REJECTION
    )
    return SimpleNamespace(is_error=True, content=[SimpleNamespace(text=text)])


async def test_demo_returns_zero_when_drop_table_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret_pw = "super-secret-demo-password-123"
    monkeypatch.setenv("CUBRID_PASSWORD", secret_pw)

    tables_result = _valid_tables_result(
        ["product", "dba.product", "dba.orders_2026", "app_user.tbl$1", "#tmp_items"]
    )
    drop_result = _valid_drop_rejection(with_prefix=True)
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
    assert (
        '["product", "dba.product", "dba.orders_2026", "app_user.tbl$1", "#tmp_items"]'
        in captured.out
    )
    assert f"rejected: {EXPECTED_REJECTION}" in captured.out
    assert captured.err == ""
    assert secret_pw not in captured.out
    assert secret_pw not in captured.err
    assert clients[0].calls == [
        ("all_table_names", {}, False),
        ("execute_query", {"sql": "DROP TABLE product"}, False),
    ]


async def test_demo_fails_nonzero_when_drop_table_is_unexpectedly_accepted(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret_pw = "super-secret-demo-password-456"
    monkeypatch.setenv("CUBRID_PASSWORD", secret_pw)

    tables_result = _valid_tables_result()
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
    assert "rejected:" not in captured.out
    assert "unexpectedly accepted DROP TABLE" in captured.err
    assert secret_pw not in captured.out
    assert secret_pw not in captured.err


@pytest.mark.parametrize(
    "error_text",
    [
        pytest.param(
            "Error calling tool 'execute_query': connection refused (CUBRID_PASSWORD=secret-pw)",
            id="connection-error-with-secret",
        ),
        pytest.param(
            "Error calling tool 'execute_query': query timed out after 30s",
            id="timeout-error",
        ),
        pytest.param(
            "Error calling tool 'execute_query': permission denied for user dba",
            id="permission-error",
        ),
        pytest.param("MCP transport closed unexpectedly", id="transport-error"),
        pytest.param(
            f"Error calling tool 'execute_query': {EXPECTED_REJECTION} leaked=secret-pw",
            id="expected-prefix-with-trailing-secret-payload",
        ),
        pytest.param(
            "Error calling tool 'execute_query': DROP is not permitted in read-only mode",
            id="truncated-guard-message",
        ),
    ],
)
async def test_demo_fails_nonzero_on_unrelated_or_untrusted_is_error_text(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error_text: str,
) -> None:
    """Any is_error=True that is not the exact read-only guard rejection must fail closed
    without echoing untrusted error text or credentials to stdout or stderr."""
    secret_pw = "secret-pw"
    monkeypatch.setenv("CUBRID_PASSWORD", secret_pw)

    _patch_demo_io(
        monkeypatch,
        tables_result=_valid_tables_result(),
        drop_result=SimpleNamespace(is_error=True, content=[SimpleNamespace(text=error_text)]),
    )

    rc = await mcp_demo.main()
    captured = capsys.readouterr()

    assert rc != 0
    assert "rejected:" not in captured.out
    assert "without the expected read-only SQL guard rejection" in captured.err
    assert secret_pw not in captured.out
    assert secret_pw not in captured.err
    assert error_text not in captured.out
    assert error_text not in captured.err


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
    ],
)
async def test_demo_fails_nonzero_on_malformed_drop_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    drop_result: Any,
) -> None:
    secret_pw = "super-secret-demo-password-789"
    monkeypatch.setenv("CUBRID_PASSWORD", secret_pw)

    _patch_demo_io(
        monkeypatch,
        tables_result=_valid_tables_result(),
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


@pytest.mark.parametrize(
    "tables_result",
    [
        pytest.param(None, id="none-result"),
        pytest.param(
            SimpleNamespace(structured_content={"result": ["dba.product"]}, data=None),
            id="missing-is-error",
        ),
        pytest.param(
            SimpleNamespace(
                is_error=True,
                structured_content={"result": ["dba.product"]},
                data=None,
            ),
            id="is-error-true",
        ),
        pytest.param(
            SimpleNamespace(
                is_error=0,
                structured_content={"result": ["dba.product"]},
                data=None,
            ),
            id="non-bool-is-error",
        ),
        pytest.param(
            SimpleNamespace(is_error=False, structured_content=None, data=None),
            id="missing-structured-and-data",
        ),
        pytest.param(
            SimpleNamespace(is_error=False, structured_content={"result": None}, data=None),
            id="structured-result-none",
        ),
        pytest.param(
            SimpleNamespace(
                is_error=False,
                structured_content={"result": {"CUBRID_PASSWORD": "leaked-table-secret"}},
                data=None,
            ),
            id="structured-result-dict-with-secret",
        ),
        pytest.param(
            SimpleNamespace(
                is_error=False,
                structured_content={"result": "dba.product"},
                data=None,
            ),
            id="structured-result-str-not-list",
        ),
        pytest.param(
            SimpleNamespace(
                is_error=False,
                structured_content={"other": ["dba.product"]},
                data=["dba.product"],
            ),
            id="structured-missing-result-key",
        ),
        pytest.param(
            SimpleNamespace(
                is_error=False,
                structured_content=["dba.product"],
                data=None,
            ),
            id="structured-not-dict",
        ),
        pytest.param(
            SimpleNamespace(
                is_error=False,
                structured_content={"result": ["dba.product", 123]},
                data=None,
            ),
            id="non-str-table-item",
        ),
        pytest.param(
            SimpleNamespace(
                is_error=False,
                structured_content={"result": [""]},
                data=None,
            ),
            id="empty-table-name",
        ),
        pytest.param(
            SimpleNamespace(
                is_error=False,
                structured_content={"result": ["CUBRID_PASSWORD=leaked-table-secret"]},
                data=None,
            ),
            id="single-line-secret-env-assignment",
        ),
        pytest.param(
            SimpleNamespace(
                is_error=False,
                structured_content={"result": ["token=abc"]},
                data=None,
            ),
            id="malformed-identifier-key-value",
        ),
        pytest.param(
            SimpleNamespace(
                is_error=False,
                structured_content={"result": ["dba.a.b"]},
                data=None,
            ),
            id="too-many-dots-in-table-name",
        ),
        pytest.param(
            SimpleNamespace(
                is_error=False,
                structured_content={"result": ["dba.product\n"]},
                data=None,
            ),
            id="trailing-newline-in-table-name",
        ),
        pytest.param(
            SimpleNamespace(
                is_error=False,
                structured_content={"result": ["dba.product\nCUBRID_PASSWORD=leaked-table-secret"]},
                data=None,
            ),
            id="multiline-secret-in-table-name",
        ),
        pytest.param(
            SimpleNamespace(
                is_error=False,
                structured_content=None,
                data={"secret": "leaked-table-secret"},
            ),
            id="fallback-data-not-list",
        ),
    ],
)
async def test_demo_fails_nonzero_on_malformed_table_list_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tables_result: Any,
) -> None:
    _patch_demo_io(
        monkeypatch,
        tables_result=tables_result,
        drop_result=_valid_drop_rejection(),
    )

    rc = await mcp_demo.main()
    captured = capsys.readouterr()

    assert rc != 0
    assert "malformed or error" in captured.err
    assert "leaked-table-secret" not in captured.out
    assert "leaked-table-secret" not in captured.err
    assert "token=abc" not in captured.out
    assert "token=abc" not in captured.err


async def test_demo_falls_back_to_data_when_structured_content_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tables_result = SimpleNamespace(is_error=False, structured_content=None, data=["dba.product"])
    drop_result = _valid_drop_rejection(with_prefix=False)
    _patch_demo_io(
        monkeypatch,
        tables_result=tables_result,
        drop_result=drop_result,
    )

    rc = await mcp_demo.main()
    captured = capsys.readouterr()

    assert rc == 0
    assert '["dba.product"]' in captured.out
    assert f"rejected: {EXPECTED_REJECTION}" in captured.out
    assert captured.err == ""


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
            ok, tables = mcp_demo._extract_table_names(tables_result)
            assert ok is True
            assert tables == ["dba.orders", "dba.product"]

            drop_result = await client.call_tool(
                "execute_query", {"sql": mcp_demo.DROP_PROBE_SQL}, raise_on_error=False
            )
            exit_code, line = mcp_demo._evaluate_drop_result(drop_result)
            assert exit_code == 0
            assert line == f"rejected: {EXPECTED_REJECTION}"
