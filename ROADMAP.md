# Roadmap

> **Last updated**: 2026-08-25
>
> This roadmap reflects current priorities. For the ecosystem-wide view, see the
> [CUBRID Labs Ecosystem Roadmap](https://github.com/cubrid-lab/.github/blob/main/ROADMAP.md).

## Links

- 📋 [GitHub Milestones](https://github.com/cubrid-lab/cubrid-mcp-server/milestones)
- 🗂️ [Org Project Board](https://github.com/orgs/cubrid-lab/projects/2)
- 🌐 [Ecosystem Roadmap](https://github.com/cubrid-lab/.github/blob/main/ROADMAP.md)

## Current Baseline — v0.2.1

- MCP server (stdio transport) exposing eleven read-only tools for schema
  inspection and query execution over the pure-Python
  [pycubrid](https://pypi.org/project/pycubrid/) driver.
- Read-only by default: a code-level SQL whitelist allows only `SELECT`, `SHOW`,
  `DESC`, `DESCRIBE`, `EXPLAIN`, and `WITH`, rejects multi-statement input, and
  is backed by a database user with `SELECT`-only grants.
- Output safety: row caps (`CUBRID_MCP_MAX_ROWS`), per-value truncation,
  base64-encoded binary values, and sanitized error messages.
- All logging is routed to `stderr` so it cannot corrupt the stdio protocol
  stream on `stdout`.

_See **Completed** for the per-release history._

## Future

Direction is set by the maintainers ([@paikend](https://github.com/paikend),
[@yeongseon](https://github.com/yeongseon)); see [issue #23](https://github.com/cubrid-lab/cubrid-mcp-server/issues/23)
for the v0.3.x tracking epic. Items under consideration:

- First PyPI release so the server can be run with `uvx` / `pipx`.
- Additional read-only introspection tools (constraints, triggers, statistics).
- Optional per-request connection context / multi-database support.

## Compatibility

Python 3.10+, CUBRID 11.2 (exercised in the integration CI job).

## Completed

### v0.2.1
- Read-only checker scans the full token stream and rejects allowed keywords
  that embed a forbidden one (e.g. `WITH ... DELETE`, `SELECT ... FOR UPDATE`). (#40)
- `main()` fails fast on missing/invalid configuration instead of erroring on the
  first tool call. (#46)
- `execute_query` row caps, per-value truncation, and binary value handling. (#37, #38, #48)
- `py.typed` marker and dynamically derived package version. (#54, #55)
- CI reports coverage and runs a lowest-direct dependency-resolution job. (#50, #51, #56)

### v0.2.0
- `explain_query` rejects multi-statement input as defense in depth. (#29)
- Raised `pycubrid` minimum to `>=1.4,<2`. (#28)
- Edge-case test coverage across `safety`, `_render_rows`, `_coerce`, and
  `explain_query`. (#31)

### v0.1.0
- Initial release: read-only CUBRID inspection tools over the MCP protocol.
