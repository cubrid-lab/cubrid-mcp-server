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

#### `list_indexes(table_name, connection=None)`

Indexes defined on a table, with the indexed key columns and flags (unique, reverse).

#### `list_class_hierarchy(connection=None, ...)`

CUBRID `CLASS` inheritance relationships — which tables inherit from which.

### Querying

#### `execute_query(sql, connection=None)`

Runs **read-only** SQL (`SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `EXPLAIN`, `WITH`). Output is automatically truncated to respect the model's context window:

- at most `CUBRID_MCP_MAX_ROWS` rows (default 1000),
- rendered output capped at `CUBRID_MCP_MAX_CHARS` characters (default 4000),
- statement length capped at `CUBRID_MCP_MAX_SQL_LENGTH` (default 65536),
- per-statement socket read timeout of `CUBRID_MCP_QUERY_TIMEOUT` seconds (default 30).

Multi-statement input is rejected. Binary values are base64-encoded when small and summarized (`<binary N bytes>`) when large.

#### `explain_query(sql, connection=None)`

Returns the execution plan/trace for a `SELECT` or `WITH` statement via CUBRID `SHOW TRACE`. Always read-only, independent of the `CUBRID_MCP_READONLY` flag.

#### `table_row_counts(connection=None, ...)`

`COUNT(*)` for one table or many — cheaper than sampling rows to estimate size.

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
