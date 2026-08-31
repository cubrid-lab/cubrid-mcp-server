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

## Prompts

The server also exposes a small set of **MCP Prompt templates** — reusable, guided
starting points for common inspection tasks. Prompts are **guidance-only**: each one
returns text that tells the client which of the existing read-only tools to call and
in what order. They never touch the database, execute SQL, or add any new data-access
surface, and any argument you pass is fenced and treated strictly as untrusted data.
The prompts are advisory templates only — the actual read-only enforcement remains in
the underlying tools (`execute_query`/`explain_query` via `safety.py`).

| Prompt | Arguments | Description |
|--------|-----------|-------------|
| `summarize_table` | `table` | Describe a table, then sample it with a bounded read-only query |
| `explain_query` | `sql` | Obtain and interpret a `SELECT`/`WITH` execution plan via `explain_query` |
| `inspect_schema` | _(none)_ | Build a high-level overview of the whole schema from the read-only tools |
| `find_index_candidates` | `table` | Review a table's index coverage for potential review areas |

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

### Multiple connections

By default the bare `CUBRID_*` variables define a single connection named `default`.
You can serve additional CUBRID databases from the same process by listing extra
connection names in `CUBRID_CONNECTIONS` (comma-separated) and providing
`CUBRID_<NAME>_*` variables for each. Every tool accepts an optional `connection`
argument selecting which connection to target; omitting it (or passing `default`)
uses the bare-variable connection, so existing single-database setups are unchanged.

```bash
# Default connection (unchanged)
export CUBRID_HOST=localhost
export CUBRID_USER=readonly_user
export CUBRID_PASSWORD=secret
export CUBRID_DATABASE=mydb

# Additional named connections
export CUBRID_CONNECTIONS=reporting,analytics

export CUBRID_REPORTING_HOST=reporting-db
export CUBRID_REPORTING_USER=readonly_user
export CUBRID_REPORTING_PASSWORD=secret
export CUBRID_REPORTING_DATABASE=reports
export CUBRID_REPORTING_MCP_MAX_ROWS=500   # optional per-connection tuning

export CUBRID_ANALYTICS_HOST=analytics-db
export CUBRID_ANALYTICS_USER=readonly_user
export CUBRID_ANALYTICS_PASSWORD=secret
export CUBRID_ANALYTICS_DATABASE=analytics
```

Notes:

- Connection names must match `[A-Za-z0-9_]+` and are matched case-insensitively.
- `default` is reserved (it always comes from the bare `CUBRID_*` variables) and
  cannot appear in `CUBRID_CONNECTIONS`.
- For a named connection `<NAME>`, connection fields live at `CUBRID_<NAME>_HOST`
  etc. and the optional MCP tuning knobs at `CUBRID_<NAME>_MCP_*` (same suffixes as
  the global ones). Named connections do **not** inherit values from the bare vars.
- Selecting an unknown connection returns a clear error listing the available names.
- Each connection has its own read-only enforcement, so a named connection can set
  `CUBRID_<NAME>_MCP_READONLY` independently of the default.

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
