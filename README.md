# cubrid-mcp-server

A [Model Context Protocol](https://modelcontextprotocol.io) server for [CUBRID](https://www.cubrid.org/), enabling LLMs to safely inspect schemas and execute read-only queries via [pycubrid](https://pypi.org/project/pycubrid/).

## Features

| Tool | Description |
|------|-------------|
| `all_table_names` | List every user table in the database |
| `filter_table_names` | Substring search over table names |
| `schema_definitions` | Column types, nullability, defaults, and primary key info |
| `describe_table` | Full metadata: columns, primary key, and indexes in one call |
| `list_indexes` | Indexes for a table with key columns and flags |
| `explain_query` | Execution plan/trace for a `SELECT`/`WITH` (via CUBRID `SHOW TRACE`) |
| `table_row_counts` | `COUNT(*)` for one or many tables |
| `list_serials` | CUBRID `SERIAL` sequences with current value and bounds |
| `list_class_hierarchy` | CUBRID `CLASS` inheritance relationships |
| `execute_query` | Run read-only SQL with automatic output truncation |

## Quick Start

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

No installation required — use [`uvx`](https://docs.astral.sh/uv/guides/tools/) to run directly from PyPI:

```bash
uvx cubrid-mcp-server
```

Or with `pipx`:

```bash
pipx run cubrid-mcp-server
```

## MCP Client Integration

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
      "command": "uvx",
      "args": ["cubrid-mcp-server"],
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
      "command": "uvx",
      "args": ["cubrid-mcp-server"],
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
git clone https://github.com/cubrid-labs/cubrid-mcp-server.git
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
