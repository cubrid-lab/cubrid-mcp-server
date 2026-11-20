#!/usr/bin/env python3
"""Drive cubrid-mcp-server over MCP stdio for the terminal demo recording.

The script starts the server with ``python -m cubrid_mcp_server`` (passing the
``CUBRID_*`` environment), then prints what a real MCP session returns: the
server name from initialization, the tool count and whether ``execute_write``
is offered from tool discovery, the result of ``all_table_names``, and the
error ``execute_query`` returns for a ``DROP TABLE`` (the read-only whitelist
rejects it). The ``>`` lines are labels the script prints before each call;
every value after them comes from the session. Nothing is written to the
database.

Requires a reachable CUBRID (``CUBRID_HOST``, ``CUBRID_PORT``,
``CUBRID_DATABASE``, ``CUBRID_USER``, ``CUBRID_PASSWORD``) and the package
installed (``pip install -e .``). ``demos/record_demo.sh`` records it.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

PAUSE = 1.2


def show(text: str, pause: float = PAUSE) -> None:
    print(text, flush=True)
    time.sleep(pause)


def _extract_table_names(result: object) -> tuple[bool, object]:
    """Return ``(ok, value)`` for the ``all_table_names`` tool result."""
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict) and "result" in structured:
        return True, structured["result"]
    if hasattr(result, "data") and result.data is not None:
        return True, result.data
    return False, None


def _evaluate_drop_result(result: object) -> tuple[int, str]:
    """Verify that ``execute_query`` rejected the destructive SQL probe.

    The recorded security demo must fail closed (non-zero exit status and a
    concise message without echoing raw database output or credentials) if
    ``DROP TABLE`` is unexpectedly accepted or if the client returns a
    malformed tool result.
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
    detail = text.split(": ", 1)[-1].strip()
    if not detail:
        return (
            1,
            "error: execute_query returned a malformed error result (empty error message)",
        )
    return 0, f"rejected: {detail}"


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
        result = await client.call_tool("all_table_names", {})
        ok, tables = _extract_table_names(result)
        if not ok:
            print(
                "error: all_table_names returned a malformed tool result",
                file=sys.stderr,
                flush=True,
            )
            return 1
        show(json.dumps(tables))

        drop = "DROP TABLE product"
        show(f'\n> execute_query("{drop}")', 0.6)
        result = await client.call_tool("execute_query", {"sql": drop}, raise_on_error=False)
        exit_code, line = _evaluate_drop_result(result)
        if exit_code != 0:
            print(line, file=sys.stderr, flush=True)
            return exit_code
        show(line, 2.5)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
