# Security Policy

`cubrid-mcp-server` bridges a CUBRID database and any MCP-speaking LLM client. Treat every query coming from the model as untrusted input: the LLM may hallucinate destructive SQL, and a malicious prompt may try to exfiltrate data the bot was never meant to see. Defence in depth is the design intent.

## Layer 1 — database-level permissions (required)

Run the server as a dedicated CUBRID user that has **only the privileges you want the model to use**. The code-level safety checker is not a substitute for this.

Minimum recommended setup for an exploration/analytics workload:

```sql
-- 1. Create the user
CREATE USER mcp_reader PASSWORD 'replace-me';

-- 2. Grant only read on the schemas you want exposed
GRANT SELECT ON demodb.* TO mcp_reader;

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

## Layer 3 — output limits

`execute_query` truncates rendered output once the cumulative character count exceeds `CUBRID_MCP_MAX_CHARS` (default 4000). This protects the model's context window, and it also limits how much data a single probing query can exfiltrate in one shot.

## Reporting a vulnerability

Please do **not** open a public GitHub issue for security-sensitive reports. Instead, email [paikend@gmail.com](mailto:paikend@gmail.com) with:

- A description of the issue and its impact.
- The smallest reproduction you can share.
- Any suggested mitigation.

You should receive an acknowledgement within three business days. Coordinated disclosure is appreciated — please give the maintainers a reasonable window to ship a fix before going public.

## Supported versions

The project is in pre-alpha (`0.0.x`). Only the latest tagged release receives security fixes until the API stabilises.
