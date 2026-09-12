# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Documentation
- **Demo GIF embedded in README** — programmatic MCP server interaction showing initialize → tools list → read-only whitelist.
- **CUBRID Skills — domain knowledge + expert prompts (#162)** — the server now ships with a knowledge layer so LLM clients can use CUBRID effectively without prior CUBRID expertise: (1) server instructions sent on connect (CUBRID dialect primer), (2) enriched tool descriptions with CUBRID-specific hints (LIMIT syntax, SHOW TRACE, USING INDEX), (3) five domain-knowledge resources (`cubrid://agent-guide` + 4 topic guides on sql-dialect/types/performance/collections), (4) five expert prompts (`optimize_query`, `migrate_from_mysql`, `explore_unknown_db`, `safe_data_analysis`, `write_cubrid_sql`). 10 new tests. Oracle-validated design.
- **Oracle post-implementation review fixes**: corrected LIMIT syntax claim (comma form is valid), acknowledged NOW()/CURRENT_DATE as supported aliases, corrected SERIAL nomenclature (objects not types), replaced undocumented collection methods with standard operators, hedged performance claims, added 'for human approval — do not execute' guardrails to DDL suggestions, distinguished read-only vs DML validation in write_cubrid_sql prompt. 5 regression tests added (284 total).
- **한국어 문서 페이지 (#160)** — 사이트 문서 5개 페이지(quickstart·TOOLS·보안 모델·멀티커넥션·문제 해결)의 한국어 번역을 `docs/ko/`에 추가하고 Project → Translations → 한국어 문서로 노출. 페이지 번역은 경고 수준 동기화(README.ko의 하드 게이트는 유지).
- **Korean docs governance** — `docs/README.ko.md` carries a sync marker, and docs-sync gained a `translation-sync` job that fails a PR when `README.md` changes without the translation changing (escape hatch: the `translations-deferred` label).
- **Docs site information architecture unified across the ecosystem** — nav reorganized to the shared six-tab skeleton (Home / Getting Started / Usage / Reference / Operations / Project): Tools and Multi-Connection under Usage, Security Model under Reference, 한국어 under Project → Translations; homepage gains an Ecosystem section linking the three sibling sites.
- **Community files**: bug/feature issue templates (adapted from the siblings, with an MCP-specific environment field: server/Python/CUBRID/client versions), `SUPPORT.md`, and `CODE_OF_CONDUCT.md` — the repo previously relied on org-level fallbacks only. README gains the docs-site badge matching pycubrid and sqlalchemy-cubrid.
- README gains a **Related Projects** section linking pycubrid, sqlalchemy-cubrid, and cubrid-cookbook-python, matching the sibling packages' READMEs — every cubrid-lab PyPI page now leads to the runnable examples.

### Fixed
- **create-release.yml: dropped `--target` from `gh release create`** — with an already-pushed tag (the normal tag-push trigger) `--verify-tag` already guarantees the tag exists, and passing `target_commitish` for an existing tag makes the Releases API return `422 Validation Failed`, so the first tag-triggered run of this workflow always failed. Verified live by the v0.4.0 tag attempt in cubrid-mcp-server.

### Fixed
- `list_serials` now works on **CUBRID 11.4**: the `db_serial` system catalog renamed its `att_name` column to `attr_name` in 11.4, so the hardcoded query failed there with a semantic error. The column is now resolved once per connection by a zero-row probe against a fixed allowlist and aliased back to `att_name`, keeping the tool's output shape identical on both versions. Found by the new 11.2+11.4 integration matrix.

### CI
- Integration tests now run against a CUBRID **11.2 + 11.4 job matrix** (previously 11.2 only), matching the pycubrid/sqlalchemy-cubrid integration matrices and the cookbook smoke matrix.

### Documentation
- **CUBRID server license relationship documented; copyright and authors unified (#150)** — `THIRD_PARTY_LICENSES.md` carries the verified upstream licensing statement (server engine Apache-2.0, APIs/connectors BSD per CUBRID's `COPYING` — the often-cited GPL v2+ no longer applies; independent wire-protocol client, Docker image CI-only). LICENSE/NOTICE copyright lines now read `Yeongseon Choe, Gyeongjun Paik` (2025-2026), and `pyproject.toml` lists both primary authors.

## [0.4.0] - 2026-09-09

### Added
- Published to PyPI: `uvx cubrid-mcp-server` and `pipx run cubrid-mcp-server` now install from PyPI instead of a git checkout.
- Documentation site (mkdocs-material) deployed to https://cubrid-lab.github.io/cubrid-mcp-server/ — quickstart, full tool reference, security model, multi-connection guide, and troubleshooting.
- Korean README translation (`docs/README.ko.md`), matching the sibling repositories' translation set.
- `upstream-canary.yml` now also tracks `fastmcp@latest` in addition to `pycubrid@main`, giving the eventual fastmcp 4.x migration decision CI evidence. The dependency pin intentionally remains `>=3.0,<4` until that canary is green.
- `THIRD_PARTY_LICENSES.md` (full runtime license inventory, pip-licenses generated) and a `NOTICE` file (original implementation, no third-party code embedded) added.
- Official MCP Registry readiness: PyPI ownership-verification marker (`mcp-name: io.github.cubrid-lab/cubrid-mcp-server`) embedded in README, and `glama.json` added at the repo root for Glama registry indexing.

### Changed
- Development Status classifier raised from `2 - Pre-Alpha` to `4 - Beta`: the server has shipped multi-database connections, opt-in write mode, audit logging, Resources, and Prompts since 0.3.0.
- `[project.urls]` now includes `Documentation` and `Changelog` links, matching the sibling repositories.
- `Framework :: AsyncIO` trove classifier added for registry/search discoverability.

### Fixed
- README: removed a duplicated `CUBRID_MCP_WRITE` row in the configuration table.

## [0.3.1] - 2026-09-02

### Fixed
- `execute_write` now honours the per-call `connection` argument instead of always writing to the `default` connection, matching the read tools and the v0.3.0 multi-connection contract. (#136)
- Per-connection `CUBRID_<NAME>_MCP_WRITE` and `CUBRID_<NAME>_MCP_AUDIT_LOG` settings are now actually applied: write-enablement is enforced against the *target* connection's config (a connection with writes off refuses even when another enables them), the `execute_write` tool is registered whenever **any** connection opts into write mode, and audit logging is resolved per connection so a named connection's `MCP_AUDIT_LOG` takes effect independently of the default. `execute_write` calls are now audited as well. (#137)

## [0.3.0] - 2026-09-01

### Added
- Schema metadata is now exposed as read-only **MCP Resources** in addition to the existing tools: `cubrid://schema` (a whole-schema index listing every user table with its per-table resource URI) and the `cubrid://schema/{table}` template (per-table columns, primary key, and indexes, mirroring `describe_table`). Resources reuse the same read-only catalog queries — no new data access or write surface — and return `application/json`. (#124)
- Opt-in audit logging (`CUBRID_MCP_AUDIT_LOG`, off by default): emits one redaction-safe JSON record per executed statement (`execute_query`/`explain_query`) to stderr with the statement category, extracted table identifiers, timing, and row counts. Raw SQL text, bound parameters, and literal values are never logged. (#127)
- MCP Prompt templates (`summarize_table`, `explain_query`, `inspect_schema`, `find_index_candidates`): guidance-only interaction templates that instruct clients which existing read-only tools to call. They never touch the database or execute SQL, add no new data-access surface, and fence user-supplied arguments as untrusted data. (#125)
- `ROADMAP.md` describing the current baseline, future direction, compatibility, and shipped history, matching the sibling repos in the Python line. (#96)
- Multi-database connection management: configure additional named connections via `CUBRID_CONNECTIONS` plus `CUBRID_<NAME>_*` variables, and target them per call with the new optional `connection` argument on every tool. The bare `CUBRID_*` variables continue to define the reserved `default` connection, so single-database setups are unchanged. Each connection has its own lock, read-only enforcement, and stale-connection lifecycle. (#126)
- Opt-in write mode (`CUBRID_MCP_WRITE=1`) exposing an `execute_write` tool that runs a single `INSERT`/`UPDATE`/`DELETE` statement in an atomic transaction (commit on success, rollback on failure). Disabled by default; when off the tool is not registered so no write path is exposed. DDL is intentionally unsupported (CUBRID auto-commits DDL) and `execute_query` stays read-only regardless. (#123)
- Repo-local `CONTRIBUTING.md` documenting the Makefile targets, the CI gates a PR must clear (ruff, mypy strict, 95% coverage floor, lowest-direct, changelog lint), and how to run the integration suite against a live CUBRID. (#94)

### Security
- Write mode is strictly gated: a dedicated DML-only whitelist (`ensure_write_allowed`) rejects standalone reads, DDL, transaction-control, and multi-statement input, and leaves the read-only default path unchanged. (#123)

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
