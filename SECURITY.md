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

## Layer 2 — code-level read-only whitelist

When `CUBRID_MCP_READONLY=1` (the default) the server parses every statement with `sqlparse` and rejects anything that is not `SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `EXPLAIN`, or `WITH` (CTE). Multi-statement input is rejected outright so a trailing `; DROP TABLE …` cannot slip through.

You can disable this layer by setting `CUBRID_MCP_READONLY=0`, but only do so when:

- the underlying DB user is already read-only (Layer 1 is in place), **and**
- you genuinely need statements outside the whitelist (for example, CUBRID administrative `SHOW` variants that confuse the parser).

**`explain_query` is always read-only**, independent of `CUBRID_MCP_READONLY`. It only ever produces a plan for a `SELECT`/`WITH` query, so it always applies the whitelist even when the server is nominally in write-allowed mode. Only `execute_query` honors `CUBRID_MCP_READONLY=0`.
## Layer 3 — output limits

`execute_query` caps the number of rows returned at `CUBRID_MCP_MAX_ROWS` (default 1000) and truncates rendered output once the cumulative character count exceeds `CUBRID_MCP_MAX_CHARS` (default 4000). Together these protect the model's context window and limit how much data a single probing query can exfiltrate in one shot. Binary values are base64-encoded when small and summarized (`<binary N bytes>`) when large, so raw blobs never flood the output.



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
- Comment-based obfuscation — SQL comments are stripped before the keyword scan

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

The project is in early development (`0.2.x`). Only the latest tagged release receives security fixes until the API stabilises.
