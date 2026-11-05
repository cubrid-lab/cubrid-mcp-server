"""Console entry: ``python -m cubrid_mcp_server``."""

from __future__ import annotations

import sys

from cubrid_mcp_server.server import main

if __name__ == "__main__":
    main(sys.argv[1:])
