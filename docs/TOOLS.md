# Tools Reference

`cubrid-mcp-server` exposes its capabilities as MCP **tools**, **resources**, and **prompts**. Every tool accepts an optional `connection` argument (see [Multi-Connection](MULTI_CONNECTION.md)); omitting it targets the `default` connection.

## Tools

### Schema inspection

#### `all_table_names(connection=None)`

Lists every user table in the database. System and catalog tables are excluded.

#### `filter_table_names(substring, connection=None)`

Case-insensitive substring search over table names. Use this instead of `all_table_names` when the schema is large.

#### `schema_definitions(table_name, connection=None)`

Column-level metadata for one table: column name, type, nullability, default value, and primary-key membership.

#### `describe_table(table_name, connection=None)`

Full metadata for one table in a single call — columns, primary key, and indexes. Mirrors the `cubrid://schema/{table}` resource.

`primary_key` lists the key columns in **declared primary-key order** (the order in `PRIMARY KEY (...)`, i.e. CUBRID's `db_index_key.key_order`), matching the primary-key entry in `indexes`. `columns` stays in table-definition order, with a per-column boolean `primary_key` flag. A table without a primary key returns `"primary_key": []`.

#### `list_indexes(table_name, connection=None)`

Indexes defined on a table, with the indexed key columns and flags (unique, reverse).

#### `list_class_hierarchy(table_name=None, connection=None)`

CUBRID `CLASS` inheritance relationships — which tables inherit from which. Omit `table_name` for every class, or pass one to get only that table's direct super classes. `table_name` is resolved like the other schema tools: matched case-insensitively against user tables, and an unknown table (including system classes and views) raises `unknown table` instead of returning an empty list.

### Querying

#### `execute_query(sql, connection=None)`

Runs **read-only** SQL (`SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `WITH`) and only statements that return a result set. Use `explain_query` for query plans. Output is automatically truncated to respect the model's context window:

- at most `CUBRID_MCP_MAX_ROWS` rows (default 1000),
- rendered output capped at `CUBRID_MCP_MAX_CHARS` characters (default 4000),
- statement length capped at `CUBRID_MCP_MAX_SQL_LENGTH` (default 65536),
- per-statement socket read timeout of `CUBRID_MCP_QUERY_TIMEOUT` seconds (default 30).

Multi-statement and empty (comment-only or `;`-only) input is rejected, also with `CUBRID_MCP_READONLY=0`. Binary values are base64-encoded when small and summarized (`<binary N bytes>`) when large.

Every read ends its own transaction: the server rolls back after the rows are collected (truncated or not), so no locks or snapshot are held between tool calls and the next call sees rows other sessions have committed. `execute_query` never commits and is read-only even with `CUBRID_MCP_READONLY=0`, which only relaxes the whitelist: statements that lead with a write, DDL or transaction-control keyword (`INSERT`, `UPDATE`, `DELETE`, `REPLACE`, `MERGE`, `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `RENAME`, `GRANT`, `REVOKE`, `COMMIT`, `ROLLBACK`, `SAVEPOINT`, `SET`, `PREPARE`, `EXECUTE`, `DEALLOCATE`, `DO`) are rejected before they reach the database, with an error pointing to `execute_write`; the first word of the leading keyword is matched, so `CREATE OR REPLACE …` is rejected like `CREATE`. This keyword check is a guardrail, not a security boundary: the read-only database account remains the boundary. A statement that still returns no result set is rolled back and fails with `statement produced no result set; execute_query is read-only, use execute_write …`; the connection is kept. Use `execute_write` for writes.

> **Migration:** clients that sent `INSERT`/`UPDATE`/`DELETE` through `execute_query` with `CUBRID_MCP_READONLY=0` must use `execute_write` (`CUBRID_MCP_WRITE=1`) instead.

#### `explain_query(sql, connection=None)`

Returns the execution plan/trace for a `SELECT` or `WITH` statement via CUBRID `SHOW TRACE`. Always read-only, independent of the `CUBRID_MCP_READONLY` flag.

#### `table_row_counts(table_names=None, connection=None)`

`COUNT(*)` for one table or many — cheaper than sampling rows to estimate size. Returns `{"tables": [{"table", "row_count"}, …], "truncated": bool, "total_tables": int}`, where `total_tables` is the number of user tables in the database; a table that is unknown or fails to count has `"row_count": null` and an `error`.

- Omitted or `None`: counts the first 50 user tables in name order. If the database has more, `truncated` is `true`; pass the remaining names (from `all_table_names`) in batches of up to 50.
- Explicit list: counts those tables; more than 50 names raises `too many tables requested (N); limit is 50 per call`.
- Empty list (`[]`): counts nothing and returns `"tables": []`.

### CUBRID specifics

#### `list_serials(connection=None)`

CUBRID `SERIAL` sequences with their current value, minimum, maximum, and increment.

#### `health_check(connection=None)`

Verifies database connectivity on demand and reports per-connection status. Useful after environment changes or long idle periods.

### Opt-in writes

#### `execute_write(sql, connection=None)`

Runs a **single** `INSERT`, `UPDATE`, or `DELETE` statement in an explicit transaction (commit on success, rollback on any failure). **Registered only when write mode is enabled** (`CUBRID_MCP_WRITE=1` or `CUBRID_<NAME>_MCP_WRITE=1` on any connection) — with write mode off, the tool does not exist in MCP capability discovery at all.

Constraints: DDL (`CREATE`/`ALTER`/`DROP`/`TRUNCATE`), standalone reads, transaction control, and multi-statement input are rejected. See the [Security Model](SECURITY_MODEL.md).

## Resources

Schema metadata is also exposed as read-only [MCP Resources](https://modelcontextprotocol.io/docs/concepts/resources), so clients can discover schema context without a tool call. Resources reuse the same read-only catalog queries — no additional data-access surface.

| Resource URI | Description |
|--------------|-------------|
| `cubrid://agent-guide` | Comprehensive CUBRID agent guide: SQL dialect, types, safety, performance, tool selection |
| `cubrid://guide/sql-dialect` | CUBRID syntax differences from MySQL/PostgreSQL |
| `cubrid://guide/types` | Data type guide: collections, ENUM, JSON, Python mapping |
| `cubrid://guide/performance` | Performance optimization: SHOW TRACE, indexes, anti-patterns |
| `cubrid://guide/collections` | Deep dive on SET, MULTISET, SEQUENCE types |
| `cubrid://schema` | Whole-schema index: every user table with its per-table resource URI |
| `cubrid://schema/{table}` | Per-table metadata (columns, primary key, indexes) — mirrors `describe_table` |

Both return `application/json`. Table names in `{table}` are percent-decoded by URI-template matching; an unknown or system table produces a resource-read error, matching the `describe_table` tool.

## Prompts

The server exposes MCP **Prompt templates** — guidance-only starting points for common inspection tasks. Each prompt returns text telling the client which read-only tools to call and in what order. Prompts never touch the database, execute SQL, or add any data-access surface, and arguments are fenced as untrusted data.

| Prompt | Arguments | Description |
|--------|-----------|-------------|
| `summarize_table` | `table` | Describe a table, then sample it with a bounded read-only query |
| `explain_query` | `sql` | Obtain and interpret a `SELECT`/`WITH` execution plan via `explain_query` |
| `inspect_schema` | *(none)* | Build a high-level overview of the whole schema from the read-only tools |
| `find_index_candidates` | `table` | Review a table's index coverage for potential review areas |
| `optimize_query` | `sql` | Analyze execution plan and suggest CUBRID-specific optimizations |
| `migrate_from_mysql` | `sql` | Convert MySQL query syntax to valid CUBRID SQL |
| `explore_unknown_db` | *(none)* | Systematically explore an unfamiliar database |
| `safe_data_analysis` | `question` | Answer data questions using read-only queries |
| `write_cubrid_sql` | `natural_language` | Generate valid CUBRID SQL from natural language |
