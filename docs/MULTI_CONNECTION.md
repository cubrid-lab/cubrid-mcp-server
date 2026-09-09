# Multi-Connection

One server process can serve several CUBRID databases. Every tool accepts an optional `connection` argument selecting the target; single-database setups are unchanged.

## Default connection

The bare `CUBRID_*` variables define a single connection named `default`:

```bash
export CUBRID_HOST=localhost
export CUBRID_USER=readonly_user
export CUBRID_PASSWORD=secret
export CUBRID_DATABASE=mydb
```

## Named connections

List extra connection names in `CUBRID_CONNECTIONS` (comma-separated) and provide `CUBRID_<NAME>_*` variables for each:

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

Then, in a client conversation: *"Query the analytics database for …"* — the model passes `connection="analytics"` to the tool.

## Rules

- Connection names must match `[A-Za-z0-9_]+` and are matched case-insensitively.
- `default` is reserved (it always comes from the bare `CUBRID_*` variables) and cannot appear in `CUBRID_CONNECTIONS`.
- For a named connection `<NAME>`, connection fields live at `CUBRID_<NAME>_HOST` etc., and the optional tuning knobs at `CUBRID_<NAME>_MCP_*` (the same suffixes as the global ones).
- Named connections do **not** inherit values from the bare variables — specify every field for each named connection.
- Selecting an unknown connection returns a clear error listing the available names.

## Per-connection isolation

Each connection is independently configured and enforced:

| Setting | Per-connection variable | Effect |
|---------|------------------------|--------|
| Read-only | `CUBRID_<NAME>_MCP_READONLY` | Whitelist enforcement for this connection only |
| Write mode | `CUBRID_<NAME>_MCP_WRITE` | Opt-in `execute_write` for this connection only |
| Audit log | `CUBRID_<NAME>_MCP_AUDIT_LOG` | Audit stream for this connection only |
| Output limits | `CUBRID_<NAME>_MCP_MAX_ROWS` / `_MAX_CHARS` / `_MAX_SQL_LENGTH` / `_QUERY_TIMEOUT` | Tuning for this connection only |

Each connection also has its own lock, connection lifecycle, and stale-connection recovery, so a hung query on one database does not block the others.

Write-mode registration nuance: the `execute_write` tool appears in MCP capability discovery when **any** connection enables writes, but every call is enforced against the **target** connection's setting — a connection with writes off refuses the write even when another connection enables them. See the [Security Model](SECURITY_MODEL.md#layer-2b-opt-in-write-mode-cubrid_mcp_write).
