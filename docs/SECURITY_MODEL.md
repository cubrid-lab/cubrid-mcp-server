# Security Model

`cubrid-mcp-server` bridges a CUBRID database and any MCP-speaking LLM client. Treat every query coming from the model as untrusted input: the LLM may hallucinate destructive SQL, and a malicious prompt may try to exfiltrate data the server was never meant to expose. Defence in depth is the design intent.

## Layer 1 — database permissions (required)

Run the server as a dedicated CUBRID user that has **only the privileges you want the model to use**. The code-level safety checker is not a substitute for this.

```sql
-- 1. Create the user
CREATE USER mcp_reader PASSWORD 'replace-me';

-- 2. Grant SELECT only on the specific tables you want exposed.
--    CUBRID grants privileges per table (there is no schema-wide db.* grant).
GRANT SELECT ON customers TO mcp_reader;
GRANT SELECT ON orders TO mcp_reader;
-- ...repeat for each table the model may read.

-- 3. Do NOT grant CREATE, ALTER, DROP, INSERT, UPDATE, DELETE, GRANT, or any DBA role.
```

Additional hardening: use a long random password from a secret manager, rotate it on your normal cadence, grant per-table rather than schema-wide, and keep CUBRID on a network only the MCP-server host can reach. See [`SECURITY.md`](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/SECURITY.md) for the full policy.

## Layer 2 — read-only SQL whitelist

The server is **read-only by default**. When `CUBRID_MCP_READONLY=1` (the default), every statement is parsed with `sqlparse` and rejected unless it is `SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `EXPLAIN`, or `WITH` (CTE). Multi-statement input is rejected outright, so a trailing `; DROP TABLE …` cannot slip through.

> The whitelist is defense-in-depth, not a security boundary. It is a parser-based guardrail against obvious mistakes; the real enforcement layer is the database itself (Layer 1).

`CUBRID_MCP_READONLY=0` disables this layer — only do so when the DB user is already read-only and you need statements the parser misclassifies. `explain_query` is **always** read-only regardless of this flag; only `execute_query` honors disabling it.

## Layer 2b — opt-in write mode (`CUBRID_MCP_WRITE`)

Write access is **off by default**. Setting `CUBRID_MCP_WRITE=1` registers a separate `execute_write` tool bounded by:

- **DML only.** A dedicated whitelist (`ensure_write_allowed`) accepts a **single** `INSERT`, `UPDATE`, or `DELETE` and rejects standalone reads, DDL, transaction control, and multi-statement input. (A single DML statement may still legally embed subqueries, e.g. `INSERT ... SELECT`.)
- **Atomic transactions.** The statement runs in an explicit transaction — commit on success, rollback on any failure.
- **DDL is intentionally unsupported.** CUBRID auto-commits DDL, which would defeat the rollback guarantee, so `CREATE`/`ALTER`/`DROP`/`TRUNCATE` are never permitted.
- **Not registered when disabled.** With write mode off, `execute_write` is absent from MCP capability discovery — there is no reachable write path, not merely a guarded one.
- **Per-connection gating.** With multiple connections, the tool is registered when **any** connection enables writes, but each write is enforced against the **target** connection's setting — a connection with writes off refuses even when another enables them.
- `execute_query` remains **read-only regardless** of the write flag.

## Layer 3 — output limits

`execute_query` caps rows at `CUBRID_MCP_MAX_ROWS` (default 1000) and truncates rendered output at `CUBRID_MCP_MAX_CHARS` (default 4000). This protects the model's context window and limits how much data a single probing query can exfiltrate. Binary values are base64-encoded when small and summarized (`<binary N bytes>`) when large.

## Layer 4 — audit logging (opt-in)

Set `CUBRID_MCP_AUDIT_LOG=1` to emit one structured JSON record per executed statement (`execute_query`, `explain_query`, `execute_write`) on **stderr**. Off by default; honoured per connection (`CUBRID_<NAME>_MCP_AUDIT_LOG`).

| Field | Description |
|-------|-------------|
| `tool` | The MCP tool that ran the statement |
| `status` | `ok` or `error` |
| `category` | The leading SQL keyword only (e.g. `SELECT`, `WITH`) — never the full statement |
| `identifiers` | Table names extracted after `FROM`/`JOIN` via a strict identifier regex; anything that is not a bare identifier is dropped |
| `sql_length` | Length of the submitted SQL, in characters |
| `row_count`, `truncated` | Result size and whether output was truncated (success only) |
| `duration_ms` | Wall-clock duration of the call, in integer milliseconds |
| `error_type` | On failure, the exception class name only |

The **raw SQL text, bound parameters, and literal values are never logged**, so secrets embedded in a query do not reach the audit stream.

## Logging discipline

The server speaks MCP stdio: `stdout` carries the JSON-RPC protocol stream, so **all logging is routed to stderr**. Errors surfaced to the LLM client are sanitized — only the exception category (e.g. `query failed: OperationalError`) is returned, while full detail goes to stderr for operators. This keeps schema details, hostnames, SQL fragments, and configuration values out of client-visible messages.
