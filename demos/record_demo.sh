#!/usr/bin/env bash
# Record docs/demo.gif from a real MCP stdio session.
#
# The recording is the terminal output of demos/mcp_demo.py, an MCP client that
# starts the server and calls its tools. The first line is the command, printed
# by this script, and the ">" lines are labels printed by the client; every
# value after them (server name, tool count, table list, rejection message)
# comes from the real MCP session. It is not a Claude Desktop recording.
#
# Requires asciinema 2.x and agg (https://github.com/asciinema/agg) on PATH, a
# reachable CUBRID with a few user tables, the CUBRID_* variables exported
# (CUBRID_HOST, CUBRID_PORT, CUBRID_DATABASE, CUBRID_USER, CUBRID_PASSWORD),
# and the package installed in the active Python (pip install -e .).
#
#   demos/record_demo.sh            # writes docs/demo.gif
set -euo pipefail
cd "$(dirname "$0")/.."

cast="$(mktemp --suffix=.cast)"
status="$(mktemp)"
trap 'rm -f "$cast" "$status"' EXIT

# Server logs go to stderr; keep them out of the recording. asciinema does not
# pass on the recorded command's exit status, so it is written to a file and
# checked before docs/demo.gif is overwritten.
asciinema rec --quiet --overwrite --cols 108 --rows 10 \
  --command "printf '\$ python demos/mcp_demo.py\n'; python demos/mcp_demo.py 2>/dev/null; echo \$? > '$status'" \
  "$cast"
if [ "$(cat "$status")" != "0" ]; then
  echo "demos/mcp_demo.py failed (exit status '$(cat "$status")'); docs/demo.gif not changed" >&2
  exit 1
fi
agg --theme github-dark --font-size 14 --last-frame-duration 4 "$cast" docs/demo.gif
