#!/usr/bin/env python3
"""Drive cubrid-mcp-server over MCP stdio for the terminal demo recording.

Every line this prints comes from a real tool call: the script starts the
server with ``python -m cubrid_mcp_server`` (inheriting the ``CUBRID_*``
environment), lists its tools, calls ``all_table_names``, and sends a
``DROP TABLE`` through ``execute_query`` to show the read-only whitelist
rejecting it. Nothing is written to the database.

Requires a reachable CUBRID (``CUBRID_HOST``, ``CUBRID_PORT``,
``CUBRID_DATABASE``, ``CUBRID_USER``, ``CUBRID_PASSWORD``) and the package
installed (``pip install -e .``). ``demos/mcp-demo.tape`` records it with VHS.
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
        show(f"{len(tools)} tools, read-only by default")

        show("\n> all_table_names()", 0.6)
        result = await client.call_tool("all_table_names", {})
        show(json.dumps(result.structured_content.get("result", result.data)))

        drop = "DROP TABLE product"
        show(f'\n> execute_query("{drop}")', 0.6)
        result = await client.call_tool("execute_query", {"sql": drop}, raise_on_error=False)
        message = result.content[0].text if result.content else ""
        status = "rejected" if result.is_error else "accepted"
        show(f"{status}: {message.split(': ', 1)[-1]}", 2.5)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
