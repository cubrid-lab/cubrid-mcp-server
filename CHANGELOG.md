# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Schema metadata is now exposed as read-only **MCP Resources** in addition to the existing tools: `cubrid://schema` (a whole-schema index listing every user table with its per-table resource URI) and the `cubrid://schema/{table}` template (per-table columns, primary key, and indexes, mirroring `describe_table`). Resources reuse the same read-only catalog queries — no new data access or write surface — and return `application/json`. (#124)
- MCP Prompt templates (`summarize_table`, `explain_query`, `inspect_schema`, `find_index_candidates`): guidance-only interaction templates that instruct clients which existing read-only tools to call. They never touch the database or execute SQL, add no new data-access surface, and fence user-supplied arguments as untrusted data. (#125)
- `ROADMAP.md` describing the current baseline, future direction, compatibility, and shipped history, matching the sibling repos in the Python line. (#96)
- Repo-local `CONTRIBUTING.md` documenting the Makefile targets, the CI gates a PR must clear (ruff, mypy strict, 95% coverage floor, lowest-direct, changelog lint), and how to run the integration suite against a live CUBRID. (#94)

### Changed
- Ruff's lint rule set is now declared explicitly (`select = ["E4", "E7", "E9", "F"]`) instead of inheriting ruff's implicit defaults, which grew from 59 to 413 rules in ruff 0.16 and broke CI on an unrelated version bump. (#88)

## [0.2.1] - 2026-08-06

### Security
- Read-only checker now scans the full token stream and rejects statements that begin with an allowed keyword but embed a forbidden one, e.g. a CTE `WITH ... DELETE` or a `SELECT ... FOR UPDATE`. (#40)
- `main()` fails fast with a clear stderr message when configuration is missing or invalid, instead of surfacing the error on the first tool call. (#46)

### Changed
- `execute_query` now caps results at `CUBRID_MCP_MAX_ROWS` (default 1000, streamed via `fetchmany`) and truncates oversized *individual values* rather than dropping whole rows; `row_count` reflects the number of rows actually returned. (#37, #38)
- Pinned `fastmcp>=3.0,<4`; the 2.x decorator typing behaviour is no longer supported. (#35)
- Schema/describe/index/row-count tools resolve the requested table against the catalog first and raise a clear error for unknown tables (excluding system classes and views). (#42, #43, #47)
- `explain_query` holds the connection lock across the whole `SET TRACE ... SHOW TRACE` sequence and no longer drains the user query result set. (#44)
- `table_row_counts` is capped at 50 tables per call. (#45)
- Binary column values are base64-encoded when small and summarized as `<binary N bytes>` when large. (#48)
- `Config.password` is excluded from `repr()`, and connection errors no longer echo the password or raw driver message. (#34, #41)
- The database wrapper closes stale connections before discarding them and serializes cursor access behind a re-entrant lock. (#33, #39)
- All logging is directed to stderr so it cannot corrupt the stdio MCP protocol stream on stdout. (#57)
- `--maxfail=25` removed from pytest defaults so the full failure surface is visible in CI. (#60)
- `explain_query` is documented as intentionally always read-only regardless of `CUBRID_MCP_READONLY`, since it only ever plans SELECT/WITH queries. (#59)
- `SECURITY.md` updated with correct per-table CUBRID GRANT syntax. (#49)

### Added
- `py.typed` marker so downstream users get type information; package version is now derived dynamically from `cubrid_mcp_server.__version__`. (#54, #55)
- CI reports coverage and runs a lowest-direct dependency-resolution job; the publish workflow verifies the tag matches the package version, runs `twine check`, and emits attestations. (#50, #51, #56)

### Fixed
- Corrected the repository org in project URLs and docs (`cubrid-labs` → `cubrid-lab`). (#53)
- README documents install-from-source path alongside `uvx`/`pipx` for PyPI. (#36)


## [0.2.0] - 2026-05-15

### Security
- `explain_query` now rejects multi-statement input as defense in depth, closing a bypass where input like `SELECT 1; DROP TABLE users` cleared the SELECT/WITH gate. (#29)

### Changed
- Raised `pycubrid` minimum from `>=1.0` to `>=1.4,<2` to pull in upstream bug fixes from the 1.x line. Setups pinned to older `pycubrid` releases will need to upgrade. (#28)
- `_render_rows` now always emits at least one row when truncating; previously a single oversized first row produced an empty `rows` list with `truncated: true`. (#30)
- `cubrid_mcp_server.__version__` is now in sync with `pyproject.toml` (was stuck at `0.0.1`).
  Note: this sync landed in the 0.2.0 source but the originally published 0.2.0 metadata may still reflect the old value; from `0.2.1` onward the version is derived dynamically to prevent drift. (#58)

### Added
- Edge-case test coverage across `safety`, `_render_rows`, `_coerce`, `explain_query` keyword acceptance, and `_quote_ident` escaping. (#31)

## [0.1.0] - 2026-04-13

Initial release. Six MCP tools for read-only CUBRID inspection: `all_table_names`, `filter_table_names`, `schema_definitions`, `describe_table`, `list_indexes`, `execute_query`.
