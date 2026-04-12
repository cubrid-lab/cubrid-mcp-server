# cubrid-mcp-server

A [Model Context Protocol](https://modelcontextprotocol.io) server for [CUBRID](https://www.cubrid.org/), enabling LLMs to safely inspect schemas and execute read-only queries via [pycubrid](https://pypi.org/project/pycubrid/).

## Features

| Tool | Description |
|------|-------------|
| `all_table_names` | List every user table in the database |
| `filter_table_names` | Substring search over table names |
| `schema_definitions` | Column types, nullability, defaults, and primary key info |
| `execute_query` | Run read-only SQL with automatic output truncation |

## Quick Start

### Install

```bash
pip install cubrid-mcp-server
```

Or install from source:

```bash
git clone https://github.com/paikend/cubrid-mcp-server.git
cd cubrid-mcp-server
pip install -e .
```

### Configure

Set the required environment variables:

```bash
export CUBRID_HOST=localhost
export CUBRID_PORT=33000        # optional, default: 33000
export CUBRID_USER=dba
export CUBRID_PASSWORD=secret
export CUBRID_DATABASE=mydb
```

Optional settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `CUBRID_MCP_READONLY` | `1` | Enforce read-only SQL whitelist |
| `CUBRID_MCP_MAX_CHARS` | `4000` | Max characters in query output |

### Run

```bash
cubrid-mcp-server
```

## MCP Client Integration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cubrid": {
      "command": "cubrid-mcp-server",
      "env": {
        "CUBRID_HOST": "localhost",
        "CUBRID_USER": "dba",
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
      "command": "cubrid-mcp-server",
      "env": {
        "CUBRID_HOST": "localhost",
        "CUBRID_USER": "dba",
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
      "command": "cubrid-mcp-server",
      "env": {
        "CUBRID_HOST": "localhost",
        "CUBRID_USER": "dba",
        "CUBRID_PASSWORD": "secret",
        "CUBRID_DATABASE": "mydb"
      }
    }
  }
}
```

## Security

The server is **read-only by default**. A code-level SQL whitelist allows only `SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `EXPLAIN`, and `WITH` statements. Multi-statement queries are rejected.

For production use, also configure a read-only database user. See [`SECURITY.md`](./SECURITY.md) for the recommended setup.

## Development

```bash
git clone https://github.com/paikend/cubrid-mcp-server.git
cd cubrid-mcp-server
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Lint & type check
ruff check .
mypy cubrid_mcp_server

# Unit tests
pytest -m "not integration"

# Integration tests (requires running CUBRID)
export CUBRID_HOST=localhost CUBRID_USER=dba CUBRID_PASSWORD="" CUBRID_DATABASE=demodb
pytest -m integration
```

## License

Apache-2.0 (see [`LICENSE`](./LICENSE)).
