# Security Model

> 한국어: [보안 모델](ko/SECURITY_MODEL.md)

`cubrid-mcp-server` bridges a CUBRID database and any MCP-speaking LLM client. Treat every query coming from the model as untrusted input: the LLM may hallucinate destructive SQL, and a malicious prompt may try to exfiltrate data the server was never meant to expose. Defence in depth is the design intent.

## Layer 1 — database permissions (required)

Run the server as a dedicated, least-privilege CUBRID user that has **only the privileges you want the model to use**. This account is the primary security control; the code-level safety checker is a guardrail and is not a substitute for it. Do not reuse `dba` or the owner account of the schema.

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

Grant `SELECT` only on the tables the model needs, and keep the account to the minimum privileges required, with no DDL rights.

> **A `SELECT`-only grant does not stop every write.** CUBRID lets a user who may only `SELECT` from a table change data through the read itself: `INCR(col)` and `DECR(col)` update the row they read, the click counter `SELECT ... WITH INCREMENT FOR col` (or `WITH DECREMENT FOR col`) does the same, and `serial.NEXT_VALUE`, `serial.NEXTVAL` and `SERIAL_NEXT_VALUE(serial, n)` advance a serial, even one the user was granted nothing on. These changes persist: the rollback that ends every read does not undo them. The read-only checks (Layer 2) reject these forms, and `execute_query` rejects them with `CUBRID_MCP_READONLY=0` too.

Additional hardening: use a long random password from a secret manager, rotate it on your normal cadence, grant per-table rather than schema-wide, and keep CUBRID on a network only the MCP-server host can reach. See [`SECURITY.md`](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/SECURITY.md) for the full policy.

## Layer 2 — read-only SQL whitelist

The server is **read-only by default**. When `CUBRID_MCP_READONLY=1` (the default), every statement is parsed with `sqlparse` and rejected unless it is `SELECT`, `SHOW`, `DESC`, `DESCRIBE`, or `WITH` (CTE). CUBRID has no `EXPLAIN` statement; use the `explain_query` tool for execution plans. Multi-statement input is rejected. Comments, quotes and statement boundaries are read with CUBRID's rules, not `sqlparse`'s: `--`, `//` and `/* ... */` are comments (block comments do not nest), `#` is not a comment, and a backslash is an ordinary character inside quotes. Input whose quote boundaries depend on whether a backslash escapes a quote (the server parameter `no_backslash_escapes`), or that has an unterminated quote, is rejected. The first word of the statement must itself be an allowed keyword: `sqlparse` reads words it does not know, such as `KILL` and `EVALUATE`, as names, so `KILL (SELECT 1)` would otherwise pass as a `SELECT`. The write path matches the first word against `INSERT`, `UPDATE` and `DELETE` the same way.

Read-only mode also rejects the CUBRID forms that change data inside a `SELECT`, which a `SELECT`-only grant does not prevent (see Layer 1): the functions `INCR` and `DECR`, the serial advances `NEXT_VALUE`, `NEXTVAL` and `SERIAL_NEXT_VALUE`, and the click counter `WITH INCREMENT FOR` / `WITH DECREMENT FOR`. A name is matched when it is called (followed by `(`) or used as an attribute (after `.`, as in `owner.serial.NEXT_VALUE`), in any case, bare or quoted (`"INCR"`, `[incr]`, `` `incr` ``), with any whitespace or comments in between, anywhere in the statement, including subqueries and CTEs. String literals and longer names such as `incr_total`, `incr#` or `#incr` (`#` is an identifier character, also as the first one) are not matched. `CURRENT_VALUE`, `CURRVAL` and `SERIAL_CURRENT_VALUE` only read a serial and stay allowed. A column that has one of these names is rejected when it is qualified (`t.next_value`); select it unqualified instead.

> The SQL keyword checks are a guardrail and defense-in-depth, not a security boundary. They are a best-effort client-side filter against obvious mistakes; the primary control is the dedicated least-privilege database account (Layer 1), which should have `SELECT` only on the tables the model needs.

`CUBRID_MCP_READONLY=0` relaxes this whitelist — only do so when the DB user is already read-only and you need result-set statements the parser misclassifies. It does **not** make `execute_query` a write path: `execute_query` still rejects statements that lead with a write, DDL or transaction-control keyword (`INSERT`, `UPDATE`, `DELETE`, `REPLACE`, `MERGE`, `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `RENAME`, `GRANT`, `REVOKE`, `COMMIT`, `ROLLBACK`, `SAVEPOINT`, `SET`, `PREPARE`, `EXECUTE`, `DEALLOCATE`, `DO`), method calls (`CALL`, `EVALUATE`) and `KILL` (matching the first word of the leading keyword and of the statement) and rejects multi-statement and empty input before they reach the database, never commits, and rolls back any statement that returns no result set (keeping the connection) as well as every successful read. `explain_query` always applies the read-only checks regardless of this flag (see below). This keyword check is a guardrail, not a security boundary: the read-only database account remains the security boundary. Use `execute_write` (opt-in write mode) for writes; clients that sent writes through `execute_query` with `CUBRID_MCP_READONLY=0` must switch to it. `CALL` is rejected because `CALL login(...) ON CLASS db_user` switches the user of the cached shared session for every later tool call, including `execute_write`; `execute_write` (`INSERT`/`UPDATE`/`DELETE` only) and `explain_query` (`SELECT`/`WITH` only) reject it too, so no tool can change the session user. `KILL` ends other sessions' transactions. `LOCK` is not a CUBRID statement and `GET` only reads a server setting, so neither is rejected by this check.

With `CUBRID_MCP_READONLY=0`, `execute_query` still rejects `INCR`, `DECR`, serial advances and the click counter, with the same matching as read-only mode: they change data although the statement returns a result set, and writes belong to `execute_write`.

## Layer 2b — opt-in write mode (`CUBRID_MCP_WRITE`)

Write access is **off by default**. Setting `CUBRID_MCP_WRITE=1` registers a separate `execute_write` tool bounded by:

- **DML only.** A dedicated whitelist (`ensure_write_allowed`) accepts a **single** `INSERT`, `UPDATE`, or `DELETE` and rejects standalone reads, DDL, transaction control, and multi-statement input. (A single DML statement may still legally embed subqueries, e.g. `INSERT ... SELECT`.)
- **Atomic transactions.** The statement runs in an explicit transaction — commit on success, rollback on any failure.
- **DDL is intentionally unsupported.** `execute_write` is a DML tool (`INSERT`/`UPDATE`/`DELETE`) and `execute_query` is read-only, so `CREATE`/`ALTER`/`DROP`/`TRUNCATE` are rejected by both. (The server runs pycubrid with autocommit off; on the CUBRID versions tested (10.2, 11.2, 11.4) DDL is transactional and is rolled back if it is not committed, so the exclusion rests on the tool contracts, not on DDL auto-commit.)
- **Not registered when disabled.** With write mode off, `execute_write` is absent from MCP capability discovery — the tool is simply not offered. Because the SQL checks are a guardrail, the database account remains what actually limits writes.
- **Per-connection gating.** With multiple connections, the tool is registered when **any** connection enables writes, but each write is enforced against the **target** connection's setting — a connection with writes off refuses even when another enables them.
- `execute_query` ignores the write flag: write mode never makes it a write path (it rejects the `SELECT` side effects in Layer 2 with `CUBRID_MCP_READONLY=0` too).

### `explain_query` executes the statement

`explain_query` does not merely plan: it runs the `SELECT`/`WITH` statement under `SET TRACE ON`, reads `SHOW TRACE`, then turns tracing off and rolls the transaction back. The statement therefore consumes real database resources (and can take as long as the query itself), and it is subject to the same keyword checks and database privileges as `execute_query`. The rollback is best-effort cleanup by the server, not a substitute for a least-privilege account. If any cleanup step fails, the server discards the connection instead of reusing a session that may still have tracing on or a transaction open; the next call reconnects.

## Layer 3 — output limits

`execute_query` caps rows at `CUBRID_MCP_MAX_ROWS` (default 1000) and truncates rendered output at `CUBRID_MCP_MAX_CHARS` (default 4000). This protects the model's context window and limits how much data a single probing query can exfiltrate. Binary values are base64-encoded when small and summarized (`<binary N bytes>`) when large.

## Layer 4 — audit logging (opt-in)

Set `CUBRID_MCP_AUDIT_LOG=1` to emit one structured JSON record per executed statement (`execute_query`, `explain_query`, `execute_write`) on **stderr**. Off by default; honoured per connection (`CUBRID_<NAME>_MCP_AUDIT_LOG`).

| Field | Description |
|-------|-------------|
| `tool` | The MCP tool that ran the statement |
| `status` | `ok` or `error` |
| `category` | The leading SQL keyword only (e.g. `SELECT`, `WITH`), read after comments and string literals are stripped — never the full statement |
| `identifiers` | Table names extracted after `FROM`/`JOIN` via a strict identifier regex; anything that is not a bare identifier is dropped |
| `sql_length` | Length of the submitted SQL, in characters |
| `row_count`, `truncated` | Result size and whether output was truncated (success only) |
| `duration_ms` | Wall-clock duration of the call, in integer milliseconds |
| `error_type` | On failure, the exception class name only |

The **raw SQL text, bound parameters, and literal values are never logged**, so secrets embedded in a query do not reach the audit stream.

## Logging discipline

The server speaks MCP stdio: `stdout` carries the JSON-RPC protocol stream, so **all logging is routed to stderr**. Errors surfaced to the LLM client are sanitized — only the exception category (e.g. `query failed: OperationalError`) is returned, while full detail goes to stderr for operators. Connection failures return the fixed message `failed to connect to CUBRID`, and `health_check` returns only the exception class name; the host, port, database and driver cause are logged to stderr only. This keeps schema details, hostnames, SQL fragments, and configuration values out of client-visible messages.
