# Security Policy

`cubrid-mcp-server` bridges a CUBRID database and any MCP-speaking LLM client. Treat every query coming from the model as untrusted input: the LLM may hallucinate destructive SQL, and a malicious prompt may try to exfiltrate data the bot was never meant to see. Defence in depth is the design intent.

## Layer 1 — database-level permissions (required)

Run the server as a dedicated CUBRID user that has **only the privileges you want the model to use**. The code-level safety checker is not a substitute for this.

Minimum recommended setup for an exploration/analytics workload:

```sql
-- 1. Create the user
CREATE USER mcp_reader PASSWORD 'replace-me';

-- 2. Grant SELECT only on the specific tables you want exposed.
--    CUBRID grants privileges per table (there is no schema-wide `db.*` grant).
GRANT SELECT ON customers TO mcp_reader;
GRANT SELECT ON orders TO mcp_reader;
-- ...repeat for each table the model may read.

-- 3. Do NOT grant CREATE, ALTER, DROP, INSERT, UPDATE, DELETE, GRANT, or any DBA role.
```

Additional hardening:

- Use a long, randomly generated password. Store it in a secret manager — never commit `.env` files.
- Rotate the password on the same cadence as the rest of your database credentials.
- If the LLM only needs a subset of tables, grant `SELECT` on those tables specifically rather than the whole schema.
- Restrict network reachability: run CUBRID on a private network and only expose it to the host running the MCP server.

> **A `SELECT`-only grant does not stop every write.** CUBRID lets a user who may only `SELECT` from a table change data through the read itself: `INCR(col)` and `DECR(col)` update the row they read, the click counter `SELECT ... WITH INCREMENT FOR col` (or `WITH DECREMENT FOR col`) does the same, and `serial.NEXT_VALUE`, `serial.NEXTVAL` and `SERIAL_NEXT_VALUE(serial, n)` advance a serial, even one the user was granted nothing on. These changes persist: the rollback that ends every read does not undo them. The read-only checks (Layer 2) reject these forms; with `CUBRID_MCP_READONLY=0`, `execute_query` does not.

## Layer 2 — code-level read-only whitelist

When `CUBRID_MCP_READONLY=1` (the default) the server parses every statement with `sqlparse` and rejects anything that is not `SELECT`, `SHOW`, `DESC`, `DESCRIBE`, or `WITH` (CTE). CUBRID has no `EXPLAIN` statement; use the `explain_query` tool for execution plans. Multi-statement input is rejected. Comments, quotes and statement boundaries are read with CUBRID's rules, not `sqlparse`'s: `--`, `//` and `/* ... */` are comments (block comments do not nest), `#` is not a comment, and a backslash is an ordinary character inside quotes. Input whose quote boundaries depend on whether a backslash escapes a quote (the server parameter `no_backslash_escapes`), or that has an unterminated quote, is rejected.

Read-only mode also rejects the CUBRID forms that change data inside a `SELECT`, which a `SELECT`-only grant does not prevent (see Layer 1): the functions `INCR` and `DECR`, the serial advances `NEXT_VALUE`, `NEXTVAL` and `SERIAL_NEXT_VALUE`, and the click counter `WITH INCREMENT FOR` / `WITH DECREMENT FOR`. A name is matched when it is called (followed by `(`) or used as an attribute (after `.`, as in `owner.serial.NEXT_VALUE`), in any case, bare or quoted (`"INCR"`, `[incr]`, `` `incr` ``), with any whitespace or comments in between, anywhere in the statement, including subqueries and CTEs. String literals and longer names such as `incr_total` are not matched. `CURRENT_VALUE`, `CURRVAL` and `SERIAL_CURRENT_VALUE` only read a serial and stay allowed. A column that has one of these names is rejected when it is qualified (`t.next_value`); select it unqualified instead.

These keyword checks are a guardrail and defense-in-depth, not a security boundary. The primary control is a dedicated least-privilege database account (Layer 1): grant `SELECT` only on the tables the model needs, do not reuse `dba` or the owner account, and keep the account to the minimum privileges required, with no DDL rights.

You can disable this layer by setting `CUBRID_MCP_READONLY=0`, but only do so when:

- the underlying DB user is already read-only (Layer 1 is in place), **and**
- you genuinely need statements outside the whitelist (for example, CUBRID administrative `SHOW` variants that confuse the parser).

With `CUBRID_MCP_READONLY=0`, `execute_query` does not reject `INCR`, `DECR`, serial advances or the click counter, so a statement that uses them changes data although it returns a result set; `explain_query` still rejects them.

**`explain_query` always applies the read-only checks**, independent of `CUBRID_MCP_READONLY`; only `execute_query` honors `CUBRID_MCP_READONLY=0`. Note that `explain_query` executes the `SELECT`/`WITH` statement under `SET TRACE ON` to produce the trace and then rolls the transaction back as best-effort cleanup, so it uses real database resources.

## Layer 2b — opt-in write mode (`CUBRID_MCP_WRITE`)

Write access is **off by default**. Setting `CUBRID_MCP_WRITE=1` registers a separate `execute_write` tool that accepts a **single** `INSERT`/`UPDATE`/`DELETE` statement and runs it in an explicit transaction (commit on success, rollback on any failure). Design constraints that bound the blast radius:

- **DML only.** Standalone reads, DDL, transaction-control, and multi-statement input are rejected by a dedicated whitelist (`ensure_write_allowed`), separate from the read-only path. (A single DML statement may still legally embed subqueries, e.g. `INSERT ... SELECT`.)
- **DDL is intentionally unsupported.** `execute_write` is a DML tool (`INSERT`/`UPDATE`/`DELETE`) and `execute_query` is read-only, so `CREATE`/`ALTER`/`DROP`/`TRUNCATE` are rejected by both. (The server runs pycubrid with autocommit off; on the CUBRID versions tested (10.2, 11.2, 11.4) DDL is transactional and is rolled back if it is not committed, so the exclusion rests on the tool contracts, not on DDL auto-commit.)
- **Not registered when disabled.** With write mode off, `execute_write` is absent from MCP capability discovery — the tool is simply not offered. The database account remains what actually limits writes.
- **`execute_query` stays read-only** regardless of the write flag.

As with the read-only layer, this is defense-in-depth: still run the server as a CUBRID user granted only the privileges the model needs.
## Layer 3 — output limits

`execute_query` caps the number of rows returned at `CUBRID_MCP_MAX_ROWS` (default 1000) and truncates rendered output once the cumulative character count exceeds `CUBRID_MCP_MAX_CHARS` (default 4000). Together these protect the model's context window and limit how much data a single probing query can exfiltrate in one shot. Binary values are base64-encoded when small and summarized (`<binary N bytes>`) when large, so raw blobs never flood the output.

## Layer 4 — audit logging (opt-in)

Set `CUBRID_MCP_AUDIT_LOG=1` to emit a structured JSON record on **stderr** for every executed statement (`execute_query`, `explain_query`), for observability and after-the-fact security review. It is **off by default**.

Audit records are deliberately redaction-safe and share the same sanitization guarantees as client-facing errors:

- Only the statement **category** (leading keyword, read after comments and string literals are stripped) and **table identifiers** (extracted via a strict identifier regex) are recorded — never the raw SQL text.
- **Bound parameters and literal values are never logged**, so a secret embedded in a query (`WHERE token = '…'`) does not appear in the audit stream.
- Failures record the exception **class name only** (via `sanitize_error`), never the raw driver message.
- Records go to `stderr` only; `stdout` remains reserved for the MCP protocol stream.

This complements — but does not replace — CUBRID's own server-side query logging.



## LLM threat model

Because this server exposes database access to an LLM via MCP, the threat surface differs from a conventional database client. Operators must understand what the safety checker prevents and what it does not.

### What read-only enforcement **prevents**

- Data mutation — `INSERT`, `UPDATE`, `DELETE`, `REPLACE`, `MERGE`
- Schema changes — `CREATE`, `DROP`, `ALTER`, `TRUNCATE`, `RENAME`
- Privilege escalation — `GRANT`, `REVOKE`
- Transaction control — `COMMIT`, `ROLLBACK`
- Server-side procedures — `CALL`, `EXECUTE`
- Row-level locking — `SELECT ... FOR UPDATE`, `LOCK`
- Multi-statement injection — `;` separated batches are rejected outright
- Comment-based obfuscation — SQL comments (`--`, `//`, `/* ... */`, read with CUBRID's rules) are stripped before the keyword scan, so a comment cannot hide the real leading keyword

### What read-only enforcement **does not prevent**

- **Data exfiltration** — `SELECT password_hash FROM users` is allowed. The checker only blocks mutation; it cannot know which columns are sensitive.
- **Information disclosure** — Schema metadata, table names, row counts, and index definitions are all readable.
- **Resource exhaustion** — An LLM can be instructed to run expensive full-table scans repeatedly. There is no per-query cost limit.

### Operator responsibilities

1. **Dedicated read-only DB user** — Create a CUBRID user with `SELECT`-only grants at the table level (see Layer 2 above).
2. **Restrict sensitive tables** — Exclude tables containing credentials, PII, or other secrets from the user's grants.
3. **Network isolation** — Run the MCP server in a network segment where the LLM cannot reach the database directly.
4. **Audit logging** — Enable CUBRID query logging and monitor for unusual `SELECT` patterns.

### Future: `CUBRID_MCP_ALLOWED_TABLES`

A planned enhancement will allow operators to restrict which tables the LLM can query via an allow-list environment variable. This will provide defense-in-depth against data exfiltration at the application layer, complementing (not replacing) database-level grants.

## Reporting a vulnerability

Please do **not** open a public GitHub issue for security-sensitive reports. Instead, email [paikend@gmail.com](mailto:paikend@gmail.com) with:

- A description of the issue and its impact.
- The smallest reproduction you can share.
- Any suggested mitigation.

You should receive an acknowledgement within three business days. Coordinated disclosure is appreciated — please give the maintainers a reasonable window to ship a fix before going public.

## Supported versions

Only the latest published release receives security fixes. Upgrade to the latest release before reporting an issue, or state the exact version you reproduced it on.
