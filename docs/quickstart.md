# Quick Start

Run the CUBRID MCP server and connect an LLM client in a few minutes.

## 1. Configure

Set the required environment variables:

```bash
export CUBRID_HOST=localhost
export CUBRID_PORT=33000        # optional, default: 33000
export CUBRID_USER=readonly_user   # a CUBRID user with SELECT-only grants (see Security Model)
export CUBRID_PASSWORD=secret
export CUBRID_DATABASE=mydb
```

Optional settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `CUBRID_MCP_READONLY` | `1` | Enforce read-only SQL whitelist |
| `CUBRID_MCP_MAX_CHARS` | `4000` | Max characters in query output |
| `CUBRID_MCP_MAX_ROWS` | `1000` | Max rows returned by `execute_query` before truncation |
| `CUBRID_MCP_MAX_SQL_LENGTH` | `65536` | Max length (characters) of a submitted SQL statement |
| `CUBRID_MCP_QUERY_TIMEOUT` | `30` | Per-statement socket read timeout in seconds |
| `CUBRID_MCP_AUDIT_LOG` | `0` | Opt-in audit logging (see Security Model) |
| `CUBRID_MCP_WRITE` | `0` | Opt-in write mode (registers `execute_write`) |

## 2. Run

From PyPI with [`uvx`](https://docs.astral.sh/uv/guides/tools/):

```bash
uvx cubrid-mcp-server
```

Or with `pipx`:

```bash
pipx run cubrid-mcp-server
```

Or from source:

```bash
git clone https://github.com/cubrid-lab/cubrid-mcp-server.git
cd cubrid-mcp-server
python -m venv .venv && source .venv/bin/activate
pip install -e .
cubrid-mcp-server
```

The server speaks MCP over stdio: it is not meant to be run standalone in a terminal, but registered as a server in an MCP client.

## 3. Connect a client

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cubrid": {
      "command": "uvx",
      "args": ["cubrid-mcp-server"],
      "env": {
        "CUBRID_HOST": "localhost",
        "CUBRID_USER": "readonly_user",
        "CUBRID_PASSWORD": "secret",
        "CUBRID_DATABASE": "mydb"
      }
    }
  }
}
```

### Claude Code

Add to `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "cubrid": {
      "command": "uvx",
      "args": ["cubrid-mcp-server"],
      "env": {
        "CUBRID_HOST": "localhost",
        "CUBRID_USER": "readonly_user",
        "CUBRID_PASSWORD": "secret",
        "CUBRID_DATABASE": "mydb"
      }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "cubrid": {
      "command": "uvx",
      "args": ["cubrid-mcp-server"],
      "env": {
        "CUBRID_HOST": "localhost",
        "CUBRID_USER": "readonly_user",
        "CUBRID_PASSWORD": "secret",
        "CUBRID_DATABASE": "mydb"
      }
    }
  }
}
```

## 4. First queries

With the client connected, try:

1. *"이 DB에 어떤 테이블이 있어?" / "What tables are in this database?"* — the client calls `all_table_names`.
2. *"Show me the structure of the `orders` table"* — `describe_table` returns columns, primary key, and indexes.
3. *"What are the top 5 products by revenue?"* — `execute_query` runs the `SELECT` and returns truncated, context-safe output.

If you ask the model to delete a table, the read-only whitelist rejects it — that enforcement lives in the server, not in the prompt. See the [Security Model](SECURITY_MODEL.md) for the full design.

## Next steps

- [Tools reference](TOOLS.md) — every tool, resource, and prompt
- [Multi-Connection](MULTI_CONNECTION.md) — serve several databases from one process
- [Troubleshooting](TROUBLESHOOTING.md) — when something does not connect
