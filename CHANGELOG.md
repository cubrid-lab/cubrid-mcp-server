# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Upgrade notes
- **`table_row_counts` result shape (#239)** — clients that read the result as a list must read `result["tables"]` instead, and check `truncated` after a call without `table_names`.
- **`EXPLAIN` in `execute_query` (#250)** — it never ran on CUBRID; use the `explain_query` tool for execution plans.
- **`execute_query` with `CUBRID_MCP_READONLY=0` (#235)** — clients that sent `INSERT`/`UPDATE`/`DELETE` through `execute_query` with the whitelist disabled must use `execute_write` (enable it with `CUBRID_MCP_WRITE=1`, or `CUBRID_<NAME>_MCP_WRITE=1` per connection). Those statements, `COMMIT`/`ROLLBACK`, `PREPARE`/`EXECUTE`/`DEALLOCATE`, `DO` and multi-statement input now fail before execution.
- **Python 3.10 users** must either upgrade to Python 3.11 or later, or stay on the last cubrid-mcp-server release that supports 3.10 together with a driver release compatible with 3.10. Newer pycubrid lines (1.10+) do not support Python 3.10, and this project does not imply otherwise.

### Changed
- **`table_row_counts` caps the default call instead of failing beyond 50 tables (#239)** — behaviour change. With no `table_names` on a database with more than 50 user tables the tool raised `too many tables requested`, although its docstring promised a capped result and the `explore_unknown_db` prompt tells the model to call it. The default call now counts the first 50 user tables in name order. The result is now an object, `{"tables": [...], "truncated": bool, "total_tables": int}`, matching how `execute_query` signals truncation: `tables` holds the per-table entries the tool returned before, `truncated` is `true` when the default call left tables out, and `total_tables` is the number of user tables. An explicit list of more than 50 names still raises; `[]` still counts nothing. `TOOLS.md` (EN/KO) and the `explore_unknown_db` prompt describe the cap and how to fetch the rest.
- **`EXPLAIN` removed from `execute_query`'s read-only whitelist (#250)** — CUBRID has no `EXPLAIN` statement: on CUBRID 11.4.6, `EXPLAIN SELECT 1` (and `EXPLAIN PLAN FOR …`) fail at the server with a syntax error, so the whitelist admitted a statement that could never run. `READ_ONLY_KEYWORDS` is now `SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `WITH`, and with `CUBRID_MCP_READONLY=1` (the default) `EXPLAIN …` is rejected before it reaches the database with `UnsafeSQLError`; with `CUBRID_MCP_READONLY=0` it is not a rejected keyword and still fails at the server. README (EN/KO), `SECURITY.md`, the Security Model (EN/KO), Troubleshooting (EN/KO), the docs home page, ROADMAP and the `cubrid://agent-guide` resource no longer list it and point to the `explain_query` tool, which already uses CUBRID's `SET TRACE`/`SHOW TRACE`. A live integration test pins both the server rejection and the whitelist rejection. No other lexer change.
- **`execute_query` stays read-only when `CUBRID_MCP_READONLY=0` (#235)** — behaviour change. `CUBRID_MCP_READONLY=0` now only relaxes the read-only whitelist; it no longer lets `execute_query` run writes. With the whitelist off, `execute_query` rejects any statement that leads with a write, DDL or transaction-control keyword (`INSERT`, `UPDATE`, `DELETE`, `REPLACE`, `MERGE`, `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `RENAME`, `GRANT`, `REVOKE`, `COMMIT`, `ROLLBACK`, `SAVEPOINT`, `SET`, `PREPARE`, `EXECUTE`, `DEALLOCATE`, `DO`) before it reaches the database, with an `UnsafeSQLError` pointing to `execute_write`; the first word of the leading keyword is matched, so `CREATE OR REPLACE …` is rejected like `CREATE`. Multi-statement input (`multi-statement SQL is not allowed in execute_query`) and empty input — including comment-only or `;`-only input — are rejected too, as in read-only mode. The keyword check is a guardrail; the read-only database account remains the security boundary. Previously such a statement ran, was reported as `query failed: InterfaceError` and cost the shared connection. As a backstop, a statement that returns no result set (`cursor.description is None`) is rolled back and fails with `ValueError: statement produced no result set; execute_query is read-only, use execute_write …`, and the connection is kept instead of discarded. With `CUBRID_MCP_READONLY=1` (the default) the whitelist and its error messages are unchanged. Result-set reads (`SELECT`, `WITH … SELECT`, `SHOW`, `DESC`, and with the whitelist off also `CALL`s that return a value) are unaffected.
- **Python 3.11 is now the minimum supported version (#221)** — `requires-python` is `>=3.11` (Python 3.10 reached upstream end of life on 2026-10-01); the 3.10 classifier is removed, Ruff targets `py311` and mypy `3.11`. Python 3.14 is added to the classifiers and the unit/full-integration matrices after the offline suite, Ruff and mypy passed on 3.14. The `lowest-direct` job and Codecov upload moved to 3.11; lowest-direct resolves FastMCP 3.0.0, pycubrid 1.4.0 and sqlparse 0.5.0 and passes. No MCP, SQL-safety, timeout or audit behavior changes; direct dependency floors are unchanged.

### Fixed
- **`list_class_hierarchy` resolves table names like the other schema tools (#240)** — the tool bound the raw `table_name`, so matching was case-sensitive and an unknown name, system class or view silently returned `[]`. It now uses `_resolve_table`: names match user tables case-insensitively (and are bound as the stored name), and an unknown table raises `unknown table: '…'`; a whitespace-only name raises `table name must not be empty`. Omitting `table_name` (or passing `""`) still lists every class. The `TOOLS.md` signature (EN/KO) is corrected from `list_class_hierarchy(connection=None, ...)` to `list_class_hierarchy(table_name=None, connection=None)`.
- **Reads end their transaction on the shared connection (#234)** — the server never enables autocommit and pycubrid defaults to `autocommit=False`, so every `fetch_all`/`fetch_many` (all read tools, including `execute_query` and its truncated early return) left a transaction open until a later write committed, `explain_query` rolled back or the connection was dropped. That kept table locks (blocking DDL from other sessions) and, under `REPEATABLE READ`, a stale snapshot that hid rows committed by other sessions. Each read now rolls back once after its rows are collected, inside the connection lock; a failed rollback discards the connection so the next call reconnects. A failed read caused by a statement the server rejected (pycubrid `ProgrammingError`, `IntegrityError` or `DataError`) now rolls back and keeps the session instead of reconnecting; timeouts, `OperationalError`, `InterfaceError`, `InternalError`, the generic `DatabaseError` and non-driver errors still discard it. `execute_write` commit/rollback and `explain_query` trace cleanup are unchanged. With `CUBRID_MCP_READONLY=0`, a write that also returns a result set is now rolled back instead of left pending; use `execute_write` for writes.
- **Accept leading comments in `explain_query` (#178)** — SELECT/WITH statements now use the same comment normalization as the read-only safety checker before the leading-token gate.
- **Blank required connection values are rejected (#177)** — an empty or whitespace-only `CUBRID_HOST`, `CUBRID_USER`, or `CUBRID_DATABASE` (and the `CUBRID_<NAME>_*` equivalents) now raises `ConfigError` at configuration time, like a missing variable, instead of producing a broken connection config. An empty `CUBRID_PASSWORD` remains allowed.
- **Port range validation (#176)** — `CUBRID_PORT` (and `CUBRID_<NAME>_PORT`) must now be an integer in the TCP port range `1..65535`; out-of-range values such as `0` or `65536` raise `ConfigError` at configuration time instead of failing later at connect time.
- **`db_serial` column probe is reset on reconnect (#181)** — the cached `att_name`/`attr_name` probe result used by `list_serials` is now cleared whenever the connection is discarded or closed, so a reconnect that lands on a different CUBRID version (e.g. 11.2 → 11.4 after a broker failover) re-probes instead of reusing the stale column name.
- **Cursor-creation failures take the normal recovery path (#180)** — `connection.cursor()` is now created inside the recovery block of both `Database.cursor()` and `execute_write()`, so a failure opening a cursor (e.g. on a connection the broker already closed) is surfaced as a sanitized `DatabaseError` (or `QueryTimeoutError`) and the unusable connection is discarded so the next call reconnects, instead of escaping raw and leaving the dead connection cached.
- **Composite primary key order (#186)** — `describe_table` and the `cubrid://schema/{table}` resource now return `primary_key` in declared key order (`db_index_key.key_order`) instead of table-column order, so it agrees with the primary-key entry in `indexes`. `schema_definitions` is unchanged (table-column order with per-column `primary_key` flags). Verified against live CUBRID 10.2 and 11.4.
- **Query timeout validation (#175)** — reject non-finite `CUBRID_MCP_QUERY_TIMEOUT` values such as `nan` and `inf` during configuration parsing instead of failing later in the socket layer.
- **table_row_counts: distinguish empty list from omitted input (#182)** — passing ``table_names=[]`` now returns an empty result instead of scanning all tables; omitting ``table_names`` (or passing ``None``) retains the default behavior of scanning all user tables.
- **create-release.yml: dropped `--target` from `gh release create`** — with an already-pushed tag (the normal tag-push trigger) `--verify-tag` already guarantees the tag exists, and passing `target_commitish` for an existing tag makes the Releases API return `422 Validation Failed`, so the first tag-triggered run of this workflow always failed. Verified live by the v0.4.0 tag attempt in cubrid-mcp-server.

### Security
- **Every user-supplied prompt argument is fenced as untrusted data (#238)** — `optimize_query` and `migrate_from_mysql` wrapped their `sql` argument in a fixed ```` ```sql ```` fence that the input could close, and `safe_data_analysis` (`question`) and `write_cubrid_sql` (`natural_language`) inserted their argument unfenced, contrary to the README's statement that prompt arguments are fenced. All four now go through `_as_untrusted`, the same labeled block the other prompts use, whose fence grows longer than any backtick run in the value. A protocol-level test discovers every registered prompt that takes arguments and fails if any argument is not inside such a block, including adversarial input with closing fences and backticks. Prompt wording is otherwise unchanged; no tool, SQL-safety or audit change.
- **Connection errors no longer reveal host or database (#236)** — `Database.connect()` now raises the fixed `failed to connect to CUBRID` (previously it included `host=` and `database=`), and `health_check` returns only the exception class name instead of `str(exc)`. `exclusive()` (used by `explain_query`) now raises a sanitized `DatabaseError` for non-timeout driver errors instead of re-raising the raw driver exception, which could carry SQL or host text. Host, port, database and the driver cause are written to the stderr log with `exc_info` for operators. Operators who matched on the old message or the raw `health_check` text must read the server log instead. No tool signature, SQL-safety, timeout or audit change.

### Documentation
- **Security model wording, DDL rationale and `explain_query` semantics (#237)** — `SECURITY_MODEL.md`, `SECURITY.md`, README and their Korean pages now state that the SQL keyword checks are a guardrail and defense-in-depth, not a security boundary: the primary control is a dedicated least-privilege database account (`SELECT` only on the tables the model needs; do not reuse `dba` or the owner account; keep the account to the minimum privileges required, with no DDL rights). Absolute claims the code does not guarantee were removed. The DDL exclusion no longer says CUBRID auto-commits DDL: the server runs pycubrid with autocommit off, and on CUBRID 10.2, 11.2 and 11.4 DDL is rolled back if not committed, so DDL is excluded because `execute_write` is a DML tool and `execute_query` is read-only. `explain_query` is documented (docs and tool docstring) as executing the statement under `SET TRACE ON` and rolling back as best-effort cleanup. The agent guide, `safety.py` comment and tool docstring no longer claim DDL auto-commits, and the Korean `TOOLS.md` prompt table now lists all nine prompts.
- **README, TOOLS, `llms.txt` and the registry manifest aligned with the server (#242)** — README lists all 9 prompts; the resource tables give the MIME type of each resource (`text/markdown` for the guides, `application/json` for schema resources); `llms.txt` now covers `health_check`, `execute_write`, resources and prompts; `.mcpb/server.json` marks `CUBRID_HOST`/`USER`/`PASSWORD`/`DATABASE` required as `config.py` does, lists the `CUBRID_MCP_*` settings and `CUBRID_CONNECTIONS`, and describes 11 read-only tools plus the opt-in `execute_write`; `MULTI_CONNECTION.md` documents that schema resources always use the `default` connection. A new test compares the registered tool, prompt and resource names with `TOOLS.md`.
- **CHANGELOG cleaned up before the next release (#241)** — entries that shipped in the `v0.4.0` tag (the `list_serials` CUBRID 11.4 fix, the 11.2 + 11.4 integration matrix, #150) moved from `[Unreleased]` into `[0.4.0]`, duplicate `### CI` and `### Documentation` headings in `[Unreleased]` were merged, a stale test count was dropped, and the `prepare-release.yml` header comment no longer claims to be identical to the sibling repositories. `[0.2.0]` carries a note that no `v0.2.0` tag exists (no tag was created or moved).
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

### CI
- **GitHub Release naming and standard release-note sections** — ported from cubrid-lab/pycubrid#792 and cubrid-lab/sqlalchemy-cubrid#772. `AGENTS.md` gains a "GitHub Release Policy" section: a Release title is exactly its `vX.Y.Z` tag (drafts included), tags are never moved or recreated to fix a title, `tag_name` is resent on draft edits, stale drafts are classified against tag and PyPI history and changed only with maintainer approval, and release notes come from the CHANGELOG with standard `###` sections. `release.yml` keeps creating Releases with `--title "$TAG"` and, on resume or recovery, fails closed through the new `scripts/check_release_title.py` when an existing draft or published Release has another title; it never renames one. `scripts/extract_release_notes.py` appends exactly one `**Full Changelog**` compare link to the unchanged CHANGELOG section (none for the first release or when the section already has a compare link). `scripts/lint_changelog.py` requires the standard headings (Upgrade notes, Added, Changed, Deprecated, Removed, Fixed, Security, Performance, Documentation, CI, Tests), once each, in that order and with content, for `[Unreleased]` and releases after 0.4.0 (`SECTION_POLICY_CUTOFF`); 0.4.0 and older keep their historical headings, and the duplicate-heading check of #241 still applies to every version. The `[Unreleased]` sections were reordered to the standard order; no entry changed. No runtime change.
- **Cookbook release verification pinned to the shared cookbook SHA** — the `verify-cookbook` call to `cubrid-cookbook-python`'s `smoke-test.yml` in `.github/workflows/release.yml` is pinned to `bd6749093813d3a447f993fec72ac733adbeae63`, the same commit as the other two package repositories (pycubrid, sqlalchemy-cubrid, cubrid-mcp-server). Since the previous pin the cookbook adds the Python 3.11 cell on release calls (`Smoke Tests (CUBRID 11.4, Python 3.11)`), so the release verification report now needs all three cells (11.2/3.12, 11.4/3.12, 11.4/3.11). `RELEASING.md` lists the third job. No runtime change.
- **`scripts/lint_changelog.py` rejects duplicate subsection headings (#241)** — a `###` heading repeated within one version section (for example two `### CI` blocks) now fails the changelog lint.
- **CI/CodeQL concurrency, grouped Dependabot updates and pinned docs tools (#243, #244, #245)** — `ci.yml` and `codeql.yml` now cancel a superseded `pull_request` run when a newer commit is pushed; `main`, release and scheduled runs use a unique group per run and are never cancelled or replaced while queued. The fail-closed `ci-gate` is unchanged (a cancelled lane still fails it). Dependabot groups dev tools (`pytest*`, `pre-commit`, `tox`, `build`, `twine`) and GitHub Actions into one minor/patch PR each, with the exact-pinned `ruff` and `mypy` in their own groups, keeping major updates and the runtime dependencies `fastmcp`, `pycubrid` and `sqlparse` separate. `docs.yml` installs `mkdocs`, `mkdocs-material` and `pymdown-extensions` from the pinned `docs-tools/requirements.txt` instead of unpinned, and Dependabot updates those pins; `docs.yml` now also builds with `mkdocs build --strict` on pull requests touching docs inputs (no deploy, read-only permissions; Pages/OIDC permissions moved to the deploy job). `tests/test_ci_policy.py` asserts all three. No runtime change.
- **Tiered PR, main and compatibility validation (#223)** — a `classify` job (`scripts/ci_scope.py`) maps the event and changed paths to explicit scopes, and only the selected lanes run. Docs/metadata-only PRs start no unit job and no CUBRID container; ordinary runtime/test PRs run one Python 3.12 unit lane and one CUBRID 11.4 live lane; connection/catalog changes add CUBRID 11.2; workflow and dependency-metadata changes run the Python 3.11/3.12/3.14 and CUBRID 11.2/11.4 endpoints (plus `lowest-direct` for `pyproject.toml`); pushes to `main` and CI-policy changes run all of those. Codecov uploads from 3.12. The required `ci-gate` now fails on a failed classification and on any failed, cancelled or unexpectedly skipped lane — a lane may be skipped only when the classification says it does not apply (previously a failed path filter silently skipped integration). `integration-full.yml` no longer runs the 16-cell Python × CUBRID matrix daily: it runs in full weekly (Sunday) and on dispatch, runs only the oldest/newest corners (3.11 × 10.2, 3.14 × 11.4) Monday–Saturday, and still runs in full, fail-closed, as the release gate. Measured on recent runs: docs-only PR 8 → 3 jobs, ordinary runtime PR 10 → 5 jobs (2 → 1 CUBRID), scheduled matrix ≈133 → ≈44 billed runner-minutes per week. No runtime, SQL-safety, write-mode, audit or release-flow change.
- **FastMCP canary now reaches pytest (#185)** — `upstream-canary.yml` installed `"fastmcp@latest"`, which pip parses as a direct-URL requirement (`Invalid URL 'latest'`), so the job failed at install and its tests were always skipped. It now runs `pip install --upgrade --force-reinstall fastmcp`, prints the resolved version, then runs the unit tests. The lane explicitly tracks the latest **stable** release (no `--pre`); the stale `<4` pin comment is corrected to the actual `>=3.0,<5` range. The job stays advisory (`continue-on-error: true`).
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

### Tests
- **Live shared-session concurrency regression (#211)** — two simultaneous in-process tool calls now verify that `execute_query` waits while `explain_query` owns the real `SET TRACE` context on the cached Database connection. The test checks distinct responses, connection reuse and closure of every real cursor, including trace cleanup. It exercises the existing serialized RLock model, not MCP stdio concurrency, a connection pool or per-request transaction isolation. No runtime change.

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
- `list_serials` now works on **CUBRID 11.4**: the `db_serial` system catalog renamed its `att_name` column to `attr_name` in 11.4, so the hardcoded query failed there with a semantic error. The column is now resolved once per connection by a zero-row probe against a fixed allowlist and aliased back to `att_name`, keeping the tool's output shape identical on both versions. Found by the new 11.2+11.4 integration matrix.

### CI
- Integration tests now run against a CUBRID **11.2 + 11.4 job matrix** (previously 11.2 only), matching the pycubrid/sqlalchemy-cubrid integration matrices and the cookbook smoke matrix.

### Documentation
- **CUBRID server license relationship documented; copyright and authors unified (#150)** — `THIRD_PARTY_LICENSES.md` carries the verified upstream licensing statement (server engine Apache-2.0, APIs/connectors BSD per CUBRID's `COPYING` — the often-cited GPL v2+ no longer applies; independent wire-protocol client, Docker image CI-only). LICENSE/NOTICE copyright lines now read `Yeongseon Choe, Gyeongjun Paik` (2025-2026), and `pyproject.toml` lists both primary authors.

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

> Note: there is no `v0.2.0` git tag for this release; the published history is `v0.1.0`, `v0.2.1`, `v0.3.0`, `v0.3.1`, `v0.4.0`. The tag was not created retroactively.

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
