#!/usr/bin/env python3
"""Drive cubrid-mcp-server over MCP stdio for the terminal demo recording.

The script starts the server with ``python -m cubrid_mcp_server`` (passing the
``CUBRID_*`` environment), then prints the server name from initialization, the
tool count and whether ``execute_write`` is offered from tool discovery, the
validated table list from ``all_table_names``, and the read-only guard rejection
summary after verifying that ``execute_query`` rejects ``DROP TABLE`` with the
exact error raised by :func:`cubrid_mcp_server.safety.ensure_read_only`. The
``>`` lines are labels printed before each call; server metadata, tool
discovery, and validated table names come from the MCP session, while the
``rejected: ...`` line is emitted from the local ``ensure_read_only`` message
once the server response matches it verbatim (avoiding echoing untrusted error
text). Nothing is written to the database.

Requires a reachable CUBRID (``CUBRID_HOST``, ``CUBRID_PORT``,
``CUBRID_DATABASE``, ``CUBRID_USER``, ``CUBRID_PASSWORD``) and the package
installed (``pip install -e .``). ``demos/record_demo.sh`` records it.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from cubrid_mcp_server.safety import UnsafeSQLError, ensure_read_only

PAUSE = 1.2
DROP_PROBE_SQL = "DROP TABLE product"
_FASTMCP_ERROR_PREFIX = "Error calling tool 'execute_query': "
# Matches unqualified (pre-11.2) or owner-qualified (11.2+) CUBRID table names
# such as ``product`` or ``dba.product``, while rejecting key=value secrets,
# whitespace, control characters, and arbitrary punctuation.
_TABLE_NAME_RE = re.compile(r"[A-Za-z_#][A-Za-z0-9_#$]*(?:\.[A-Za-z_#][A-Za-z0-9_#$]*)?")


def show(text: str, pause: float = PAUSE) -> None:
    print(text, flush=True)
    time.sleep(pause)


def _expected_drop_rejection() -> str:
    """Return the exact ``UnsafeSQLError`` message raised for ``DROP_PROBE_SQL``."""
    try:
        ensure_read_only(DROP_PROBE_SQL)
    except UnsafeSQLError as exc:
        return str(exc)
    raise AssertionError(f"ensure_read_only unexpectedly accepted {DROP_PROBE_SQL!r}")


def _extract_table_names(result: object) -> tuple[bool, list[str] | None]:
    """Return ``(ok, table_names)`` for a validated ``all_table_names`` tool result.

    Requires ``is_error is False`` and a list of safe CUBRID table identifier
    strings (unqualified or ``owner.table``, matched with :data:`_TABLE_NAME_RE`)
    from ``structured_content["result"]`` when present, else ``data``. Malformed
    payloads, error results, ``None``, non-string items, or strings containing
    unexpected characters (e.g. ``CUBRID_PASSWORD=...`` or ``token=abc``) fail
    closed so untrusted or secret-bearing data is never printed to stdout.
    """
    is_error = getattr(result, "is_error", None)
    if is_error is not False:
        return False, None

    structured = getattr(result, "structured_content", None)
    if structured is not None:
        if not isinstance(structured, dict) or "result" not in structured:
            return False, None
        raw: object = structured["result"]
    else:
        raw = getattr(result, "data", None)

    if not isinstance(raw, list):
        return False, None
    for item in raw:
        if not isinstance(item, str) or _TABLE_NAME_RE.fullmatch(item) is None:
            return False, None
    return True, raw


def _evaluate_drop_result(result: object) -> tuple[int, str]:
    """Verify that ``execute_query`` rejected the destructive SQL probe via the read-only guard.

    The recorded security demo must fail closed (non-zero exit status and a
    concise message without echoing raw database output or credentials) if
    ``DROP TABLE`` is unexpectedly accepted, if the server fails with an
    unrelated error (connection/timeout/permission/transport), or if the client
    returns a malformed tool result.

    On the expected rejection path, stdout receives the fixed safe summary
    derived from :func:`cubrid_mcp_server.safety.ensure_read_only` rather than
    echoing untrusted raw text from the MCP result.
    """
    is_error = getattr(result, "is_error", None)
    if not isinstance(is_error, bool):
        return (
            1,
            "error: execute_query returned a malformed tool result (missing boolean is_error)",
        )
    if not is_error:
        return (
            1,
            "error: execute_query unexpectedly accepted DROP TABLE; expected read-only rejection",
        )

    content = getattr(result, "content", None)
    if not isinstance(content, (list, tuple)) or not content:
        return (
            1,
            "error: execute_query returned a malformed error result (missing content)",
        )
    text = getattr(content[0], "text", None)
    if not isinstance(text, str) or not text.strip():
        return (
            1,
            "error: execute_query returned a malformed error result (missing text)",
        )

    expected = _expected_drop_rejection()
    detail = text.strip().removeprefix(_FASTMCP_ERROR_PREFIX).strip()
    if detail != expected:
        return (
            1,
            "error: execute_query failed without the expected read-only SQL guard rejection",
        )
    return 0, f"rejected: {expected}"


async def main() -> int:
    # The MCP stdio client passes only a minimal environment by default, so hand
    # the CUBRID_* settings through explicitly.
    transport = StdioTransport(
        command=sys.executable, args=["-m", "cubrid_mcp_server"], env=dict(os.environ)
    )
    async with Client(transport) as client:
        info = client.server_info
        show(f"connected: {info.name} (MCP stdio)")

        tools = sorted(tool.name for tool in await client.list_tools())
        writes = "offered" if "execute_write" in tools else "not offered (write mode is off)"
        show(f"{len(tools)} tools; execute_write {writes}")

        show("\n> all_table_names()", 0.6)
        result = await client.call_tool("all_table_names", {}, raise_on_error=False)
        ok, tables = _extract_table_names(result)
        if not ok or tables is None:
            print(
                "error: all_table_names returned a malformed or error tool result",
                file=sys.stderr,
                flush=True,
            )
            return 1
        show(json.dumps(tables))

        show(f'\n> execute_query("{DROP_PROBE_SQL}")', 0.6)
        result = await client.call_tool(
            "execute_query", {"sql": DROP_PROBE_SQL}, raise_on_error=False
        )
        exit_code, line = _evaluate_drop_result(result)
        if exit_code != 0:
            print(line, file=sys.stderr, flush=True)
            return exit_code
        show(line, 2.5)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
