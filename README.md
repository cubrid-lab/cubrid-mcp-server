# cubrid-mcp-server

A [Model Context Protocol](https://modelcontextprotocol.io) server for [CUBRID](https://www.cubrid.org/), enabling LLMs to safely inspect schemas and execute read-only queries over [pycubrid](https://pypi.org/project/pycubrid/).

> 🚧 **Status:** Early development. Not yet released.

## Planned Tools

- `all_table_names` — list every table in the connected database
- `filter_table_names` — substring search over table names
- `schema_definitions` — column types, keys, and foreign relationships
- `execute_query` — run SQL (read-only by default)

## Design Principles

- **Secure by default** — read-only SQL whitelist enforced in code, layered on top of database-level permissions
- **Minimal surface area** — four focused tools inspired by [`mcp-alchemy`](https://github.com/runekaagaard/mcp-alchemy)
- **Ops-friendly** — environment-variable configuration, clear security guidance

## License

Apache-2.0 (see [`LICENSE`](./LICENSE)).
