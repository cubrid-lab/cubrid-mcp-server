# cubrid-mcp-server

A [Model Context Protocol](https://modelcontextprotocol.io) server for the [CUBRID](https://www.cubrid.org/) database. It lets LLM clients such as Claude Desktop, Claude Code, and Cursor safely inspect schemas and run **read-only** queries through the pure-Python [pycubrid](https://pypi.org/project/pycubrid/) driver.

```bash
uvx cubrid-mcp-server
```

## Why this server

- **Read-only by default.** A code-level SQL whitelist allows only `SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `EXPLAIN`, and `WITH` statements; multi-statement input is rejected. Write access is a separate, opt-in tool.
- **Schema-aware.** Twelve tools cover table discovery, column metadata, indexes, serials, class hierarchy, row counts, execution plans, and health checks — plus the same metadata as MCP Resources.
- **Multi-database.** One server process can serve several CUBRID databases, each with independent read-only, write, and audit settings.
- **Operations-friendly.** All logging goes to stderr (stdout is reserved for the MCP protocol stream), errors returned to the client are sanitized, and an opt-in audit log records every executed statement without ever logging raw SQL.

## Tool surface

| Tool | Description |
|------|-------------|
| `all_table_names` | List every user table in the database |
| `filter_table_names` | Substring search over table names |
| `schema_definitions` | Column types, nullability, defaults, and primary key info |
| `describe_table` | Full metadata: columns, primary key, and indexes in one call |
| `list_indexes` | Indexes for a table with key columns and flags |
| `explain_query` | Execution plan/trace for a `SELECT`/`WITH` (via CUBRID `SHOW TRACE`) |
| `table_row_counts` | `COUNT(*)` for one or many tables |
| `list_serials` | CUBRID `SERIAL` sequences with current value and bounds |
| `list_class_hierarchy` | CUBRID `CLASS` inheritance relationships |
| `execute_query` | Run read-only SQL with automatic output truncation |
| `health_check` | Verify database connectivity on demand |
| `execute_write` | Single `INSERT`/`UPDATE`/`DELETE` in an atomic transaction (**only registered when opt-in write mode is enabled**) |

See the full [Tools reference](TOOLS.md) for parameters and return shapes, the [Security Model](SECURITY_MODEL.md) for the safety design, and [Multi-Connection](MULTI_CONNECTION.md) for serving several databases from one process.

## Documentation

- [Quick Start](quickstart.md) — configure, run, and connect your first MCP client
- [Tools](TOOLS.md) — the complete tool, resource, and prompt reference
- [Security Model](SECURITY_MODEL.md) — read-only enforcement, opt-in writes, audit logging
- [Multi-Connection](MULTI_CONNECTION.md) — named connections and per-connection settings
- [Troubleshooting](TROUBLESHOOTING.md) — common problems and fixes
- [한국어 문서](README.ko.md)

## License

MIT — see [LICENSE](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/LICENSE).

> This project is part of [CUBRID Lab](https://github.com/cubrid-lab), an independent open-source initiative for CUBRID developer tooling, and is not affiliated with, sponsored by, or endorsed by CUBRID Corporation or the official CUBRID project.

## Ecosystem

Part of the cubrid-lab Python ecosystem:

- **cubrid-mcp-server** — MCP server — natural-language access for LLM clients
- [pycubrid](https://github.com/cubrid-lab/pycubrid) — Pure-Python DB-API 2.0 driver for CUBRID (sync + native asyncio)
- [sqlalchemy-cubrid](https://github.com/cubrid-lab/sqlalchemy-cubrid) — SQLAlchemy 2.0–2.2 dialect + Alembic
- [cubrid-cookbook-python](https://github.com/cubrid-lab/cubrid-cookbook-python) — 68 runnable examples and application templates
