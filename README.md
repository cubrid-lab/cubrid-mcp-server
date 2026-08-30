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
| `health_check` | Verify database connectivity on demand |

### Resources

Schema metadata is also exposed as read-only [MCP Resources](https://modelcontextprotocol.io/docs/concepts/resources), so clients can discover and read schema context without a tool call. Resources reuse the same read-only catalog queries as the tools — no additional data access or write surface.

| Resource URI | Description |
|--------------|-------------|
| `cubrid://schema` | Whole-schema index: every user table with its per-table resource URI |
| `cubrid://schema/{table}` | Per-table metadata (columns, primary key, indexes) — mirrors `describe_table` |

Both return `application/json`. Table names in `{table}` are percent-decoded by URI-template matching; an unknown or system table produces a resource-read error, matching the `describe_table` tool.

## Quick Start

### Configure

Set the required environment variables:

```bash
export CUBRID_HOST=localhost
export CUBRID_PORT=33000        # optional, default: 33000
export CUBRID_USER=readonly_user   # a CUBRID user with SELECT-only grants (see Security)
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
| `CUBRID_MCP_QUERY_TIMEOUT` | `30` | Per-statement socket read timeout in seconds. If the server sends no data within this window the query is aborted and the connection is reset. This is a socket read timeout, not a true server-side statement timeout. |

### Run

> **Note:** The package is not yet published to PyPI. Until the first release lands, install and run it from source (see [Development](#development)); the `uvx`/`pipx` commands below will work once the package is available on PyPI.

### Run from source (available now)

```bash
git clone https://github.com/cubrid-lab/cubrid-mcp-server.git
cd cubrid-mcp-server
python -m venv .venv && source .venv/bin/activate
pip install -e .
cubrid-mcp-server
```

### Run from PyPI (once published)

Use [`uvx`](https://docs.astral.sh/uv/guides/tools/) to run directly from PyPI:

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

## Security

The server is **read-only by default**. A code-level SQL whitelist allows only `SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `EXPLAIN`, and `WITH` statements. Multi-statement queries are rejected.

> **The SQL whitelist is defense-in-depth, not a security boundary.** It is a non-validating parser-based guardrail against obvious mistakes. The real enforcement layer is the database itself: **always run the server as a CUBRID user that has only `SELECT` grants** on the tables the model may read. See [`SECURITY.md`](./SECURITY.md).

For production use, also configure a read-only database user. See [`SECURITY.md`](./SECURITY.md) for the recommended setup.

## Logging

The server speaks the MCP **stdio transport**, where `stdout` carries the JSON-RPC protocol stream. Anything written to `stdout` by the server or its dependencies will corrupt that stream and break the client connection. For this reason **all logging is routed to `stderr`**, and you should keep it that way: when adding custom logging or diagnostics, never `print()` to `stdout` — use the standard `logging` module (which is configured to emit on `stderr`) or write to `stderr` explicitly. The log level defaults to `INFO`.

Errors surfaced back to the LLM client are **sanitized**: only the exception category (e.g. `query failed: OperationalError`) is returned, while the full exception detail is logged to `stderr` for operators. This keeps schema details, hostnames, SQL fragments, and configuration values out of client-visible messages.


## Development

```bash
git clone https://github.com/cubrid-lab/cubrid-mcp-server.git
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

## Disclaimer

> This project is part of [CUBRID Lab](https://github.com/cubrid-lab), an independent open-source initiative for CUBRID developer tooling, and is not affiliated with, sponsored by, or endorsed by CUBRID Corporation or the official CUBRID project.


## License

MIT (see [`LICENSE`](./LICENSE)).
