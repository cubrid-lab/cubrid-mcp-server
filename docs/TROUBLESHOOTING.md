# Troubleshooting

Symptom → cause → fix for the most common problems.

## The client cannot connect to the server

**Symptom:** the MCP client shows the server as failed or unavailable.

- **`uvx` not found.** The client launches `uvx cubrid-mcp-server` — install [uv](https://docs.astral.sh/uv/) so `uvx` is on the client's `PATH`, or use an absolute path in the client config (`"command": "/home/you/.local/bin/uvx"`).
- **Environment variables missing.** `CUBRID_HOST`, `CUBRID_USER`, `CUBRID_PASSWORD`, and `CUBRID_DATABASE` must be present in the client's `env` block — a plain terminal export is not visible to GUI apps like Claude Desktop.
- **Config file location.** Claude Desktop reads `~/Library/Application Support/Claude/claude_desktop_config.json`; Claude Code reads `.mcp.json` at the project root; Cursor reads `.cursor/mcp.json`. After editing, restart the client.

## CUBRID connection refused

**Symptom:** tools fail with connection or operational errors.

- **Wrong port.** The server connects to the CUBRID **broker** on port 33000 (`CUBRID_PORT`), not the manager port 1523.
- **Database does not exist.** Create it first (`cubrid createdb`) or point `CUBRID_DATABASE` at an existing database.
- **CUBRID still starting.** A fresh CUBRID container takes a while to accept connections — the broker accepts TCP slightly after the engine is up. Wait for readiness (e.g. the docker-compose healthcheck) before starting queries. `health_check` verifies connectivity on demand.
- **Credentials.** `CUBRID_USER`/`CUBRID_PASSWORD` must be valid; `dba` with an empty password is common in local docker setups.

## Permission denied on queries

**Symptom:** authorization errors on `SELECT` statements.

The CUBRID user lacks grants. CUBRID grants privileges **per table** — there is no schema-wide `db.*` grant. Create a user and grant `SELECT` on each table the model may read; see the [Security Model](SECURITY_MODEL.md#layer-1-database-permissions-required).

## Read-only rejection

**Symptom:** `execute_query` rejects a statement.

By design. The whitelist allows only `SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `EXPLAIN`, and `WITH`; multi-statement input is always rejected. If you truly need other statements, first put a read-only DB user in place, then consider `CUBRID_MCP_READONLY=0` — and for writes, use opt-in write mode instead of disabling the whitelist.

## Output looks cut off

**Symptom:** `execute_query` results end abruptly or report truncation.

Row and character caps protect the model's context window. Raise `CUBRID_MCP_MAX_ROWS` (default 1000) or `CUBRID_MCP_MAX_CHARS` (default 4000) if you need more, or narrow the query.

## Query timeout semantics

**Symptom:** long-running queries abort after ~30s.

`CUBRID_MCP_QUERY_TIMEOUT` (default 30) is a **socket read timeout**, not a true server-side statement timeout: if the server sends no data within the window, the query is aborted and the connection reset. Tune it per workload (and per connection via `CUBRID_<NAME>_MCP_QUERY_TIMEOUT`).

## No logs anywhere / server output looks like JSON garbage

The server speaks MCP stdio: `stdout` carries the protocol stream, and **all logging goes to stderr**. Look at the client's MCP log pane (or launch the server manually and redirect `2>server.log`). Never add `print()` to stdout in customizations — it corrupts the protocol stream and breaks the connection.

## Audit log not appearing

Set `CUBRID_MCP_AUDIT_LOG=1` (opt-in, off by default). With multiple connections, enable it per connection via `CUBRID_<NAME>_MCP_AUDIT_LOG`. Records are JSON lines on **stderr** — they never appear on stdout. See the [Security Model](SECURITY_MODEL.md#layer-4-audit-logging-opt-in).
