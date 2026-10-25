# Tools Reference

> 한국어: [도구 참조](ko/TOOLS.md)

`cubrid-mcp-server` exposes its capabilities as MCP **tools**, **resources**, and **prompts**. Every tool accepts an optional `connection` argument (see [Multi-Connection](MULTI_CONNECTION.md)); omitting it targets the `default` connection.

## Tools

The examples under each tool are real responses, captured by calling the tools over MCP stdio (FastMCP client) against the `cubrid/cubrid:11.4` Docker image, with `CUBRID_MCP_WRITE=1` and `CUBRID_MCP_MAX_ROWS=3` and this demo schema:

```sql
CREATE TABLE product (id INT PRIMARY KEY, name VARCHAR(40) NOT NULL, category VARCHAR(20), price NUMERIC(10,2));
CREATE INDEX idx_product_category ON product (category);
INSERT INTO product VALUES (1, 'Notebook', 'stationery', 3.50), (2, 'Pen', 'stationery', 1.20),
  (3, 'Desk lamp', 'furniture', 24.90), (4, 'Chair', 'furniture', 89.00), (5, 'Stapler', 'stationery', 7.80);
CREATE TABLE note (id INT AUTO_INCREMENT PRIMARY KEY, body VARCHAR(100) NOT NULL, created_at DATETIME DEFAULT SYS_DATETIME);
CREATE INDEX idx_note_created ON note (created_at DESC);
CREATE CLASS vehicle (maker VARCHAR(40));
CREATE CLASS car UNDER vehicle (doors INT);
CREATE SERIAL order_no START WITH 1000 INCREMENT BY 10;
```

The table, schema and index examples ran on this schema as created. Two writes ran next: `execute_write(sql="INSERT INTO note (body) VALUES ('first note')")`, shown under `execute_write`, and `execute_write(sql="INSERT INTO note (body) VALUES ('second note')")`, which returned the same `{"affected_rows": 1}`. They ran before `execute_query`, `explain_query`, `table_row_counts`, `list_serials` and `health_check`, so those examples see two `note` rows and the `note_ai_id` serial at `2`.

Each response is the tool's JSON text content, pretty-printed. Values such as `server_version` and serial values depend on your server.

### Schema inspection

**Table names and owners.** From CUBRID 11.2 on, two users may each own a table with the same name. On those servers the tools return table names as `owner.table` (owner in lower case, for example `dba.product`) and select metadata by owner and table name. A `table_name` argument may be `owner.table` or just `table`. An unqualified name matches a table of that name owned by anyone. If several owners have one, the configured user's own table is used, as CUBRID does for an unqualified name in SQL; otherwise the call fails with `ambiguous table name '…'; qualify it with the owner: …`. `filter_table_names` matches its substring against `owner.table`. On CUBRID 10.2 and 11.0 table names are unique in the database, so names are returned and matched without an owner, as before. The examples below ran on 11.4 as `dba`.

#### `all_table_names(connection=None)`

Lists every user table in the database. System and catalog tables are excluded.

Example: `all_table_names()` returns

```json
[
  "dba.car",
  "dba.note",
  "dba.product",
  "dba.vehicle"
]
```

#### `filter_table_names(substring, connection=None)`

Case-insensitive substring search over table names. Use this instead of `all_table_names` when the schema is large.

Example: `filter_table_names(substring="prod")` returns

```json
[
  "dba.product"
]
```

#### `schema_definitions(table_name, connection=None)`

Column-level metadata for one table: column name, type, nullability, default value, and primary-key membership.

Example: `schema_definitions(table_name="note")` returns

```json
[
  {
    "name": "id",
    "type": "INTEGER",
    "nullable": false,
    "default": null,
    "primary_key": true
  },
  {
    "name": "body",
    "type": "STRING",
    "nullable": false,
    "default": null,
    "primary_key": false
  },
  {
    "name": "created_at",
    "type": "DATETIME",
    "nullable": true,
    "default": "SYS_DATETIME",
    "primary_key": false
  }
]
```

#### `describe_table(table_name, connection=None)`

Full metadata for one table in a single call — columns, primary key, and indexes. Mirrors the `cubrid://schema/{table}` resource.

`primary_key` lists the key columns in **declared primary-key order** (the order in `PRIMARY KEY (...)`, i.e. CUBRID's `db_index_key.key_order`), matching the primary-key entry in `indexes`. `columns` stays in table-definition order, with a per-column boolean `primary_key` flag. A table without a primary key returns `"primary_key": []`.

Example: `describe_table(table_name="note")` returns

```json
{
  "table": "dba.note",
  "columns": [
    {
      "name": "id",
      "type": "INTEGER",
      "nullable": false,
      "default": null,
      "primary_key": true
    },
    {
      "name": "body",
      "type": "STRING",
      "nullable": false,
      "default": null,
      "primary_key": false
    },
    {
      "name": "created_at",
      "type": "DATETIME",
      "nullable": true,
      "default": "SYS_DATETIME",
      "primary_key": false
    }
  ],
  "primary_key": ["id"],
  "indexes": [
    {
      "name": "idx_note_created",
      "unique": false,
      "primary_key": false,
      "foreign_key": false,
      "reverse": false,
      "key_count": 1,
      "columns": [
        {
          "name": "created_at",
          "order": 0,
          "asc_desc": "DESC"
        }
      ]
    },
    {
      "name": "pk_note_id",
      "unique": true,
      "primary_key": true,
      "foreign_key": false,
      "reverse": false,
      "key_count": 1,
      "columns": [
        {
          "name": "id",
          "order": 0,
          "asc_desc": "ASC"
        }
      ]
    }
  ]
}
```

#### `list_indexes(table_name, connection=None)`

Indexes defined on a table, with the indexed key columns and flags (unique, reverse).

Example: `list_indexes(table_name="note")` returns

```json
[
  {
    "name": "idx_note_created",
    "unique": false,
    "primary_key": false,
    "foreign_key": false,
    "reverse": false,
    "key_count": 1,
    "columns": [
      {
        "name": "created_at",
        "order": 0,
        "asc_desc": "DESC"
      }
    ]
  },
  {
    "name": "pk_note_id",
    "unique": true,
    "primary_key": true,
    "foreign_key": false,
    "reverse": false,
    "key_count": 1,
    "columns": [
      {
        "name": "id",
        "order": 0,
        "asc_desc": "ASC"
      }
    ]
  }
]
```

#### `list_class_hierarchy(table_name=None, connection=None)`

CUBRID `CLASS` inheritance relationships — which tables inherit from which. Omit `table_name` for every class, or pass one to get only that table's direct super classes. From CUBRID 11.2 on, class and super class names are `owner.table`. `table_name` is resolved like the other schema tools: matched case-insensitively against user tables, and an unknown table (including system classes and views) raises `unknown table` instead of returning an empty list.

Example: `list_class_hierarchy(table_name="car")` returns

```json
[
  {
    "class_name": "dba.car",
    "super_classes": ["dba.vehicle"]
  }
]
```

### Querying

#### `execute_query(sql, connection=None)`

Runs **read-only** SQL (`SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `WITH`) and only statements that return a result set. Use `explain_query` for query plans. Output is automatically truncated to respect the model's context window:

- at most `CUBRID_MCP_MAX_ROWS` rows (default 1000),
- rendered output capped at `CUBRID_MCP_MAX_CHARS` characters (default 4000), counted as the text length of every value across all rows (JSON quotes and separators are not counted; `null` counts 4). Rows are returned while they fit whole. A first row that alone is longer is still returned, cut to the cap: values that fit are kept, the first that does not is shortened to end in `…` (a non-string value becomes `…`), and every later value becomes `…` (an empty string stays empty), so a cut row can exceed the cap by one character per later column. `truncated` is `true` whenever a row was left out or a value was cut,
- statement length capped at `CUBRID_MCP_MAX_SQL_LENGTH` (default 65536),
- per-statement socket read timeout of `CUBRID_MCP_QUERY_TIMEOUT` seconds (default 30).

Multi-statement and empty (comment-only or `;`-only) input is rejected, also with `CUBRID_MCP_READONLY=0`. Comments (`--`, `//`, `/* ... */`), quotes and `;` are read with CUBRID's rules, so a comment cannot hide the leading keyword; input with an unterminated quote, or with a backslash that would change where a quote ends, is rejected. Binary values up to `CUBRID_MCP_MAX_INLINE_BINARY_BYTES` bytes (default 256) are base64-encoded; larger ones are summarized (`<binary N bytes>`).

`execute_query` also rejects `INCR`, `DECR`, the serial advances `NEXT_VALUE`, `NEXTVAL` and `SERIAL_NEXT_VALUE`, and the click counter `WITH INCREMENT FOR` / `WITH DECREMENT FOR`, in any case, bare or quoted and anywhere in the statement: they change data inside a `SELECT`, the rollback does not undo them, and a `SELECT`-only grant does not prevent them. `CURRENT_VALUE`, `CURRVAL` and `SERIAL_CURRENT_VALUE` stay allowed. With `CUBRID_MCP_READONLY=0` `execute_query` rejects these forms too. See the [Security Model](SECURITY_MODEL.md).

Every read ends its own transaction: the server rolls back after the rows are collected (truncated or not), so no locks or snapshot are held between tool calls and the next call sees rows other sessions have committed. `execute_query` never commits. `CUBRID_MCP_READONLY=0` relaxes the whitelist but still keeps writes out of `execute_query`: statements that lead with a write, DDL or transaction-control keyword (`INSERT`, `UPDATE`, `DELETE`, `REPLACE`, `MERGE`, `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `RENAME`, `GRANT`, `REVOKE`, `COMMIT`, `ROLLBACK`, `SAVEPOINT`, `SET`, `PREPARE`, `EXECUTE`, `DEALLOCATE`, `DO`), method calls (`CALL`, `EVALUATE`) and `KILL` are rejected before they reach the database, with an error pointing to `execute_write`; the first word of the leading keyword and of the statement is matched, so `CREATE OR REPLACE …` is rejected like `CREATE`. `CALL` is rejected because `CALL login(...) ON CLASS db_user` would switch the user of the shared session for every later tool call; no tool runs it. This keyword check is a guardrail, not a security boundary: the read-only database account remains the boundary. A statement that still returns no result set is rolled back and fails with `statement produced no result set; execute_query is read-only, use execute_write …`; the connection is kept. Use `execute_write` for writes.

> **Migration:** clients that sent `INSERT`/`UPDATE`/`DELETE` through `execute_query` with `CUBRID_MCP_READONLY=0` must use `execute_write` (`CUBRID_MCP_WRITE=1`) instead.

Example: with `CUBRID_MCP_MAX_ROWS=3`, the five-row result is cut to three rows and `truncated` is `true`. `NUMERIC` values are returned as strings, so no precision is lost. `execute_query(sql="SELECT id, name, category, price FROM product ORDER BY id")` returns

```json
{
  "row_count": 3,
  "truncated": true,
  "rows": [
    [1, "Notebook", "stationery", "3.50"],
    [2, "Pen", "stationery", "1.20"],
    [3, "Desk lamp", "furniture", "24.90"]
  ]
}
```

Rejected: `execute_query(sql="DELETE FROM note")` fails (`isError: true`) with

```text
Error calling tool 'execute_query': DELETE is not permitted in read-only mode; allowed statements: DESC, DESCRIBE, SELECT, SHOW, WITH
```

#### `explain_query(sql, connection=None)`

Returns the execution plan/trace for a `SELECT` or `WITH` statement via CUBRID `SHOW TRACE`. The statement is **actually executed** under `SET TRACE ON` (it consumes real database resources and can run as long as the query itself); the trace is read, tracing is turned off and the transaction is rolled back as best-effort cleanup. If that cleanup fails (the cleanup cursor cannot be opened, `SET TRACE OFF` fails or the rollback fails), the plan is still returned, the failure is logged to stderr and the connection is discarded, so the next call opens a fresh one; after a query timeout no cleanup statement is sent. It applies the read-only checks independent of the `CUBRID_MCP_READONLY` flag, so it also rejects `INCR`, `DECR`, serial advances and the click counter, which would otherwise change data when the statement runs; the database account's privileges still apply. CUBRID has no `EXPLAIN` statement; this is the tool for execution plans. The leading keyword is read the same way as the SQL checks read it, so `SELECT*FROM t` and `(SELECT 1)` are accepted like in `execute_query`; only `SELECT` and `WITH` statements are. A statement the server rejects (for example, an unknown table) fails with `query failed: ProgrammingError` and keeps the connection, as in `execute_query`. The plan is capped at `CUBRID_MCP_MAX_CHARS` characters, ending in `…` when cut, and `truncated` says whether it was cut; the `sql` echo is the statement as sent, bounded by `CUBRID_MCP_MAX_SQL_LENGTH`.

Example: `explain_query(sql="SELECT name, price FROM product WHERE category = 'furniture'")` returns

```json
{
  "sql": "SELECT name, price FROM product WHERE category = 'furniture'",
  "plan": "Query Plan:\n  INDEX SCAN (dba.product.idx_product_category) (key range: [dba.product].category= ?:0 )\n\n  rewritten query: select [dba.product].[name], [dba.product].price from [dba.product] [dba.product] where [dba.product].category= ?:0 \n\nTrace Statistics:\n  SELECT (time: 0, fetch: 4, fetch_time: 0, ioread: 0)\n    SCAN (index: dba.product.idx_product_category), (btree time: 0, fetch: 3, ioread: 0, readkeys: 1, filteredkeys: 0, rows: 2) (lookup time: 0, rows: 2)",
  "truncated": false
}
```

#### `table_row_counts(table_names=None, connection=None)`

`COUNT(*)` for one table or many — cheaper than sampling rows to estimate size. Returns `{"tables": [{"table", "row_count"}, …], "truncated": bool, "total_tables": int}`, where `total_tables` is the number of user tables in the database; a table that is unknown, ambiguous (see [Table names and owners](#schema-inspection)) or fails to count has `"row_count": null` and an `error`. From CUBRID 11.2 on, `COUNT(*)` names the table as `"OWNER"."table"`, so a table owned by another user is counted even when the configured user has a table of that name or none.

- Omitted or `None`: counts the first 50 user tables in name order. If the database has more, `truncated` is `true`; pass the remaining names (from `all_table_names`) in batches of up to 50.
- Explicit list: counts those tables; more than 50 names raises `too many tables requested (N); limit is 50 per call`.
- The limit of 50 is the default of `CUBRID_MCP_MAX_ROW_COUNT_TABLES` (per connection: `CUBRID_<NAME>_MCP_MAX_ROW_COUNT_TABLES`).
- Empty list (`[]`): counts nothing and returns `"tables": []`.

Example: `table_row_counts(table_names=["product", "note", "missing_table"])` returns

```json
{
  "tables": [
    {
      "table": "dba.product",
      "row_count": 5
    },
    {
      "table": "dba.note",
      "row_count": 2
    },
    {
      "table": "missing_table",
      "row_count": null,
      "error": "unknown table"
    }
  ],
  "truncated": false,
  "total_tables": 4
}
```

### CUBRID specifics

#### `list_serials(connection=None)`

CUBRID `SERIAL` sequences with their current value, minimum, maximum, and increment.

Example: `list_serials()` returns

```json
[
  {
    "name": "note_ai_id",
    "current_value": "2",
    "increment": "1",
    "max_value": "2147483647",
    "min_value": "1",
    "cyclic": false,
    "started": true,
    "class_name": "note",
    "attribute_name": "id",
    "cached_num": 0,
    "comment": null
  },
  {
    "name": "order_no",
    "current_value": "1000",
    "increment": "10",
    "max_value": "99999999999999999999999999999999999999",
    "min_value": "1000",
    "cyclic": false,
    "started": false,
    "class_name": null,
    "attribute_name": null,
    "cached_num": 0,
    "comment": null
  }
]
```

The `db_serial` catalog column was renamed from `att_name` to `attr_name` in CUBRID 11.4, so the server probes once per connection which spelling the server has, and only a server rejecting one spelling moves it to the other. A timeout or a lost connection during that probe is reported as such, and if the probe's connection is reset the call fails with `connection was reset while probing db_serial; retry the request` rather than reusing the answer on a new connection.

#### `health_check(connection=None)`

Verifies database connectivity on demand and reports per-connection status. Useful after environment changes or long idle periods.

Example: `health_check()` returns

```json
{
  "ok": true,
  "server_version": "11.4.6.1963"
}
```

### Opt-in writes

#### `execute_write(sql, connection=None)`

Runs a **single** `INSERT`, `UPDATE`, or `DELETE` statement in an explicit transaction (commit on success, rollback on any failure). **Registered only when write mode is enabled** (`CUBRID_MCP_WRITE=1` or `CUBRID_<NAME>_MCP_WRITE=1` on any connection) — with write mode off, the tool does not exist in MCP capability discovery at all.

Constraints: DDL (`CREATE`/`ALTER`/`DROP`/`TRUNCATE`), standalone reads, transaction control, and multi-statement input are rejected. DDL is excluded because `execute_write` is a DML tool and `execute_query` is read-only, not because of DDL auto-commit. See the [Security Model](SECURITY_MODEL.md).

The result is `{"affected_rows": N}`, returned after the commit. A statement that matches no rows still succeeds and returns `"affected_rows": 0`. A rejected statement is never sent to the database, and a statement that fails is rolled back. If the commit itself times out (`CUBRID_MCP_QUERY_TIMEOUT`), the connection is discarded and the outcome is unknown: the server may have committed before its reply was lost, so check the data before retrying.

Example: `execute_write(sql="INSERT INTO note (body) VALUES ('first note')")` returns

```json
{
  "affected_rows": 1
}
```

Example: `execute_write(sql="UPDATE note SET body = 'edited' WHERE id = 999")` returns

```json
{
  "affected_rows": 0
}
```

Rejected: `execute_write(sql="DROP TABLE note")` fails (`isError: true`) with

```text
Error calling tool 'execute_write': DROP is not permitted in write mode; allowed statements: DELETE, INSERT, UPDATE
```

## Resources

Schema metadata is also exposed as read-only [MCP Resources](https://modelcontextprotocol.io/docs/concepts/resources), so clients can discover schema context without a tool call. Resources reuse the same read-only catalog queries — no additional data-access surface.

| Resource URI | MIME type | Description |
|--------------|-----------|-------------|
| `cubrid://agent-guide` | `text/markdown` | Comprehensive CUBRID agent guide: SQL dialect, types, safety, performance, tool selection |
| `cubrid://guide/sql-dialect` | `text/markdown` | CUBRID syntax differences from MySQL/PostgreSQL |
| `cubrid://guide/types` | `text/markdown` | Data type guide: collections, ENUM, JSON, Python mapping |
| `cubrid://guide/performance` | `text/markdown` | Performance optimization: SHOW TRACE, indexes, anti-patterns |
| `cubrid://guide/collections` | `text/markdown` | Deep dive on SET, MULTISET, SEQUENCE types |
| `cubrid://schema` | `application/json` | Whole-schema index: every user table with its per-table resource URI |
| `cubrid://schema/{table}` | `application/json` | Per-table metadata (columns, primary key, indexes) — mirrors `describe_table` |

The `cubrid://guide/*` documents and the agent guide are static Markdown. The schema resources always read the `default` connection and take no `connection` argument (see [Multi-Connection](MULTI_CONNECTION.md)). Table names in `{table}` are percent-decoded by URI-template matching; an unknown or system table produces a resource-read error, matching the `describe_table` tool.

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
