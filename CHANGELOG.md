# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Python 3.11 is now the minimum supported version (#221)** — `requires-python` is `>=3.11` (Python 3.10 reached upstream end of life on 2026-10-01); the 3.10 classifier is removed, Ruff targets `py311` and mypy `3.11`. Python 3.14 is added to the classifiers and the unit/full-integration matrices after the offline suite (459 tests), Ruff and mypy passed on 3.14. The `lowest-direct` job and Codecov upload moved to 3.11; lowest-direct resolves FastMCP 3.0.0, pycubrid 1.4.0 and sqlparse 0.5.0 and passes. No MCP, SQL-safety, timeout or audit behavior changes; direct dependency floors are unchanged.

### CI
- **Tiered PR, main and compatibility validation (#223)** — a `classify` job (`scripts/ci_scope.py`) maps the event and changed paths to explicit scopes, and only the selected lanes run. Docs/metadata-only PRs start no unit job and no CUBRID container; ordinary runtime/test PRs run one Python 3.12 unit lane and one CUBRID 11.4 live lane; connection/catalog changes add CUBRID 11.2; workflow and dependency-metadata changes run the Python 3.11/3.12/3.14 and CUBRID 11.2/11.4 endpoints (plus `lowest-direct` for `pyproject.toml`); pushes to `main` and CI-policy changes run all of those. Codecov uploads from 3.12. The required `ci-gate` now fails on a failed classification and on any failed, cancelled or unexpectedly skipped lane — a lane may be skipped only when the classification says it does not apply (previously a failed path filter silently skipped integration). `integration-full.yml` no longer runs the 16-cell Python × CUBRID matrix daily: it runs in full weekly (Sunday) and on dispatch, runs only the oldest/newest corners (3.11 × 10.2, 3.14 × 11.4) Monday–Saturday, and still runs in full, fail-closed, as the release gate. Measured on recent runs: docs-only PR 8 → 3 jobs, ordinary runtime PR 10 → 5 jobs (2 → 1 CUBRID), scheduled matrix ≈133 → ≈44 billed runner-minutes per week. No runtime, SQL-safety, write-mode, audit or release-flow change.

### Upgrade notes
- **Python 3.10 users** must either upgrade to Python 3.11 or later, or stay on the last cubrid-mcp-server release that supports 3.10 together with a driver release compatible with 3.10. Newer pycubrid lines (1.10+) do not support Python 3.10, and this project does not imply otherwise.

### Tests
- **Live shared-session concurrency regression (#211)** — two simultaneous in-process tool calls now verify that `execute_query` waits while `explain_query` owns the real `SET TRACE` context on the cached Database connection. The test checks distinct responses, connection reuse and closure of every real cursor, including trace cleanup. It exercises the existing serialized RLock model, not MCP stdio concurrency, a connection pool or per-request transaction isolation. No runtime change.

### Documentation
- **Reproducible third-party license inventory; FastMCP range corrected (#218)** — `THIRD_PARTY_LICENSES.md` described the direct dependency as `fastmcp>=3.0,<4` while `pyproject.toml` allows `>=3.0,<5`; a direct-dependency table now shows the allowed ranges from `pyproject.toml` separately from the versions observed in the snapshot (FastMCP 4.0.11). The runtime (70 packages) and `.[dev]` (37 additions) inventories are regenerated in fresh environments at a recorded commit, Python and OS by `scripts/generate_third_party_licenses.py` (shared with pycubrid and sqlalchemy-cubrid), with a **Required by** column attributing each transitive package to what pulls it in. Every runtime package is permissive; MPL-2.0 (`certifi`, `pathspec`) now appears only in the dev toolchain and is classified as weak file-level copyleft instead of under a blanket "no copyleft" statement, and docutils' GPL classifier is resolved from its own `COPYING`. `tests/test_third_party_licenses.py` fails when the documented ranges disagree with `pyproject.toml`, a declared dependency is missing or outside its range (exact `==` pins are checked for presence only), a row has no parent or the dev table repeats a runtime package, or a category disagrees with the generator; `scripts/ci_scope.py` now routes `THIRD_PARTY_LICENSES.md` changes to the unit lane that runs it. The package contract is unchanged.
- **Durable security support wording and review routing (#224)** — `SECURITY.md` states that only the latest published release receives security fixes, replacing the stale 0.2.x early-development note; email remains the private reporting channel. `.github/CODEOWNERS` requests maintainer review for release, CI-policy, configuration and SQL-safety/write-mode/audit/protocol files. ROADMAP current-state prose is refreshed.
- **PyPI badge added to README** — version badge linking to https://pypi.org/project/cubrid-mcp-server/
- **Demo GIF embedded in README** — programmatic MCP server interaction showing initialize → tools list → read-only whitelist.
- **CUBRID Skills — domain knowledge + expert prompts (#162)** — the server now ships with a knowledge layer so LLM clients can use CUBRID effectively without prior CUBRID expertise: (1) server instructions sent on connect (CUBRID dialect primer), (2) enriched tool descriptions with CUBRID-specific hints (LIMIT syntax, SHOW TRACE, USING INDEX), (3) five domain-knowledge resources (`cubrid://agent-guide` + 4 topic guides on sql-dialect/types/performance/collections), (4) five expert prompts (`optimize_query`, `migrate_from_mysql`, `explore_unknown_db`, `safe_data_analysis`, `write_cubrid_sql`). 10 new tests. Oracle-validated design.
- **Oracle post-implementation review fixes**: corrected LIMIT syntax claim (comma form is valid), acknowledged NOW()/CURRENT_DATE as supported aliases, corrected SERIAL nomenclature (objects not types), replaced undocumented collection methods with standard operators, hedged performance claims, added 'for human approval — do not execute' guardrails to DDL suggestions, distinguished read-only vs DML validation in write_cubrid_sql prompt. 5 regression tests added (284 total).
- **한국어 문서 페이지 (#160)** — 사이트 문서 5개 페이지(quickstart·TOOLS·보안 모델·멀티커넥션·문제 해결)의 한국어 번역을 `docs/ko/`에 추가하고 Project → Translations → 한국어 문서로 노출. 페이지 번역은 경고 수준 동기화(README.ko의 하드 게이트는 유지).
- **Korean docs governance** — `docs/README.ko.md` carries a sync marker, and docs-sync gained a `translation-sync` job that fails a PR when `README.md` changes without the translation changing (escape hatch: the `translations-deferred` label).
- **Docs site information architecture unified across the ecosystem** — nav reorganized to the shared six-tab skeleton (Home / Getting Started / Usage / Reference / Operations / Project): Tools and Multi-Connection under Usage, Security Model under Reference, 한국어 under Project → Translations; homepage gains an Ecosystem section linking the three sibling sites.
- **Community files**: bug/feature issue templates (adapted from the siblings, with an MCP-specific environment field: server/Python/CUBRID/client versions), `SUPPORT.md`, and `CODE_OF_CONDUCT.md` — the repo previously relied on org-level fallbacks only. README gains the docs-site badge matching pycubrid and sqlalchemy-cubrid.
- README gains a **Related Projects** section linking pycubrid, sqlalchemy-cubrid, and cubrid-cookbook-python, matching the sibling packages' READMEs — every cubrid-lab PyPI page now leads to the runnable examples.

### Fixed
- **Accept leading comments in `explain_query` (#178)** — SELECT/WITH statements now use the same comment normalization as the read-only safety checker before the leading-token gate.
- **Blank required connection values are rejected (#177)** — an empty or whitespace-only `CUBRID_HOST`, `CUBRID_USER`, or `CUBRID_DATABASE` (and the `CUBRID_<NAME>_*` equivalents) now raises `ConfigError` at configuration time, like a missing variable, instead of producing a broken connection config. An empty `CUBRID_PASSWORD` remains allowed.
- **Port range validation (#176)** — `CUBRID_PORT` (and `CUBRID_<NAME>_PORT`) must now be an integer in the TCP port range `1..65535`; out-of-range values such as `0` or `65536` raise `ConfigError` at configuration time instead of failing later at connect time.
- **`db_serial` column probe is reset on reconnect (#181)** — the cached `att_name`/`attr_name` probe result used by `list_serials` is now cleared whenever the connection is discarded or closed, so a reconnect that lands on a different CUBRID version (e.g. 11.2 → 11.4 after a broker failover) re-probes instead of reusing the stale column name.
- **Cursor-creation failures take the normal recovery path (#180)** — `connection.cursor()` is now created inside the recovery block of both `Database.cursor()` and `execute_write()`, so a failure opening a cursor (e.g. on a connection the broker already closed) is surfaced as a sanitized `DatabaseError` (or `QueryTimeoutError`) and the unusable connection is discarded so the next call reconnects, instead of escaping raw and leaving the dead connection cached.
- **Composite primary key order (#186)** — `describe_table` and the `cubrid://schema/{table}` resource now return `primary_key` in declared key order (`db_index_key.key_order`) instead of table-column order, so it agrees with the primary-key entry in `indexes`. `schema_definitions` is unchanged (table-column order with per-column `primary_key` flags). Verified against live CUBRID 10.2 and 11.4.
- **Query timeout validation (#175)** — reject non-finite `CUBRID_MCP_QUERY_TIMEOUT` values such as `nan` and `inf` during configuration parsing instead of failing later in the socket layer.
- **table_row_counts: distinguish empty list from omitted input (#182)** — passing ``table_names=[]`` now returns an empty result instead of scanning all tables; omitting ``table_names`` (or passing ``None``) retains the default behavior of scanning all user tables.
- **create-release.yml: dropped `--target` from `gh release create`** — with an already-pushed tag (the normal tag-push trigger) `--verify-tag` already guarantees the tag exists, and passing `target_commitish` for an existing tag makes the Releases API return `422 Validation Failed`, so the first tag-triggered run of this workflow always failed. Verified live by the v0.4.0 tag attempt in cubrid-mcp-server.
- `list_serials` now works on **CUBRID 11.4**: the `db_serial` system catalog renamed its `att_name` column to `attr_name` in 11.4, so the hardcoded query failed there with a semantic error. The column is now resolved once per connection by a zero-row probe against a fixed allowlist and aliased back to `att_name`, keeping the tool's output shape identical on both versions. Found by the new 11.2+11.4 integration matrix.

### CI
- **FastMCP canary now reaches pytest (#185)** — `upstream-canary.yml` installed `"fastmcp@latest"`, which pip parses as a direct-URL requirement (`Invalid URL 'latest'`), so the job failed at install and its tests were always skipped. It now runs `pip install --upgrade --force-reinstall fastmcp`, prints the resolved version, then runs the unit tests. The lane explicitly tracks the latest **stable** release (no `--pre`); the stale `<4` pin comment is corrected to the actual `>=3.0,<5` range. The job stays advisory (`continue-on-error: true`).
- Integration tests now run against a CUBRID **11.2 + 11.4 job matrix** (previously 11.2 only), matching the pycubrid/sqlalchemy-cubrid integration matrices and the cookbook smoke matrix.
- Release workflow unified with pycubrid and sqlalchemy-cubrid: new `RELEASING.md`;
  `make release` replaced by the read-only `make release-check VERSION=x.y.z` (which also
  checks the `.mcpb/server.json` versions); `publish-pypi.yml` is manual-dispatch only,
  requires the GitHub Release + SBOM, and dispatches the cookbook smoke test after a
  successful publish (replacing `notify-cookbook.yml`).
- **PyPI publish fails closed on duplicate files (cubrid-lab/sqlalchemy-cubrid#566)** —
  `publish-pypi.yml` no longer passes `skip-existing: true`. The new stdlib-only `scripts/pypi_duplicate_guard.py`
  compares the SHA-256 of every verified file with the file PyPI already serves under the
  same name: an identical file (a partial upload recovered with `gh run rerun --failed`)
  is dropped from the upload, and a different hash or an unreachable PyPI fails the job.
  `RELEASING.md` documents the bounded recovery; offline tests cover the guard.
- **CI: releases happen automatically when a reviewed release PR is merged (#204)** —
  ported from cubrid-lab/pycubrid#540. `prepare-release.yml` opens the
  `chore: release vX.Y.Z` PR (moves `[Unreleased]` into a dated section, bumps
  `__version__` and both `.mcpb/server.json` versions, runs `make release-check`). On every
  push to `main`, the new `release.yml` decides from git facts only
  (`scripts/release_detect.py`: version changed against the first parent, dated CHANGELOG
  section, tag absent or at the same commit) and then runs, pinned to the merge SHA:
  release check, the full `integration-full.yml` matrix (now also a `workflow_call`
  workflow, no longer run on tag pushes), one build with SHA-256 hashes, the annotated
  tag, a draft GitHub Release with SBOM, the PyPI upload through the duplicate guard, and
  the cookbook verification of that exact version, with one run summary. The cookbook
  smoke test runs inside the release run as a reusable workflow pinned to a cookbook
  commit, so it needs no cross-repository token or secret; the release fails unless it
  reports the requested version installed (#206).
  `create-release.yml` and the manual `publish-pypi.yml` are removed; a narrow recovery
  dispatch (`resume`, `verify-only`, `dry-run`) remains. The CHANGELOG stays hand-curated.
  This supersedes the `create-release.yml` and `publish-pypi.yml` details in the entries
  above; the duplicate guard and the `.mcpb/server.json` check in `make release-check` stay.

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
