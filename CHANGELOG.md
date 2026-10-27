# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.0] - 2026-10-27

### Added

- **Configurable connect timeout and server output limits (#430)** — three values that were
  hardcoded can now be set per deployment: `CUBRID_MCP_CONNECT_TIMEOUT` (seconds for opening
  a broker connection, positive finite number, default `10`),
  `CUBRID_MCP_MAX_ROW_COUNT_TABLES` (tables `table_row_counts` counts in one call, positive
  integer, default `50`) and `CUBRID_MCP_MAX_INLINE_BINARY_BYTES` (largest binary value
  returned inline as base64, non-negative integer, default `256`; `0` summarizes every
  non-empty binary value). Each also has a per-connection `CUBRID_<NAME>_MCP_*` form and an
  invalid value fails at startup with an error naming the variable. Without them the
  behavior is unchanged. README (EN/KO), `TOOLS.md`, `MULTI_CONNECTION.md` and
  `TROUBLESHOOTING.md` (EN/KO) and the `.mcpb/server.json` manifest list them.

* **config:** make the connect timeout and server output limits configurable ([#454](https://github.com/cubrid-lab/cubrid-mcp-server/issues/454)) ([f65e548](https://github.com/cubrid-lab/cubrid-mcp-server/commit/f65e548348100494510838ec731ed474a889a159))

### Documentation

- **README and docs site show the brand icon with white marks (#472)** — the icon URL pinned in the README, its translations and `mkdocs.yml` (logo and favicon) now points at brand revision `3a385be`, where the Python Yellow icons draw white role marks on a bare cube like every other language. Documentation only; behavior is unchanged.
- **README and docs site show the emblem-aligned brand icon (#469)** — the icon URL pinned in the README, its translations and `mkdocs.yml` (logo and favicon) now points at the brand revision `538bad3`, whose Python Yellow keyline keeps the cube silhouette of the organization emblem (open seams, no flat bottom). Documentation only; behavior is unchanged.
- **README and docs site show the 2026-10-25 brand icon (#456)** — the icon URL pinned in the README, its translations and `mkdocs.yml` (logo and favicon) now points at the approved CUBRID Lab brand revision `8aa81b7`. Documentation only; behavior is unchanged.

* adopt type-only issue titles and shared triage guidance ([31cc0b0](https://github.com/cubrid-lab/cubrid-mcp-server/commit/31cc0b0fa536cce00845d6192e77ffd6823fea8e))
* **readme:** repin the brand icon to the 2026-10-25 brand revision ([#457](https://github.com/cubrid-lab/cubrid-mcp-server/issues/457)) ([d35e4a5](https://github.com/cubrid-lab/cubrid-mcp-server/commit/d35e4a51bffa97bd4e51cba9f891d1578a8bf520))
* **readme:** repin the brand icon to the emblem-aligned keyline ([#470](https://github.com/cubrid-lab/cubrid-mcp-server/issues/470)) ([c80a8c0](https://github.com/cubrid-lab/cubrid-mcp-server/commit/c80a8c0b5a10a6f0fada88b857890d15c087109c))
* **readme:** repin the brand icon to the shared white marks ([#473](https://github.com/cubrid-lab/cubrid-mcp-server/issues/473)) ([6eaba76](https://github.com/cubrid-lab/cubrid-mcp-server/commit/6eaba766ffdb0e1f42c7e5e8dfade1d81d281f68))

### CI

- **Fewer routine CUBRID version runs, full release coverage kept (#417)** — a push to
  `main` now runs live integration on CUBRID 11.4 only (it also ran 11.2); its Python
  3.11/3.12/3.14 unit lanes and `lowest-direct` are unchanged. `integration-full.yml`
  drops its Monday–Saturday two-corner schedule and keeps the weekly Sunday 4 × 4
  matrix; manual dispatch and the release `workflow_call` from `publish-pypi.yml` still
  run all 16 cells and gate publication as before. PR selection is unchanged. Each
  matrix cell now records the image digest and engine version it ran, and a new
  advisory weekly job (`scripts/latest_server.py`) checks whether `cubrid/cubrid:latest`
  is the same image as `11.4`, runs a focused canary only on a newer engine build, and
  reports a failed lookup as unverified. No supported CUBRID version changes.

### Tests

- **Live proof that the default configuration refuses writes (#451)** — the new
  `integration`-marked `tests/test_integration_readonly.py` calls every SQL-accepting tool
  through `mcp.call_tool` against the run-owned CUBRID, with no `CUBRID_MCP_READONLY`,
  `CUBRID_MCP_WRITE` or `CUBRID_CONNECTIONS` set. `CREATE TABLE`, `INSERT`, `UPDATE`,
  `DELETE`, `TRUNCATE`, `ALTER`, `DROP` (also behind a comment) and `SELECT 1; DROP ...`-style
  multi-statement input fail with the documented `execute_query` and `explain_query` errors,
  `execute_write` is not offered, and a table name carrying SQL is an unknown table for
  `table_row_counts`; an independent session then shows the catalog, columns and rows
  unchanged. One more test enables `CUBRID_MCP_WRITE=1`, commits an `INSERT` through
  `execute_write` into a uniquely named table that it always drops, and shows DDL and
  multi-statement input are still refused. Test-only; the server is unchanged.

## [0.6.0] - 2026-10-25

### Upgrade notes

- **`make verify` now runs the live integration lane (#404)** — it runs `make check`, the offline
  `make test` and then the run-owned `make integration` lane, so it needs Docker and fails when
  CUBRID never becomes ready or every live test skips. The live lane starts only after the offline
  tests pass, also under `make -j`. `make test` stays offline; run `make check test` for the
  former offline-only `make verify`. Development tooling only; the MCP tools are unchanged.

### Added

- **`make verify` writes an aggregate summary (#449)** — `scripts/run_verify.py` now runs the
  three phases and always writes `test-results/verify/summary.json` (overall `PASS`/`FAIL`/
  `INCOMPLETE` and each phase's status, `NOT_RUN` when it never started, and exit code), copies of
  the lanes' JUnit files under `junit/<lane>.xml` and the live `environment.json`, with the
  configured connection passwords masked, also after a failure or a signal. A missing, unreadable
  or non-string lane status, an all-skipped live lane or a file that cannot be copied is never
  `PASS`. The first SIGINT, SIGTERM or SIGHUP is forwarded to the running phase and the run exits
  128 + the signal number; `make integration` now `exec`s its runner, so a SIGTERM to make reaches
  it, and the runner also cleans up on SIGHUP. New `scripts/report_results.py aggregate`
  subcommand. Development tooling only; the MCP tools are unchanged.

* **make:** run the live integration lane in make verify ([#447](https://github.com/cubrid-lab/cubrid-mcp-server/issues/447)) ([e694f56](https://github.com/cubrid-lab/cubrid-mcp-server/commit/e694f569cbbe62034a275a846b90bd8ed7e827f1))
* **make:** write an aggregate verification summary under test-results/verify ([#450](https://github.com/cubrid-lab/cubrid-mcp-server/issues/450)) ([3260e38](https://github.com/cubrid-lab/cubrid-mcp-server/commit/3260e3810ec8ed1a285f3f84731ac96271ca9892)), refs [#449](https://github.com/cubrid-lab/cubrid-mcp-server/issues/449)

### CI

- **Every new issue starts in `status: needs triage` (#418)** — the issue forms add the
  label and the new `issue-triage.yml` workflow adds it to every opened issue. Priority and
  size are still set by a maintainer, who removes the label after triage.

### Tests

- **Named-connection invalid values keep the prefixed variable name (#434)** — `tests/test_config.py` now checks that an invalid `PORT`, `MCP_MAX_ROWS`, `MCP_MAX_CHARS`, `MCP_MAX_SQL_LENGTH` or `MCP_QUERY_TIMEOUT` on a named connection raises `ConfigError` naming the full `CUBRID_<NAME>_...` variable and not the bare default one, and that a blank required named variable is reported like a missing one. Test-only; `config.py` is unchanged. Refs #434.

## [0.5.6] - 2026-10-25

### Changed

- **Invalid boolean settings name their variable (#435)** — `CUBRID_MCP_READONLY`, `CUBRID_MCP_WRITE` and `CUBRID_MCP_AUDIT_LOG` (and the `CUBRID_<NAME>_` forms for named connections) reported only `expected a boolean-like value, got 'x'`, so with several connections the operator had to guess which variable was wrong. The error now reads `<VARIABLE> must be a boolean (1/true/yes/on or 0/false/no/off), got 'x'`, matching the integer settings. Accepted aliases are unchanged, and `_parse_bool(value)` without a key keeps its old message. Refs #435.

### Fixed

* **config:** name the variable when a boolean setting is invalid ([#443](https://github.com/cubrid-lab/cubrid-mcp-server/issues/443)) ([8fc77db](https://github.com/cubrid-lab/cubrid-mcp-server/commit/8fc77db9e5379706dae95b1e85894be677f92df7)), refs [#435](https://github.com/cubrid-lab/cubrid-mcp-server/issues/435)

### Documentation

* **agents:** align independent MCP safety review and local title rules ([7592c53](https://github.com/cubrid-lab/cubrid-mcp-server/commit/7592c534b089882077f2b5da8345659aeb041d5c))
* **agents:** clarify MCP safety review and local PR policy ([#442](https://github.com/cubrid-lab/cubrid-mcp-server/issues/442)) ([7592c53](https://github.com/cubrid-lab/cubrid-mcp-server/commit/7592c534b089882077f2b5da8345659aeb041d5c))

## [0.5.5] - 2026-10-25

### Fixed

- **Audit logger invariants raise `RuntimeError` instead of asserting (#429)** — `AppContext.audit_for()` and `server._audit()` guarded the audit logger that `AppContext.__post_init__` always sets with `assert`, which `python -O` strips. Both now raise `RuntimeError` naming the missing field; behavior is unchanged while the invariant holds, so no tool output changes. Refs #429.

- **Suppressed connection close failures are logged (#431)** — `AppContext.close()` re-raises only the first close failure and silently dropped any later one, hiding secondary shutdown problems. Each suppressed failure is now logged at WARNING through the module logger with the connection name and the exception type only (driver error text can echo connection details, so it is deliberately left out). The first error is still raised unchanged. Refs #431.

* **context:** log suppressed connection close failures ([#439](https://github.com/cubrid-lab/cubrid-mcp-server/issues/439)) ([9924e2c](https://github.com/cubrid-lab/cubrid-mcp-server/commit/9924e2c94454eb0abda19776e23135d12acca381))
* **context:** raise RuntimeError for unset audit loggers instead of asserting ([#438](https://github.com/cubrid-lab/cubrid-mcp-server/issues/438)) ([b6d8bb0](https://github.com/cubrid-lab/cubrid-mcp-server/commit/b6d8bb0e79022dc7a0df7282c87fae8784fdcf69))
* **reporting:** redact credentials embedded in environment command metadata ([#433](https://github.com/cubrid-lab/cubrid-mcp-server/issues/433)) ([702aac6](https://github.com/cubrid-lab/cubrid-mcp-server/commit/702aac6f4b4c43a5b2abdaa36a4adfe645c0830a))

### Security

- **`environment.json` masks credentials embedded in the recorded command (#426)** — `scripts/report_results.py` stored the `--command` string, which `make integration` builds from its overridable `--pytest` value, verbatim, so a password assignment, an authenticated database URL or a token option in it would have reached the `test-results/integration/environment.json` CI artifact. It now masks the password of URL userinfo (`scheme://user:***@host`, percent-encoded passwords included) and the value of a `password`, `passwd`, `pwd`, `token`, `secret`, `api_key` or `apikey` assignment or option, case-insensitively and as a key suffix (`PASSWORD=***`, `CUBRID_PASSWORD=***`, `--password=***`, `--password ***`), and keeps every other byte of the command. The schema, statuses, exit codes and the arguments pytest receives are unchanged. The masking is a best-effort safety net with documented limits (for example `-p secret` is not recognized); `CONTRIBUTING.md` and the module docstring now say to supply secrets through environment variables or the CI secret store, not the command line. Refs #426.

### Documentation

- **The table-resolution and schema helpers in `server.py` are documented (#432)** — `_schema_definitions` and `_list_indexes` were the last of the private helpers behind the schema tools without a docstring; each now states what it returns and how the table is selected by owner and name. Docstrings only: no behavior, signature or tool output changes. Refs #432.

* **server:** document the table-resolution and schema helper functions ([#440](https://github.com/cubrid-lab/cubrid-mcp-server/issues/440)) ([c645e6c](https://github.com/cubrid-lab/cubrid-mcp-server/commit/c645e6c6b272a8dadfa1f1113c07b9f7571422c5)), refs [#432](https://github.com/cubrid-lab/cubrid-mcp-server/issues/432)

### CI

- **The temporary `last-release-sha` override is removed after 0.5.4 (#388)** — `v0.5.4` is published, and the release run verified it against the cookbook, so the next candidate starts from that tag. The override for the abandoned 0.5.3 (`8633db6`) is no longer needed, and leaving it in place would make a later recovery start from a stale base (RELEASING.md, "A merged X.Y.Z is abandoned"). Refs #388.

## [0.5.4] - 2026-10-24

### Upgrade notes

- **0.5.3 was never published (#388).** Its cookbook candidate verification failed: the pinned cookbook commit predated the cookbook's pandas 3.1 golden fix (cubrid-lab/cubrid-cookbook-python#444), so no 0.5.3 tag, GitHub Release or PyPI version exists. 0.5.4 contains every 0.5.3 change below; upgrade from 0.5.2 directly to 0.5.4.

- **`make integration` needs Docker Compose and reads `CUBRID_TEST_PORT` (#402)** — it now runs `docker compose ... up --detach --wait`, so it needs the Docker Compose plugin (v2 or later) as well as Docker. Its port is `CUBRID_TEST_PORT` (default 33000), the variable `make docker-up` already uses, so a `CUBRID_TEST_PORT` exported for a running lab also moves `make integration` onto that port (pass another one). `INTEGRATION_PORT` still works and wins when set. Refs #402.

- **The `dev` extra is now the `dev` dependency group (#398)** — `pip install -e ".[dev]"` no longer installs the contributor tools, and the published wheel and sdist no longer carry a `dev` extra (their runtime dependencies are unchanged). Install them with `make install` or `python -m pip install -e . --group dev`, which needs pip 25.1 or later (`python -m pip install --upgrade pip`). Refs #398.

- **`make integration` now starts its own CUBRID (#379)** — it used to run `pytest -m integration` against a CUBRID you had already started. It now starts a uniquely named `cubrid/cubrid:$(CUBRID_VERSION)` container (default 11.4) with `demodb`, publishes the broker on host port `$(INTEGRATION_PORT)` (default 33000), waits for `demodb`, runs the integration tests against `127.0.0.1:$(INTEGRATION_PORT)/demodb` as `dba` (exported `CUBRID_*` connection variables are ignored), and always removes that container, so it needs Docker. The old behavior is `make integration-local`. `make test` now also measures coverage and fails below `fail_under = 95` and writes `coverage.xml`, `make lint` checks the whole repository (`ruff check .`) instead of `cubrid_mcp_server/` and `tests/`, and `make check` adds `format-check`, so all three can fail where they passed before.

### Added

- **A persistent local CUBRID with Docker Compose (#378)** — a root `docker-compose.yml` defines one service, `cubrid` (`cubrid/cubrid:${CUBRID_VERSION:-11.4}`, `demodb`, `CUBRID_DB_HOST=localhost`, the broker on `127.0.0.1:${CUBRID_TEST_PORT:-33000}` only, a `csql ... SELECT 1` health check, a named data volume, no fixed container name), and new Make targets drive it for manual work: `make docker-up` starts it and waits until it is healthy, `make docker-down` removes the container and network but keeps the data volume, and `make docker-clean` also deletes the volume. `make integration`, `make verify` and the CI live jobs are unchanged: the live lane still starts and always removes its own run-owned container. `CONTRIBUTING.md`, `AGENTS.md` and the README development section (English and Korean) document the targets and how to point `make integration-local` at the service. Refs #378.

- **`make test` and `make integration` write `test-results/` summaries (#405)** — both targets now write a gitignored `test-results/` tree: `make test` writes `test-results/test/junit.xml`, `coverage.xml` and `summary.json` (the root `coverage.xml` that CI uploads to Codecov is still written, as a copy), and `make integration` writes `test-results/integration/junit.xml`, `summary.json`, `environment.json` (Python, package and CUBRID versions, platform and command; never credentials) and, on a failure, `logs/cubrid.log`. The new `scripts/report_results.py` builds `summary.json` (`schema_version`, `status` of `PASS`, `FAIL` or `INCOMPLETE`, counts, coverage) from the JUnit and coverage files, and each command ends with a one-line console summary of the same status and counts. A lane that collected nothing, or in which no test passed, is `INCOMPLETE`, never `PASS`. Exit statuses, test selection and the coverage floor are unchanged, and `make clean` removes `test-results/`. Refs #405.

### Changed

- **`make integration` runs the `docker-compose.yml` service as a run-owned Compose project (#402)** — `scripts/run_integration.py` no longer starts its own `docker run` container: it runs `docker compose --file docker-compose.yml --project-name cubrid-mcp-it-<random id> up --detach --wait cubrid` with `CUBRID_VERSION` and `CUBRID_TEST_PORT` set, so `make integration` and `make docker-up` share one service definition (image tag, `demodb`, health check, shared-memory size, loopback-only broker). Readiness is the service's `csql ... SELECT 1` health check instead of a separate `docker exec` probe loop; on a failure it prints `docker compose logs cubrid`; and it always runs `down --volumes` on that project, which removes its container, network and named volumes, on success, failure, a readiness failure, SIGINT or SIGTERM (the cleanup runs in its own session, so a second Ctrl-C cannot stop it). The exit-status rules are unchanged. The project name is unique per run, so concurrent runs on different ports, and a `make docker-up` lab, are never touched. `CUBRID_TEST_PORT` is now the one port variable of both lanes, with `INTEGRATION_PORT` kept as a compatibility override. The offline tests use a fake `docker compose`; `CONTRIBUTING.md`, `AGENTS.md`, the README development section (English and Korean) and the `docker-compose.yml` comments describe it. Refs #402.

- **Contributor tools are a PEP 735 `dev` dependency group; the Makefile runs them through one interpreter (#398)** — the pins that were in `[project.optional-dependencies].dev` (including `ruff==0.17.1` and `mypy==2.4.0`) now live unchanged in `[dependency-groups].dev`; there is no lock file and no other group. `make install` runs `$(PYTHON) -m pip install -e . --group dev`, and `pytest`, `ruff` and `mypy` run as `$(PYTHON) -m ...` instead of bare executables, so an activated virtualenv is honored even when `PATH` lists another one. `PYTHON ?= python3`, `PYTEST`, `RUFF` and `MYPY` are all overridable (`make lint PYTHON=.venv/bin/python`, `make lint RUFF=ruff`); the commands, flags, coverage floor and Docker lifecycle of `check`, `test`, `verify` and `integration` are unchanged. Refs #398.

- **The Makefile is the canonical local and CI interface (#379)** — new targets: `doctor` (checks Python 3.11+, `ruff`, `mypy`, `pytest`, `pytest-cov` and `pytest-asyncio`; exits non-zero without a success line if any is missing), `format-check` (`ruff format --check .`), `verify` (`check` + `test`, no Docker), `integration` (the run-owned Docker lifecycle in `scripts/run_integration.py`: start, readiness wait, `pytest -m integration -v`, the container log on a failure, removal of the container and its anonymous volumes on success, failure, SIGINT or SIGTERM; the first failing step's exit status, or 128 + the signal number) and `integration-local`. `lint`, `format-check` and `typecheck` use the same paths and flags as CI, `format` is the only target that edits files, `test` takes extra pytest arguments in `PYTEST_ARGS`, `clean` also removes `.ruff_cache`, `.coverage`, `coverage.xml` and `htmlcov` (all gitignored, generated files), and `make help` groups the targets by purpose. Refs #379.

* remove the App-owned agent-review publisher ([#397](https://github.com/cubrid-lab/cubrid-mcp-server/issues/397)) ([e5bf28e](https://github.com/cubrid-lab/cubrid-mcp-server/commit/e5bf28e006f8c005c7d9334ed87ee3531bf61eb2))

### Fixed

- **A failed service-log save no longer skips `make integration` cleanup** — with `--results-dir`, an I/O error while writing `logs/cubrid.log` after a failing lane used to escape before `docker compose down --volumes`, leaving the run-owned project behind and losing the lane's exit status. Saving the log is now best-effort: the error is printed as a warning, the project is still taken down and the summary keeps the lane's status.

* **test:** never let a failed service-log save skip make integration cleanup ([#416](https://github.com/cubrid-lab/cubrid-mcp-server/issues/416)) ([dec3942](https://github.com/cubrid-lab/cubrid-mcp-server/commit/dec39420852edc175e36f5d9afa5953685c7c937))

### Documentation

- **Install instructions use the `dev` group (#398)** — `CONTRIBUTING.md`, the README (English and Korean), `scripts/doctor.py` and `THIRD_PARTY_LICENSES.md` replace `.[dev]` with `--group dev`, document the pip 25.1 requirement and the Makefile overrides, and explain that the dev table's `cubrid-mcp-server` attribution is hand-kept because installed metadata does not record group membership. Refs #398.

- **Make targets in the contributor docs (#379)** — `CONTRIBUTING.md`, `AGENTS.md`, the PR template and the README development section (English and Korean) describe the new targets, the `make integration` variables and that CI calls the same targets. Refs #379.

* **agents:** require repository-local issue authoring checks ([#383](https://github.com/cubrid-lab/cubrid-mcp-server/issues/383)) ([4f04af7](https://github.com/cubrid-lab/cubrid-mcp-server/commit/4f04af7b503cae0e2fcc97b79326a629d9e68aea))
* enforce repository-local issue drafting ([4f04af7](https://github.com/cubrid-lab/cubrid-mcp-server/commit/4f04af7b503cae0e2fcc97b79326a629d9e68aea))
* **ko:** replace the mistranslated redaction term in the Korean docs ([#389](https://github.com/cubrid-lab/cubrid-mcp-server/issues/389)) ([2621d8b](https://github.com/cubrid-lab/cubrid-mcp-server/commit/2621d8b415a1dcf7ea8a34fab758126bb6b5f216)), refs [#290](https://github.com/cubrid-lab/cubrid-mcp-server/issues/290)
* **triage:** clarify PR overlap and execution precedence ([440166a](https://github.com/cubrid-lab/cubrid-mcp-server/commit/440166adcf3b8a1e51cda51353a2c4f762adec40)), refs [#410](https://github.com/cubrid-lab/cubrid-mcp-server/issues/410)

### CI

- **The release workflow verifies against the current cookbook, and preparation restarts after the abandoned 0.5.3 (#388)** — 0.5.3 was not published: its cookbook candidate verification failed at the pinned cookbook commit `0d8b5bb`, which predates the cookbook's pandas 3.1 golden fix (cubrid-lab/cubrid-cookbook-python#444), so nothing was tagged, released or uploaded. Both `smoke-test.yml@` pins in `publish-pypi.yml` (`verify-candidate` and `verify-cookbook`) move to cookbook `main` `fbaaa8c`; the called workflow's inputs and outputs are unchanged. The top-level `last-release-sha` in `release-please-config.json` is set to the 0.5.3 merge `8633db6` so the next candidate starts after it (RELEASING.md, "A merged X.Y.Z is abandoned"); remove it after the next release is tagged. Refs #388.

* **release:** verify against the current cookbook and restart after the abandoned 0.5.3 ([#424](https://github.com/cubrid-lab/cubrid-mcp-server/issues/424)) ([1d1e5a1](https://github.com/cubrid-lab/cubrid-mcp-server/commit/1d1e5a18f1496a9b4a5c6f5794bd488edbf020cd)), refs [#388](https://github.com/cubrid-lab/cubrid-mcp-server/issues/388)

- **CI publishes and uploads the test results (#405)** — the `lint-and-test` job and both `integration` jobs (`ci.yml`, `integration-full.yml`) now append the one-line `test-results/*/summary.json` summary to the run's job summary (`scripts/report_results.py step-summary`) and upload `test-results/` with `actions/upload-artifact` (the commit already pinned in `publish-pypi.yml`, v7) on every run, pass or fail, as one `test-results-...` artifact per matrix entry kept for 7 days. No permissions, secrets or triggers change, and the Codecov upload is unchanged. Closes #405.

- **CI installs the `dev` group (#398)** — the `lint-and-test`, `lowest-direct`, `integration` and `integration-full` jobs run `uv pip install --system [--resolution lowest-direct] -e . --group dev` with the same pinned uv (`0.12.17`, which supports `--group`). The upstream canary jobs upgrade pip to 25.1 or later and run `python -m pip install -e . --group dev`. No workflow permissions, triggers or secrets change. Refs #398.

- **CI calls the Make targets (#379)** — the unit lane runs `make lint`, `make format-check`, `make typecheck` and `make test` (the Codecov upload of `coverage.xml` stays a CI-only step), and the live jobs in `ci.yml` and `integration-full.yml` run `make integration CUBRID_VERSION=${{ matrix.cubrid }}` instead of inline `docker run`, readiness and `docker logs` steps; the container log is still printed on a failure. The live container no longer publishes the unused CUBRID master port 1523. The Python and CUBRID matrices, the lane selection, the coverage threshold and the test selection are unchanged; `lowest-direct` and the upstream canary still run pytest directly without coverage. Refs #379.
- **Editing `make integration` runs the live lane (#381)** — `scripts/ci_scope.py` now selects the default live CUBRID lane, besides the unit lane, for a pull request that changes the `Makefile` or `scripts/run_integration.py`, which implement the live job's `make integration`. Before, both were unit-only tooling, so a PR that broke the integration lifecycle passed PR CI. Other `scripts/*` files stay unit-only. Refs #381.

### Tests

- **The live lane fails closed and pins the read-only rejection (#403)** — `tests/conftest.py` makes `pytest -m integration` exit non-zero when no integration test passed (none collected, all deselected or all skipped) or when a test was skipped because the CUBRID server was not configured or unreachable, pinned offline by `tests/test_integration_guard.py`; runs that do not select the marker, such as `make test`, are unchanged. A module fixture creates and drops a disposable `mcp_it_fixture` table, so the five tests that skipped with `no user tables` against a fresh `demodb` now run, and a new live test asserts that INSERT, UPDATE, DELETE and DROP through the default read-only `execute_query` are rejected and leave the table unchanged. The read-only enforcement code is unchanged. Refs #378.
- **Compose environment contract tests (#378)** — `tests/test_makefile.py` pins the `docker-up`, `docker-down` and `docker-clean` commands (only `docker-clean` passes `--volumes`), that `make integration` and `scripts/run_integration.py` do not use Compose, and that `docker-compose.yml` has a single `cubrid` service without `container_name`, the Makefile's default `CUBRID_VERSION` and `CUBRID_TEST_PORT`, a loopback-only broker port, the runner's database name, the `SELECT 1` health check and a named data volume. Refs #378.
- **Install and interpreter drift tests (#398)** — `tests/test_makefile.py` pins `make install`, that every tool recipe follows `PYTHON` and that `PYTHON`, `PYTEST`, `RUFF` and `MYPY` can each be overridden, that `pyproject.toml` has a single `dev` dependency group and no package extra, that no tracked file still installs `.[dev]`, and the CI and canary install commands; `tests/test_workflow_installs.py` requires every uv install to end in `-e . --group dev`; `tests/test_third_party_licenses.py` reads the dev pins from the group. Refs #398.

- **Release-note extraction edge cases (#385)** — `tests/test_extract_release_notes.py` pins that a tag without the `v` prefix (`1.2.0`) writes notes byte-identical to the prefixed form (`v1.2.0`), including the generated `v1.1.0...v1.2.0` compare link, and that an undated `## [1.3.0]` header and a `## [Unreleased]` header are not release sections: extracting them exits 1 with `Missing dated CHANGELOG section` and writes no `RELEASE_NOTES.md`. Refs #385.
- **Makefile semantics and CI parity tests (#379)** — `tests/test_makefile.py` reads each target with `make -n` and pins its commands (CI paths and flags, `check` and `verify` composition, coverage enforcement, only `format` mutating, `clean` removing only gitignored untracked paths, grouped `help`, a fail-closed `doctor`) and that the CI jobs call the targets; `tests/test_run_integration.py` drives `scripts/run_integration.py` with a fake `docker` and checks cleanup and exit statuses on success, test failure, start failure, readiness timeout, cleanup failure, missing Docker, SIGINT and SIGTERM. Refs #379.

## [0.5.2] - 2026-10-20

### Fixed

- **The `db_serial` column probe keeps transport failures and its connection (#351)** — `list_serials` resolves whether `db_serial` names its column `att_name` (CUBRID 10.2–11.2) or `attr_name` (11.4) with a zero-row probe per connection. The probe treated every error as "this spelling is missing": a timeout or a lost connection on the first probe made it try the other spelling, and two such failures were reported as `db_serial exposes neither att_name nor attr_name`. A successful probe whose read-transaction rollback then failed also cached its answer after that connection had been discarded, so the replacement connection, possibly on another server version, reused it without probing. Now only a server rejection of the column (a `ProgrammingError`, `IntegrityError` or `DataError` that is not a timeout, as CUBRID 10.2, 11.2 and 11.4 raise) moves on to the other spelling; a timeout raises `QueryTimeoutError` and other failures their sanitized `query failed: ...` error. If the probe's connection is discarded, the call fails with `connection was reset while probing db_serial; retry the request` and nothing is cached; the next call probes the new connection. Refs #351.

* **agent-review:** do not count empty reply-only Copilot records as review rounds ([#349](https://github.com/cubrid-lab/cubrid-mcp-server/issues/349)) ([6d75295](https://github.com/cubrid-lab/cubrid-mcp-server/commit/6d75295e4a724302099c3789213f14cb922e9253))
* **agent-review:** fail closed when a review thread lacks author or resolver identity ([#347](https://github.com/cubrid-lab/cubrid-mcp-server/issues/347)) ([09d746e](https://github.com/cubrid-lab/cubrid-mcp-server/commit/09d746ec158d165b2d9700f346ee3c49eb127b1d)), refs [#346](https://github.com/cubrid-lab/cubrid-mcp-server/issues/346)
* **database:** preserve serial-probe failures and fence the cache to its connection ([#357](https://github.com/cubrid-lab/cubrid-mcp-server/issues/357)) ([0832251](https://github.com/cubrid-lab/cubrid-mcp-server/commit/08322518dd85efeb3e0fe743ebc827deee93788d))

### Documentation

- **A release review checklist (#355)** — `RELEASING.md` now has a checklist to complete before merging a release PR: the candidate's base and final head, each required check's state at that head (missing, approval required, running, failed or cancelled, successful; only successful counts), the review evidence, the impact classification (including 0.x upgrade notes, the `.mcpb/server.json` version agreement and the `serverInfo` tests) and whether there is a user-facing reason to publish (a candidate may stay pending; a documentation-only release stays possible). A release counts as complete when the publisher summaries show publication and post-publication verification for the same tag, SHA and version (`published and verified`, or a published run followed by a successful `verify-only` recovery); the package version stays apart from FastMCP, client and registry tool versions, and `server.json` is not proof of a registry entry. The "start CI after the final bot update" step now describes what happened for candidate #339 (runs waiting as `action_required`, no check runs) instead of saying that bot pushes start no workflow. `CONTRIBUTING.md` and `AGENTS.md` point to the checklist. The release workflows and gates are unchanged. Refs #355.

- **The documentation site says it is built from `main` (#355)** — every page of the site, English and Korean, now opens with a notice that it is development documentation for the `main` branch, built at a linked commit (from `GITHUB_SHA` in GitHub Actions; a local build says that no commit was recorded), that it can describe unpublished changes, and that a published version's documentation is the `docs/` folder at its tag on the release list. The label never reads `__version__`, the release manifest or `.mcpb/server.json`, and the site shows no hardcoded latest version; offline tests render the template for each case. The Quick Start separates the document source, the package release (the version in the source and an open release pull request are not proof of publication) and the one verified combination recorded in #356, and names what was not run. The docs workflow stays build-only on pull requests and is unchanged. Refs #355.

- **The documentation site is grouped by reader (#354)** — the navigation now has Start here (the Quick Start), How-to guides (serving several databases), Reference (tools, resources and prompts; configuration settings; Security Model), Help (Troubleshooting, the issue forms and private vulnerability reporting through `SECURITY.md`) and a 한국어 tab with the same groups, instead of Korean pages nested under Project → Translations. Every English page links its Korean page below the title and every Korean page links back; the documentation home lists the pages by the same groups and warns not to paste secrets or query results into issues. Pages now show previous and next links. `CONTRIBUTING.md` records the page map (reader, question, group and which content #352 owns) and a convention for writing walkthrough steps. No page is renamed, so existing URLs and anchors keep working; no content, tool, setting or security behavior changes. Refs #354.

- **The Quick Start is one safe, tested walkthrough (#352)** — the English and Korean Quick Start now explain how CUBRID, the server and an MCP client fit together and what stdio means, then go step by step: a disposable CUBRID 11.4 Docker lab bound to `127.0.0.1`, an install in a virtual environment, a one-time administrator script that creates the sample table `mcp_quickstart_books` and the account `mcp_reader` with `SELECT` on that table only (in one transaction, refusing to touch existing objects), a FastMCP Python client whose `mcpServers` configuration starts the server with an explicit environment, tool discovery and `health_check`, a first `describe_table`/`execute_query` read and a refused `DELETE`, real first-connection error messages, and a cleanup script that removes only the walkthrough's own objects, with `docker rm -f -v` for the lab's volume. The model's account is never `dba`, and the password stays in an environment variable. Every command and script was run as written on Linux against `cubrid/cubrid:11.4`; the Claude Desktop, Claude Code and Cursor configurations are kept as optional, unverified examples using the same names. The README (English and Korean) and the documentation home point to the walkthrough first, and the README Quick Start states that its values are placeholders. Refs #352.

- **Agent PR review route: Copilot or a maintainer** — maintainer decision of 2026-10-15: a standalone-agent PR needs a substantive submitted Copilot review or a review by a maintainer (a code owner other than the PR's author), recorded on the PR. Reviews by other people or by other AI agents do not satisfy the route. No CI check enforces it; whether to add one is pending (#317). The two-round AI review budget stays. New: under every route, changes to `safety.py`, `database.py`, `audit.py`, `server.py` and workflows that hold write permissions or perform releases need a review that explicitly assesses their invariants, and a maintainer confirms that disposition before merge. `AGENTS.md`, `CONTRIBUTING.md` and the PR template are updated; the Korean docs carry no review rules, so nothing there changes. Refs #317.

* **agents:** accept an independent reviewer agent in the standalone-agent review route ([#342](https://github.com/cubrid-lab/cubrid-mcp-server/issues/342)) ([bbfe3a4](https://github.com/cubrid-lab/cubrid-mcp-server/commit/bbfe3a476fee5c8a63c3f35b823ba305c627eb66)); superseded before this release by [#344](https://github.com/cubrid-lab/cubrid-mcp-server/issues/344): an independent reviewer agent does not satisfy the review route
* **agents:** require a Copilot or maintainer review in the standalone-agent route ([#344](https://github.com/cubrid-lab/cubrid-mcp-server/issues/344)) ([3b18cdf](https://github.com/cubrid-lab/cubrid-mcp-server/commit/3b18cdfbd46a83a70268a2642a18fd5e540cad46)), refs [#317](https://github.com/cubrid-lab/cubrid-mcp-server/issues/317)
* **contributing:** clarify good-first-issue access for human contributors ([#322](https://github.com/cubrid-lab/cubrid-mcp-server/issues/322)) ([b319f9f](https://github.com/cubrid-lab/cubrid-mcp-server/commit/b319f9fe33c7576f412d17c9ca1397a6f89ba246))
* fix Korean documentation typos and links ([#320](https://github.com/cubrid-lab/cubrid-mcp-server/issues/320)) ([6f49f05](https://github.com/cubrid-lab/cubrid-mcp-server/commit/6f49f059ae8e6cf7e9f12d2ed6d31b5641d54680))
* **ko:** fix a typo and broken cross-page links ([#319](https://github.com/cubrid-lab/cubrid-mcp-server/issues/319)) ([6f49f05](https://github.com/cubrid-lab/cubrid-mcp-server/commit/6f49f059ae8e6cf7e9f12d2ed6d31b5641d54680))
* **onboarding:** provide a safe single-client walkthrough with a prepared read-only lab ([#356](https://github.com/cubrid-lab/cubrid-mcp-server/issues/356)) ([e3e0185](https://github.com/cubrid-lab/cubrid-mcp-server/commit/e3e0185f21e25ffe08f5a866a30c2557505b519a)), refs [#352](https://github.com/cubrid-lab/cubrid-mcp-server/issues/352)
* **release:** add a release review checklist to the runbook ([#360](https://github.com/cubrid-lab/cubrid-mcp-server/issues/360)) ([f196135](https://github.com/cubrid-lab/cubrid-mcp-server/commit/f196135b82298e6af701469925e57424f345dab0)), refs [#355](https://github.com/cubrid-lab/cubrid-mcp-server/issues/355)
* **site:** label the site as main-branch documentation with its build commit ([#359](https://github.com/cubrid-lab/cubrid-mcp-server/issues/359)) ([08550e7](https://github.com/cubrid-lab/cubrid-mcp-server/commit/08550e7655260de42c78e879bb5eb1580106d67d)), refs [#355](https://github.com/cubrid-lab/cubrid-mcp-server/issues/355)
* **structure:** group the site by reader and make Korean pages peers ([#358](https://github.com/cubrid-lab/cubrid-mcp-server/issues/358)) ([c0f900b](https://github.com/cubrid-lab/cubrid-mcp-server/commit/c0f900b76fe72523e51e5ae4e84fe197324284f8)), refs [#354](https://github.com/cubrid-lab/cubrid-mcp-server/issues/354)

### CI

- **Manual agent runs are recorded and summarized as distributions (#318)** — `scripts/agent_eval.py` adds three commands, `prompt`, `record` and `summarize`:
  - `prompt` gives the agent the task, the issue and the report format, but not the grading key.
  - `record` stores one run: the tool and version, the model and revision, the task revision and prompt digest, the base SHA, the reported and observed commands, the skipped live checks, whether the dry run was network-isolated, the changed files, the wall clock, the time limit, review rework rounds, review findings, an optional exclusion for an unfair run, and the rubric result.
  - `summarize` reports repeated runs per task revision and model as counts with a 95% Wilson interval, never as a bare pass percentage, and counts excluded and not-isolated runs separately.

  `agent-evals/README.md` describes the manual-only protocol: a disposable, credential-free environment, an isolated clone without later history or a push remote, a fixed time limit, and publishing only when allowed. Nothing runs an agent in CI, and no score gates a pull request.

- **Agent evaluation tasks for audit redaction and connection cleanup (#318)** — `agent-evals/` adds `audit-category-after-comments` (#179) and `trace-cleanup-discards-connection` (#264). The first checks the audit category read past leading comments, with comments and literals kept out of the record. The second checks that a failed trace cleanup retires the shared connection, using a fake driver. Each task has evaluator-owned hidden tests that fail at its base and pass at its fix, plus the shared policy invariants. Their fixtures cover tests and docs without the source fix, an audit leak, stdout contamination, an unrelated modification and a missing *not verified* statement, and their dry-run results are real `run` output. No runtime or CI lane change.

- **Offline agent evaluation tasks and grader (#318)** — `agent-evals/` adds a versioned task format for benchmarking coding agents on frozen historical fixes, and `scripts/agent_eval.py` grades a candidate's patch, test report and dry-run result. It checks the task's evaluator-owned hidden tests at its base SHA. These include shared policy invariants: read-only by default, write mode and audit off by default, writes rejected, redacted audit records and no stdout writes. It also checks the changed-file scope, the `docs/TOOLS.md` / `docs/SECURITY_MODEL.md` and CHANGELOG updates, a policy check on the patch (stdout writes, removed read-only or write-mode guards, escalating defaults, raw SQL in the audit record or logs, hardcoded secrets) and honest live evidence: stale results, a live claim without a recorded run, or an integration test reported as offline evidence fail. Findings and errors never quote candidate text; they name the file and rule or an entry index. The tests use mocks only. The dry run passes only an allowlisted environment (no tokens, credentials or `CUBRID*` settings), disables network access through `unshare -rn` where available (`--require-isolation` makes it mandatory), bounds every command and never runs integration tests. The first task is the #295 read-only fix, with fixtures for each of these failures. `make agent-eval-check` re-grades them deterministically, and `scripts/ci_scope.py` sends every `agent-evals/` change to the unit lane, so the grader's tests run (README changes included) without a live CUBRID. No score gates a pull request, and `ci-gate` and the runtime security policy are unchanged.

- **A change to the site notice template runs its tests (#361)** — `scripts/ci_scope.py` classified `docs/overrides/` and `mkdocs.yml` as documentation only, so a pull request that changed only the notice template or its `mkdocs.yml` wiring selected no unit lane, and `tests/test_docs_channel_notice.py` did not run. Both are now tooling paths: they select the Python 3.12 unit lane and start no CUBRID. `CONTRIBUTING.md`'s lane table is updated.

- **The site notice template tests run in CI (#361)** — `tests/test_docs_channel_notice.py` skipped its seven rendering tests in every `lint-and-test` lane, because `.[dev]` did not install Jinja2 and the documentation build runs no tests. The `dev` extra now includes `jinja2>=3.1`, and the test imports it directly instead of skipping, so a lane without it fails. `THIRD_PARTY_LICENSES.md` records Jinja2 and MarkupSafe. No workflow changes.

- **`agent-review` no longer counts empty reply-only Copilot records as review rounds (#348)** — a Copilot record with no body and no thread-opening comment, such as a reply to an existing thread, is now ignored like an error or quota notice. It used to count as a summary-only round, so one substantive review plus two such records put a PR past the two-round budget and rejected valid evidence. A record that opens a thread still counts. The same change goes unchanged to the cookbook, pycubrid and sqlalchemy-cubrid copies (Refs cubrid-lab/sqlalchemy-cubrid#933).
- **`agent-review` fails closed on incomplete review-thread and commit identities (#346)** — a review thread whose first comment lacks `author`, a resolved thread that lacks `resolvedBy`, a non-neutral commit without `author` or `committer`, or any of them without a login now fails the check. Before, the identity silently became empty, so an unresolved or author-resolved security thread, or a maintainer's own commit, could be ignored. An explicit `null` (a deleted account, or a commit email linked to no account) is still accepted, and `isResolved` must be a boolean. Ported from cubrid-lab/cubrid-cookbook-python#379, so the two gate scripts again differ only in their constants block and issue number.
- **Advisory `agent-review` check for review evidence** — `.github/workflows/agent-review.yml` runs `scripts/agent_review_gate.py` from the base branch with a read-only token on every pull request and review event and reports whether GitHub's own review records meet the review route of 2026-10-15: a substantive Copilot review within the two-round AI review budget, or a maintainer's `APPROVED` review or `COMMENTED` review that opens an inline thread. Changes to `safety.py`, `database.py`, `audit.py`, `server.py`, `config.py`, `__main__.py`, `context.py`, any workflow and the gate itself need a maintainer's `APPROVED` review. Pending requests, PR-body checkboxes, summary-only bot text, other people's reviews and stale reviews never count; unresolved or author-resolved critical or security threads and missing API data fail the check. release-please PRs that change only release-please files, and Dependabot PRs, are exempt. The check is advisory: a pull request can publish a check with the same name, so it must not be made a required check until it is posted from an identity a PR cannot impersonate. `CONTRIBUTING.md` documents the rules (#317).

## [0.5.1] - 2026-10-14

### Upgrade notes

- **Owner-qualified table names on CUBRID 11.2 and later** — `all_table_names`, `filter_table_names`, `describe_table`, `table_row_counts`, `list_class_hierarchy` and the `cubrid://schema` resources now return table names as `owner.table` (for example `dba.product`) on CUBRID 11.2 and later. Clients that compared these names with bare table names must accept the owner prefix. Bare names are still accepted as input; one that several owners share now fails as ambiguous unless the configured user owns one of them. CUBRID 10.2 and 11.0 are unchanged.
- **`CALL`, `EVALUATE` and `KILL` in `execute_query` with `CUBRID_MCP_READONLY=0`** — these statements now fail before execution. Call stored functions from a `SELECT` (`SELECT my_function(…)`) and evaluate expressions with `SELECT`; `KILL` is not offered by any tool.
- **`INCR`, `DECR`, serial advances and the click counter in `execute_query` with `CUBRID_MCP_READONLY=0`** — these forms now fail before execution, as they already did in read-only mode. Use `execute_write` for writes; read a serial with `CURRENT_VALUE`.

### Removed

- **Test-only helpers left the package** — `AppContext.single()` (`cubrid_mcp_server/context.py`) and `ConnectionRegistry.names` (`cubrid_mcp_server/config.py`) were used only by the tests. The tests now build single-connection contexts with `tests/helpers.py:single_context()` and read `sorted(registry.configs)`. The server never called either helper, so its behavior is unchanged.

### Fixed

- **MCP `serverInfo.version` is the package version** — the server passes `__version__` to FastMCP, which otherwise reported its own version (for example `4.1.0`) in the `initialize` response.
- **Audit `category` ignores leading comments** — the audit log reads the statement category after stripping comments and string literals, as it already did for table identifiers, so `-- note\nSELECT …` and `/* note */ SELECT …` are `SELECT` and `/* SELECT */ DELETE …` is `DELETE`. Literals and comments are found with the same CUBRID-aware scanner as the SQL checks (`//` line comments, `\r` line ends, unterminated block comments or literals), under both `no_backslash_escapes` settings, and double-quoted text that is not a plain name is treated as a literal, so audit records never echo text that is a literal or comment under either reading.
- **SQL checks read comments, quotes and statements with CUBRID's rules** — `ensure_read_only`, `ensure_query_statement` and `ensure_write_allowed` no longer rely on `sqlparse`'s generic lexer for comment, quote and `;` boundaries, which differ from CUBRID's: `sqlparse` does not know CUBRID's `//` line comments, reads `#` and `$$ … $$` as a comment and a string where CUBRID does not, and reads a backslash as a quote escape. A comment that names an allowed keyword can no longer hide the real leading statement, and input that CUBRID would split into more than one statement is rejected. Input with an unterminated quote, or whose quote boundaries depend on the server parameter `no_backslash_escapes`, is now rejected; escape a quote by doubling the quote character used (`''` or `""`).
- **The release workflow is named `publish-pypi.yml` again** — `.github/workflows/release.yml` is renamed back to `.github/workflows/publish-pypi.yml`, the workflow filename registered as the PyPI Trusted Publisher (environment `pypi`). Under the `release.yml` name the 0.5.0 run failed at the PyPI upload with "Publisher with matching claims was not found". The shared release scripts (`release_detect.py`, `release_summary.py`, `verify_dist.py`, `pypi_duplicate_guard.py`, `reconcile_release_labels.py`) are again byte-identical with pycubrid and sqlalchemy-cubrid, and `RELEASING.md`, `CONTRIBUTING.md`, `AGENTS.md`, the `Makefile` and the workflow tests name `publish-pypi.yml`. `RELEASING.md` notes that the filename is the Trusted Publisher identity and must not be renamed. No runtime change.
- **`#`-prefixed names are one name in the side-effect check** — CUBRID accepts `#` as the first character of an identifier, but the check read `SELECT #incr(cnt) FROM t` as `#` followed by `INCR(` and rejected it as the `INCR` side effect. `#incr`, `#decr`, `#next_value` and the like are now read as single names and pass the check (on CUBRID 10.2 and 11.4 the server then reports `Function #incr is undefined` unless such a function exists). `INCR(`, `x.next_value` and the other side-effect forms are still rejected, including next to a `#` name (`SELECT #a, INCR(cnt) …`) and after a lone `#`.
- **`CUBRID_MCP_MAX_CHARS` limits the first row of a result** — `execute_query` always returned the first row whole and capped each value on its own, so a 60-column `SELECT` of `REPEAT('x', 3990)` returned 239,688 characters with `truncated: false` against the default cap of 4000. The cap now runs across the values of every row: rows are returned while they fit whole, and a first row that alone is longer is cut to the cap (later values become `…`, so it can exceed the cap by one character per later column). `truncated` is now `true` whenever a value was cut, including a single long value in a one-row result. A later row is left out rather than cut. `docs/TOOLS.md` and `docs/ko/TOOLS.md` describe how the cap is counted.
- **Table metadata is selected by owner on CUBRID 11.2 and later** — the schema tools ignored the owner, so with `dba.t` and `other.t` both present, `all_table_names()` returned `['t', 't']`, `describe_table('t')` merged the columns of both tables, and `table_row_counts()` failed for every table, because an unqualified `"t"` resolves to the configured user's own `t`. The tools now read `db_class.owner_name`, filter `db_attribute`, `db_index`, `db_index_key` and `db_direct_super_class` on owner and table name, count `"OWNER"."table"`, and return `owner.table`. An unqualified name resolves to the only table with that name, or to the configured user's own table, and otherwise fails as ambiguous. Whether the catalog has owner columns is probed once per connection, like the `db_serial` column; CUBRID 10.2 and 11.0 keep unqualified names. `docs/TOOLS.md` and `docs/ko/TOOLS.md` describe the naming, and their examples show the 11.4 output.
- **`explain_query` reads, recovers and caps like `execute_query`** — it found the leading keyword by splitting on whitespace, so `SELECT*FROM t` and `(SELECT 1)` were rejected with "only accepts SELECT or WITH" although `execute_query` runs them; it now reads the keyword with the same rules as the SQL checks. A statement the server rejects (`ProgrammingError`, `IntegrityError`, `DataError`) no longer discards the connection held for `SET TRACE ON … SHOW TRACE`: the transaction is rolled back and the session kept, as `execute_query` already did, so a mistyped query no longer forces a reconnect. The plan is now capped at `CUBRID_MCP_MAX_CHARS` and the result has a new `truncated` field. `docs/TOOLS.md` and `docs/ko/TOOLS.md` describe the behavior.

* **audit:** determine SQL category after stripping leading comments ([#283](https://github.com/cubrid-lab/cubrid-mcp-server/issues/283)) ([2c64d0f](https://github.com/cubrid-lab/cubrid-mcp-server/commit/2c64d0f74d4a3bb6fa9cc0619e4e5b05a559f492))
* **safety:** reject CALL and KILL in execute_query when read-only mode is off ([#304](https://github.com/cubrid-lab/cubrid-mcp-server/issues/304)) ([49bb56f](https://github.com/cubrid-lab/cubrid-mcp-server/commit/49bb56f3d196ce3f73de45e809da2e78a38bb4ca))
* **safety:** reject INCR and serial advances in execute_query with the whitelist off ([#305](https://github.com/cubrid-lab/cubrid-mcp-server/issues/305)) ([56c97eb](https://github.com/cubrid-lab/cubrid-mcp-server/commit/56c97eb99052f231d8103d7dbb6002153ddc03e3)), refs [#301](https://github.com/cubrid-lab/cubrid-mcp-server/issues/301) [#303](https://github.com/cubrid-lab/cubrid-mcp-server/issues/303)
* **safety:** reject INCR, DECR and serial advances in read-only queries ([#302](https://github.com/cubrid-lab/cubrid-mcp-server/issues/302)) ([d17bf58](https://github.com/cubrid-lab/cubrid-mcp-server/commit/d17bf584d9987f39752357398e5f0d05ee23f23a))
* **server:** report the package version in MCP serverInfo ([#288](https://github.com/cubrid-lab/cubrid-mcp-server/issues/288)) ([55fea91](https://github.com/cubrid-lab/cubrid-mcp-server/commit/55fea91d9428fe7b421f25564dcef0864de85b6b))
* **tools:** cap the first result row at the configured character limit ([#306](https://github.com/cubrid-lab/cubrid-mcp-server/issues/306)) ([094b3c6](https://github.com/cubrid-lab/cubrid-mcp-server/commit/094b3c6fbe74892e629284c48fe87a8e735e6578))
* **tools:** parse, keep connections and cap output in explain_query like execute_query ([#308](https://github.com/cubrid-lab/cubrid-mcp-server/issues/308)) ([75dd0cc](https://github.com/cubrid-lab/cubrid-mcp-server/commit/75dd0cc4de2dcb9d16fa40811edd154e96142c69))
* **tools:** qualify table metadata by owner on CUBRID 11.2 and later ([#307](https://github.com/cubrid-lab/cubrid-mcp-server/issues/307)) ([6f8a60f](https://github.com/cubrid-lab/cubrid-mcp-server/commit/6f8a60f602f657b42ed27836fe025836ffc13f28))

### Security

- **Read-only mode rejects `INCR`, `DECR`, serial advances and the click counter** — `ensure_read_only` checked only `sqlparse` keyword tokens, so `SELECT INCR(cnt) …`, `DECR(…)`, `serial.NEXT_VALUE`, `serial.NEXTVAL`, `SERIAL_NEXT_VALUE(serial, n)` and `SELECT … WITH INCREMENT FOR col` / `WITH DECREMENT FOR col` passed `execute_query` and `explain_query` and changed data. The rollback after the read does not undo these changes, and a `SELECT`-only grant does not prevent them: on CUBRID 11.4 a user granted only `SELECT` on a table increased a column in it and advanced a serial it had no grant on. Read-only mode now rejects these names when they are called or used as an attribute, in any case, bare or quoted (`"INCR"`, `[incr]`, `` `incr` ``), with whitespace or comments in between, anywhere in the statement, including subqueries and CTEs; string literals and longer names such as `incr_total` are not matched. `CURRENT_VALUE`, `CURRVAL` and `SERIAL_CURRENT_VALUE` stay allowed. A qualified column with one of these names (`t.next_value`) is now rejected. `docs/SECURITY_MODEL.md`, `SECURITY.md`, `docs/TOOLS.md` and the README say that a `SELECT`-only grant does not stop them.
- **No tool can change the session user** — with `CUBRID_MCP_READONLY=0`, `execute_query` accepted `CALL`, `EVALUATE` and `KILL`, because none of them was in its reject list. `CALL login('dba', '') ON CLASS db_user` returned a row and switched the cached shared session to `dba` for every later tool call, including `execute_write`; `KILL` ends other sessions' transactions. `execute_query` now rejects all three with `CUBRID_MCP_READONLY=0`. `execute_write` (`INSERT`/`UPDATE`/`DELETE` only) and `explain_query` (`SELECT`/`WITH` only) already rejected them, and on CUBRID 10.2 and 11.4 the server rejects `login` called inside a `SELECT`, `INSERT`, `UPDATE` or `DELETE`. All three checks now also match the first word of the statement: `sqlparse` reads `KILL` and `EVALUATE` as names, so `KILL (SELECT 1)` and `EVALUATE (SELECT 1)` passed read-only mode as a `SELECT`, and `EVALUATE (UPDATE …)` passed the write check as an `UPDATE`. `LOCK` is not a CUBRID statement (a syntax error on 10.2 and 11.4) and `GET` only reads a server setting, so neither is added. `README.md`, `SECURITY.md`, `docs/SECURITY_MODEL.md`, `docs/TOOLS.md`, `llms.txt` and the Korean translations list the new keywords.
- **`execute_query` stays read-only with `CUBRID_MCP_READONLY=0`** — with the whitelist off, `execute_query` matched only the leading keyword, so `SELECT INCR(cnt) …`, `DECR(…)`, `serial.NEXT_VALUE`, `serial.NEXTVAL`, `SERIAL_NEXT_VALUE(serial, n)` and `SELECT … WITH INCREMENT FOR col` / `WITH DECREMENT FOR col` ran and changed data that the rollback after the read does not undo. `docs/TOOLS.md`, `docs/SECURITY_MODEL.md` and the tool description said `execute_query` is read-only in that mode. It now rejects these forms with the same check as read-only mode, and the error points to `execute_write`. `README.md`, `SECURITY.md`, `docs/SECURITY_MODEL.md`, `docs/TOOLS.md`, `llms.txt` and the Korean translations are updated to match.

### Documentation

- **Abandoned release without a tag** — RELEASING.md's abandoned-version recovery now says to set the top-level `last-release-sha` in `release-please-config.json` to the abandoned merge SHA before preparing the next release. Otherwise release-please 17.6.0 falls back to `bootstrap-sha` and lists every commit since then again. The recovery also says to fold the unpublished section under `autorelease: review` and to remove the override after the next release is tagged. sqlalchemy-cubrid and pycubrid document the same recovery (cubrid-lab/sqlalchemy-cubrid#912, cubrid-lab/pycubrid#930).
- **The README and the documentation site show the CUBRID Lab repository icon (#310)** — `README.md` and the Korean `docs/README.ko.md` open with the cubrid-mcp-server MCP icon, centered and without a caption, and the documentation site uses it as its header logo and favicon. All of them load the SVG from one immutable [cubrid-lab/brand](https://github.com/cubrid-lab/brand) commit.
- **Korean README lists the related projects** — `docs/README.ko.md` now has the Related Projects section (pycubrid, sqlalchemy-cubrid, cubrid-cookbook-python) that the English README already had.
- **README demo GIF recorded from a real MCP session** — `docs/demo.gif` was rendered from a script of hard-coded output lines (`demos/mcp-demo.json`, `demos/render_gif.py`), which also showed a stale version. It is now a terminal recording of `demos/mcp_demo.py`, an MCP stdio client that lists the tools, calls `all_table_names` and sends a `DROP TABLE` that `execute_query` rejects; `demos/record_demo.sh` records it with asciinema and agg. The VHS tape `demos/mcp-demo.tape`, which printed a hard-coded tool count, and the scripted renderer are removed. The Claude Desktop recording and the docs-site video remain to be recorded by hand.
- **Per-tool JSON response examples in `docs/TOOLS.md`** — every tool, including `execute_write`, now has a response example captured from real tool calls over MCP stdio against the `cubrid/cubrid:11.4` Docker image with a small demo schema (shown on the page): truncation flags for `execute_query`, `null` row counts with `error` for `table_row_counts`, the `affected_rows` result of `execute_write`, and rejected calls for `execute_query` and `execute_write`. The Korean `docs/ko/TOOLS.md` has the same examples.

* add per-tool JSON response examples to TOOLS.md ([#285](https://github.com/cubrid-lab/cubrid-mcp-server/issues/285)) ([d88b998](https://github.com/cubrid-lab/cubrid-mcp-server/commit/d88b99820ed1afa6392bb574762d6917dbdc7aad))
* add Related Projects to the Korean README and test the empty password ([#293](https://github.com/cubrid-lab/cubrid-mcp-server/issues/293)) ([908f834](https://github.com/cubrid-lab/cubrid-mcp-server/commit/908f8348650b298db257c65c1639869e07b3709e))
* **agents:** refresh the module list and tool surface in AGENTS.md ([#289](https://github.com/cubrid-lab/cubrid-mcp-server/issues/289)) ([d10f0bc](https://github.com/cubrid-lab/cubrid-mcp-server/commit/d10f0bc46cbcbef3a3a94393a1317f3a61c6c64d))
* **brand:** show the centered repository icon in the README and docs site ([#316](https://github.com/cubrid-lab/cubrid-mcp-server/issues/316)) ([666174d](https://github.com/cubrid-lab/cubrid-mcp-server/commit/666174d30abeab16b561551bd938bed0bd7b7669)), refs [#310](https://github.com/cubrid-lab/cubrid-mcp-server/issues/310)
* record the README demo GIF from a real MCP session ([#287](https://github.com/cubrid-lab/cubrid-mcp-server/issues/287)) ([f46426b](https://github.com/cubrid-lab/cubrid-mcp-server/commit/f46426b30a9637537f93102a9d62c8e5087acb7f))
* **release:** set last-release-sha when an abandoned release has no tag ([#323](https://github.com/cubrid-lab/cubrid-mcp-server/issues/323)) ([a4ffb9b](https://github.com/cubrid-lab/cubrid-mcp-server/commit/a4ffb9ba3dac79c7afb4c94f5bc9b189298b9f65))

### Tests

- **Empty `CUBRID_PASSWORD` is covered** — `tests/test_config.py` checks that an empty password is accepted, as CUBRID's default `dba` user has none.

## [0.5.0] - 2026-10-12

### Upgrade notes

- **`table_row_counts` result shape (#239)** — clients that read the result as a list must read `result["tables"]` instead, and check `truncated` after a call without `table_names`.
- **`EXPLAIN` in `execute_query` (#250)** — it never ran on CUBRID; use the `explain_query` tool for execution plans.
- **`execute_query` with `CUBRID_MCP_READONLY=0` (#235)** — clients that sent `INSERT`/`UPDATE`/`DELETE` through `execute_query` with the whitelist disabled must use `execute_write` (enable it with `CUBRID_MCP_WRITE=1`, or `CUBRID_<NAME>_MCP_WRITE=1` per connection). Those statements, `COMMIT`/`ROLLBACK`, `PREPARE`/`EXECUTE`/`DEALLOCATE`, `DO` and multi-statement input now fail before execution.
- **Python 3.10 users** must either upgrade to Python 3.11 or later, or stay on the last cubrid-mcp-server release that supports 3.10 together with a driver release compatible with 3.10. Newer pycubrid lines (1.10+) do not support Python 3.10, and this project does not imply otherwise.

### Added

* add MCP Registry server.json ([f04c32e](https://github.com/cubrid-lab/cubrid-mcp-server/commit/f04c32e58ead79e633bbc3425b25b94e8ebe2a50))
* add MCP Registry server.json for official listing ([c45bfd5](https://github.com/cubrid-lab/cubrid-mcp-server/commit/c45bfd5217824d9178d5036aa2b1f7d440e3e49e))
* CUBRID Skills — domain knowledge resources + expert prompts + tool hints + server instructions ([#162](https://github.com/cubrid-lab/cubrid-mcp-server/issues/162)) ([#163](https://github.com/cubrid-lab/cubrid-mcp-server/issues/163)) ([79927e5](https://github.com/cubrid-lab/cubrid-mcp-server/commit/79927e5b376afb05eb424e15163d29930e3ff62c))
* VHS terminal demo script — MCP server programmatic interaction ([#165](https://github.com/cubrid-lab/cubrid-mcp-server/issues/165)) ([685a437](https://github.com/cubrid-lab/cubrid-mcp-server/commit/685a4379659ac1d67a4e84f92d16c1c252fce4a7))

### Changed

- **`table_row_counts` caps the default call instead of failing beyond 50 tables (#239)** — behaviour change. With no `table_names` on a database with more than 50 user tables the tool raised `too many tables requested`, although its docstring promised a capped result and the `explore_unknown_db` prompt tells the model to call it. The default call now counts the first 50 user tables in name order. The result is now an object, `{"tables": [...], "truncated": bool, "total_tables": int}`, matching how `execute_query` signals truncation: `tables` holds the per-table entries the tool returned before, `truncated` is `true` when the default call left tables out, and `total_tables` is the number of user tables. An explicit list of more than 50 names still raises; `[]` still counts nothing. `TOOLS.md` (EN/KO) and the `explore_unknown_db` prompt describe the cap and how to fetch the rest.
- **`EXPLAIN` removed from `execute_query`'s read-only whitelist (#250)** — CUBRID has no `EXPLAIN` statement: on CUBRID 11.4.6, `EXPLAIN SELECT 1` (and `EXPLAIN PLAN FOR …`) fail at the server with a syntax error, so the whitelist admitted a statement that could never run. `READ_ONLY_KEYWORDS` is now `SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `WITH`, and with `CUBRID_MCP_READONLY=1` (the default) `EXPLAIN …` is rejected before it reaches the database with `UnsafeSQLError`; with `CUBRID_MCP_READONLY=0` it is not a rejected keyword and still fails at the server. README (EN/KO), `SECURITY.md`, the Security Model (EN/KO), Troubleshooting (EN/KO), the docs home page, ROADMAP and the `cubrid://agent-guide` resource no longer list it and point to the `explain_query` tool, which already uses CUBRID's `SET TRACE`/`SHOW TRACE`. A live integration test pins both the server rejection and the whitelist rejection. No other lexer change.
- **`execute_query` stays read-only when `CUBRID_MCP_READONLY=0` (#235)** — behaviour change. `CUBRID_MCP_READONLY=0` now only relaxes the read-only whitelist; it no longer lets `execute_query` run writes. With the whitelist off, `execute_query` rejects any statement that leads with a write, DDL or transaction-control keyword (`INSERT`, `UPDATE`, `DELETE`, `REPLACE`, `MERGE`, `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `RENAME`, `GRANT`, `REVOKE`, `COMMIT`, `ROLLBACK`, `SAVEPOINT`, `SET`, `PREPARE`, `EXECUTE`, `DEALLOCATE`, `DO`) before it reaches the database, with an `UnsafeSQLError` pointing to `execute_write`; the first word of the leading keyword is matched, so `CREATE OR REPLACE …` is rejected like `CREATE`. Multi-statement input (`multi-statement SQL is not allowed in execute_query`) and empty input — including comment-only or `;`-only input — are rejected too, as in read-only mode. The keyword check is a guardrail; the read-only database account remains the security boundary. Previously such a statement ran, was reported as `query failed: InterfaceError` and cost the shared connection. As a backstop, a statement that returns no result set (`cursor.description is None`) is rolled back and fails with `ValueError: statement produced no result set; execute_query is read-only, use execute_write …`, and the connection is kept instead of discarded. With `CUBRID_MCP_READONLY=1` (the default) the whitelist and its error messages are unchanged. Result-set reads (`SELECT`, `WITH … SELECT`, `SHOW`, `DESC`, and with the whitelist off also `CALL`s that return a value) are unaffected.
- **Python 3.11 is now the minimum supported version (#221)** — `requires-python` is `>=3.11` (Python 3.10 reached upstream end of life on 2026-10-01); the 3.10 classifier is removed, Ruff targets `py311` and mypy `3.11`. Python 3.14 is added to the classifiers and the unit/full-integration matrices after the offline suite, Ruff and mypy passed on 3.14. The `lowest-direct` job and Codecov upload moved to 3.11; lowest-direct resolves FastMCP 3.0.0, pycubrid 1.4.0 and sqlparse 0.5.0 and passes. No MCP, SQL-safety, timeout or audit behavior changes; direct dependency floors are unchanged.

### Fixed

- **`explain_query` discards the connection when trace cleanup fails (#264)** — after the statement ran, `explain_query` turns tracing off and rolls back on the shared connection. A failure to open the cleanup cursor, run `SET TRACE OFF` or roll back was only logged, so the next tool call could reuse a session that still had tracing on or a transaction open. Any such failure now discards the connection under the connection lock, so the next call reconnects; cleanup stops at the first failed step, and after a query timeout no cleanup statement is sent. A successful query still returns its plan, a query error is still the error the client sees, and a healthy cleanup keeps the connection. `TOOLS.md` and the Security Model (EN/KO) describe the behavior.
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

* accept leading comments in explain_query ([#203](https://github.com/cubrid-lab/cubrid-mcp-server/issues/203)) ([7e10f29](https://github.com/cubrid-lab/cubrid-mcp-server/commit/7e10f29c55eae08ca48780405f78ffbb0e6307bf))
* **database:** discard the shared connection when trace cleanup fails ([#269](https://github.com/cubrid-lab/cubrid-mcp-server/issues/269)) ([739dca0](https://github.com/cubrid-lab/cubrid-mcp-server/commit/739dca082a0026ee9ab8210d546b7f2520741460)), refs [#264](https://github.com/cubrid-lab/cubrid-mcp-server/issues/264)
* **database:** end the read transaction after every fetch ([#246](https://github.com/cubrid-lab/cubrid-mcp-server/issues/246)) ([1c838f2](https://github.com/cubrid-lab/cubrid-mcp-server/commit/1c838f24fb6d5f9f6afcd9b78731487d78159d6b))
* **database:** route cursor-creation failures through recovery and re-probe serial column after reconnect ([#200](https://github.com/cubrid-lab/cubrid-mcp-server/issues/200)) ([a4f3492](https://github.com/cubrid-lab/cubrid-mcp-server/commit/a4f34922cc17a784be810bc44d91f0d592dc1364))
* **database:** stop returning host and database names in connect and health_check errors ([#248](https://github.com/cubrid-lab/cubrid-mcp-server/issues/248)) ([aa2f547](https://github.com/cubrid-lab/cubrid-mcp-server/commit/aa2f5479e5518665ccda3af81a22ef677b6be3c4))
* distinguish empty table_names from omitted in table_row_counts ([#183](https://github.com/cubrid-lab/cubrid-mcp-server/issues/183)) ([e6748f0](https://github.com/cubrid-lab/cubrid-mcp-server/commit/e6748f04cbeb0d8df35313226f03061791254f0b))
* preserve composite PK order and make the FastMCP canary reach pytest ([#198](https://github.com/cubrid-lab/cubrid-mcp-server/issues/198)) ([3f9b97e](https://github.com/cubrid-lab/cubrid-mcp-server/commit/3f9b97ede33e62a27187693dc50333d09016b91b))
* regenerate demo GIF — 8fps, 800x450, 10s ([#167](https://github.com/cubrid-lab/cubrid-mcp-server/issues/167)) ([16fba7e](https://github.com/cubrid-lab/cubrid-mcp-server/commit/16fba7e15a35b7866826f5b8afae4d67aecc0916))
* reject blank required connection values ([#194](https://github.com/cubrid-lab/cubrid-mcp-server/issues/194)) ([12e6a0d](https://github.com/cubrid-lab/cubrid-mcp-server/commit/12e6a0d3a0d3d617c73cd1933c2370446eab1fcd))
* reject non-finite query timeouts ([#184](https://github.com/cubrid-lab/cubrid-mcp-server/issues/184)) ([4310a90](https://github.com/cubrid-lab/cubrid-mcp-server/commit/4310a901af89f24b02939dd46dcf4c3cb80cc9ee))
* remove the duplicate environment field from the bug report form ([#190](https://github.com/cubrid-lab/cubrid-mcp-server/issues/190)) ([825d736](https://github.com/cubrid-lab/cubrid-mcp-server/commit/825d7368aa74234dce578647cb0b687ee6e28df5))
* **server:** keep execute_query read-only when CUBRID_MCP_READONLY=0 ([#249](https://github.com/cubrid-lab/cubrid-mcp-server/issues/249)) ([f59308c](https://github.com/cubrid-lab/cubrid-mcp-server/commit/f59308cc07cbdb830910d8cbd350862c645ee978))
* **tools:** fence prompt args, cap table_row_counts, resolve class hierarchy names, drop EXPLAIN ([#252](https://github.com/cubrid-lab/cubrid-mcp-server/issues/252)) ([55e6a23](https://github.com/cubrid-lab/cubrid-mcp-server/commit/55e6a238c46d6dbaca430e9df230af5ac6b0a886))
* validate CUBRID port range ([#193](https://github.com/cubrid-lab/cubrid-mcp-server/issues/193)) ([d679122](https://github.com/cubrid-lab/cubrid-mcp-server/commit/d679122b61810cbaf845f1e0537291e027ae6522))

### Security

- **Every user-supplied prompt argument is fenced as untrusted data (#238)** — `optimize_query` and `migrate_from_mysql` wrapped their `sql` argument in a fixed ```` ```sql ```` fence that the input could close, and `safe_data_analysis` (`question`) and `write_cubrid_sql` (`natural_language`) inserted their argument unfenced, contrary to the README's statement that prompt arguments are fenced. All four now go through `_as_untrusted`, the same labeled block the other prompts use, whose fence grows longer than any backtick run in the value. A protocol-level test discovers every registered prompt that takes arguments and fails if any argument is not inside such a block, including adversarial input with closing fences and backticks. Prompt wording is otherwise unchanged; no tool, SQL-safety or audit change.
- **Connection errors no longer reveal host or database (#236)** — `Database.connect()` now raises the fixed `failed to connect to CUBRID` (previously it included `host=` and `database=`), and `health_check` returns only the exception class name instead of `str(exc)`. `exclusive()` (used by `explain_query`) now raises a sanitized `DatabaseError` for non-timeout driver errors instead of re-raising the raw driver exception, which could carry SQL or host text. Host, port, database and the driver cause are written to the stderr log with `exc_info` for operators. Operators who matched on the old message or the raw `health_check` text must read the server log instead. No tool signature, SQL-safety, timeout or audit change.

### Documentation

- **`main` branch protection documented (#224)** — `CONTRIBUTING.md` now describes the protection baseline for `main`: pull request required, `ci-gate` and `PR title` as required checks, no deletion or force push, no required human or code-owner approval, and no bypass actor, with the reason each release and Dependabot workflow works under it. `RELEASING.md` lists it among the repository settings the release flow relies on.
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

* add issue templates, SUPPORT.md, Code of Conduct, docs badge ([#157](https://github.com/cubrid-lab/cubrid-mcp-server/issues/157)) ([ff1d408](https://github.com/cubrid-lab/cubrid-mcp-server/commit/ff1d40809684aa6768e9597843079627dc184cfe))
* add PyPI version badge to README ([#168](https://github.com/cubrid-lab/cubrid-mcp-server/issues/168)) ([0bc0ca9](https://github.com/cubrid-lab/cubrid-mcp-server/commit/0bc0ca9adbceadeac6270310af47393edf5a960c))
* add Related Projects section linking the cubrid-lab Python stack ([#155](https://github.com/cubrid-lab/cubrid-mcp-server/issues/155)) ([33b9892](https://github.com/cubrid-lab/cubrid-mcp-server/commit/33b9892f3f0631d53c94261f005e3e35110a266d))
* **agents:** add issue size-label convention to AGENTS.md ([#172](https://github.com/cubrid-lab/cubrid-mcp-server/issues/172)) ([33303e5](https://github.com/cubrid-lab/cubrid-mcp-server/commit/33303e50e71a0888cb3130abaec3a6ef38009c53))
* **agents:** align ownership, contributor and review guardrails ([#225](https://github.com/cubrid-lab/cubrid-mcp-server/issues/225)) ([724de18](https://github.com/cubrid-lab/cubrid-mcp-server/commit/724de18fc8f0c84f4dde9142aafdeb1e73ad8adb)), refs [#222](https://github.com/cubrid-lab/cubrid-mcp-server/issues/222)
* **agents:** require priority and size labels when filing issues ([#187](https://github.com/cubrid-lab/cubrid-mcp-server/issues/187)) ([d177ab2](https://github.com/cubrid-lab/cubrid-mcp-server/commit/d177ab27ce4a564256356fd360fc888b5472a2db))
* align security model, docs and changelog with the server ([#253](https://github.com/cubrid-lab/cubrid-mcp-server/issues/253)) ([0649c53](https://github.com/cubrid-lab/cubrid-mcp-server/commit/0649c53d59688b5aa805b4eb83826f16c2ce620a))
* align the closing-guard wording with sqlalchemy-cubrid ([#277](https://github.com/cubrid-lab/cubrid-mcp-server/issues/277)) ([e7eece8](https://github.com/cubrid-lab/cubrid-mcp-server/commit/e7eece86adc913496d86c3c6915a90c48814fd44))
* correct the older closing-guard CHANGELOG notes ([#278](https://github.com/cubrid-lab/cubrid-mcp-server/issues/278)) ([c917df4](https://github.com/cubrid-lab/cubrid-mcp-server/commit/c917df4e920dd68e906439a83a7ea226906e1881))
* embed demo GIF in README ([#166](https://github.com/cubrid-lab/cubrid-mcp-server/issues/166)) ([179b91d](https://github.com/cubrid-lab/cubrid-mcp-server/commit/179b91d1265e0a3b85a45e8f0762b067df4794b9))
* Korean site pages — docs/ko/ (5 pages) ([#161](https://github.com/cubrid-lab/cubrid-mcp-server/issues/161)) ([2db0059](https://github.com/cubrid-lab/cubrid-mcp-server/commit/2db00590f59ac4d31a4bd46030733d33d6b93396))
* **licenses:** reproducible inventory and the real FastMCP range ([#233](https://github.com/cubrid-lab/cubrid-mcp-server/issues/233)) ([7828861](https://github.com/cubrid-lab/cubrid-mcp-server/commit/7828861e21f94fb07fc21f08a092ad55f6a67f67))
* pin cookbook smoke-test fallback to the exact release ([#196](https://github.com/cubrid-lab/cubrid-mcp-server/issues/196)) ([959b6b7](https://github.com/cubrid-lab/cubrid-mcp-server/commit/959b6b7481438f5e23079bf4c3f22f5c83299593))
* **repo:** document the main branch protection baseline ([#266](https://github.com/cubrid-lab/cubrid-mcp-server/issues/266)) ([bf288a0](https://github.com/cubrid-lab/cubrid-mcp-server/commit/bf288a061fac9ae0f18ad0d209ed70df744bc7f5))
* **review:** separate Oracle and GitHub review requirements ([#265](https://github.com/cubrid-lab/cubrid-mcp-server/issues/265)) ([4763bfc](https://github.com/cubrid-lab/cubrid-mcp-server/commit/4763bfc1f268c20d0ae6d342220ab1deeb1e478a))
* **site:** unified six-tab IA, translations group, ecosystem links ([#158](https://github.com/cubrid-lab/cubrid-mcp-server/issues/158)) ([c086826](https://github.com/cubrid-lab/cubrid-mcp-server/commit/c086826fb30b2800b9fb969ee74de34fad479026))
* translation sync markers + translation-sync CI check ([#159](https://github.com/cubrid-lab/cubrid-mcp-server/issues/159)) ([eb66e09](https://github.com/cubrid-lab/cubrid-mcp-server/commit/eb66e0961dcb4b7b894cbc4794e32ce675db9a8d))

### CI

- **The closing guard skips a multi-line link reference definition** — CommonMark
  lets a definition's destination and title run on to later lines, so `Closes`, a
  `[a]:` line, an indented `/target` line and then `owner/repo#N` still renders
  nothing between the keyword and the reference. The gap walk now reaches every
  later line end of the paragraph after a definition line, up to a blank line, which
  can only add blocking; each line end is scanned once per check. Copilot found this
  in cubrid-lab/sqlalchemy-cubrid#822; `pr-title.yml` stays byte-identical across
  pycubrid, sqlalchemy-cubrid, cubrid-mcp-server and cubrid-cookbook-python.
- **Generated issue references are written as "refs", not "closes", in `CHANGELOG.md` and the
  release PR body** — release-please 17.6.0 renders every issue trailer in a commit's final
  footer block as `, closes [#N](…)`, so a commit that only said `Refs #N` was listed as
  closing that issue, and GitHub read the release PR body as closing it on merge.
  `scripts/compose_release_changelog.py` (shared byte for byte with sqlalchemy-cubrid,
  cubrid-lab/sqlalchemy-cubrid#820 and cubrid-lab/sqlalchemy-cubrid#821) now rewrites generated
  references to `, refs [#N](…)` on generated entry lines outside code blocks, and the
  **Prepare release** workflow applies the same rewrite to the release PR body right after
  release-please updates it; no permission changes (#280).
- **The closing guard catches a closing keyword used as link text** —
  `[Closes](url) owner/repo#N` renders as "Closes owner/repo#N", but the gap after
  the keyword stopped at `]`. The `PR title` check now crosses a link's `]`,
  `](destination)` or `][label]`, and also a quoted continuation line, an image's
  alt text and a link reference definition line, each of which renders nothing
  between the keyword and the reference. Scanning stays linear in the body length,
  so adversarial link syntax at GitHub's 65,536-character limit stays well under the
  tests' 5-second timeout. The fix came from Copilot's review of
  cubrid-lab/pycubrid#849, and `pr-title.yml` is again byte-identical across
  pycubrid, sqlalchemy-cubrid, cubrid-mcp-server and cubrid-cookbook-python.
- **The closing guard also checks the PR title and commit messages, and owners with
  an underscore** — the PR title and the PR's commit messages make up the squash
  commit, so the `PR title` check now reads them too, as plain text: Markdown code
  does not hide a keyword there, and each commit message is checked on its own. The
  job lists the commits with `gh api`, using a token that can only read pull
  requests (the job has `pull-requests: read`; the workflow-level permissions stay
  empty), and fails when a PR has 250 or more commits, because GitHub lists only
  250. A test pins that step. Owners with an underscore, as Enterprise Managed Users
  have (`alice_acme/repo#N`), are now matched in references and links. The job setup
  and these checks come from pycubrid's guard (cubrid-lab/pycubrid#845); code-block
  and comment handling of the PR body is unchanged; an underscore inside a word is
  no longer read as emphasis, so underscore owners are matched there too.
  cubrid-cookbook-python (cubrid-lab/cubrid-cookbook-python#294) and
  sqlalchemy-cubrid (cubrid-lab/sqlalchemy-cubrid#818) have the same change.
- **The PR-body closing guard catches emphasized, linked, escaped and split
  closures, and fails closed where Markdown structure is uncertain** — the
  `PR title` check now rejects:
  - emphasis or HTML around the keyword or the reference (`**Closes**`, `*Fixes*`,
    `__Resolves__`, `Closes **owner/repo#N**`, `<b>Closes</b>`), a keyword split by
    markup (`Close**s**`), and inline comments, processing instructions or CDATA
    between the keyword and the reference;
  - `http://`, `www.` and scheme-less `github.com/` issue URLs, autolinks, backslash
    escapes (`\#`), HTML entities (`&#35;`, `&nbsp;`), a backslash line break,
    leading zeros, and a foreign issue listed after another one
    (`Closes #1, owner/repo#2`);
  - a closing keyword followed by a link (`[text](…)`, `[text][label]`, `<a href>`)
    when the body links any foreign issue, absolute or relative, since the link
    text hides its target. This case has its own error message.

  Only fenced and indented code blocks and HTML comment blocks are ignored. Inline
  code and inline comments are scanned, because hiding them needs inline parsing
  that link destinations, HTML attributes and autolinks can defeat. Once a fence
  appears where its extent is unknown (in a list item, a block quote, after a list
  marker, inside raw HTML, on an indented line, or as a line that only looks like a
  fence), no later fence or comment is hidden, so a closing fence can never be
  misread as an opener. Raw HTML blocks end where CommonMark ends them, and any
  other line starting with a tag is treated as raw HTML until a blank line. Comments
  after anything that may start an HTML tag are scanned, a comment also ends at
  `--!>`, and after a raw-text element such as `<textarea>` or `<select>` the rest
  of the body is scanned. Lines split only at CR and LF, a leading byte order mark
  is dropped, and only spaces and tabs count as blank or indentation. A heading,
  block quote, fence, thematic break or comment block directly under a list item now
  ends the list, so indented code after it is ignored instead of blocking the PR.
  Footnote text is treated like list text. A very long issue number is reported
  instead of crashing the check, and long adversarial bodies stay fast at GitHub's
  65,536-character limit. This is the same guard, with the same regression cases, as
  sqlalchemy-cubrid (cubrid-lab/sqlalchemy-cubrid#816) and cubrid-cookbook-python
  (cubrid-lab/cubrid-cookbook-python#293). A test pins the guard block's SHA-256 so
  every copy changes together. `CONTRIBUTING.md` describes when code and comment
  blocks are still checked.
- **The PR-body closing guard keeps list context after a lazy continuation line** — a
  list item followed by an unindented continuation line, a blank line and an
  indented `Closes other/repo#N` is still list text on GitHub, so the `PR title`
  check must scan it. The guard previously ended the list context at the
  continuation line and skipped the closure as indented code. The list context
  now ends only at an unindented paragraph that follows a blank line. The
  regression suite gains this case. (Superseded in part by the entry above: a
  heading, block quote, fence, thematic break or comment block directly under a
  list item now ends the list.)
- **PRs cannot directly auto-close another repository's issue** — the existing
  required `PR title` check rejects foreign closing keywords in PR-body text while
  allowing `Closes #N` for local issues and `Refs owner/repo#N` for genuine
  technical dependencies. The PR body is inert data and the validator uses no
  checkout or token permissions. `Closes: owner/repo#N` is caught too. (Superseded
  in part by the entries above: the job now has a `pull-requests: read` token to
  list the commit messages, and the PR title and commit messages are checked too.)
  The guard is a best-effort line scanner, not a full Markdown parser: fenced,
  indented code and HTML comments are ignored in one pass, so a comment opener
  inside a fence cannot hide a later closure. (Superseded in part by the entry
  above: inline code and inline comments are now scanned.) Indented text in a list
  item is always scanned, and fences inside block quotes or list items are not
  recognized, so either may block a PR but never lets a closure through.
  Repository-local issue and PR templates document ownership.
- **The cookbook verifies the built wheel before it is published
  (cubrid-lab/cubrid-cookbook-python#240)** — `release.yml` gains
  `verify-candidate`, which calls the cookbook smoke test in candidate mode on the
  `release-dist` wheel of the same run (exact file set and SHA-256 checked against
  the `build` job's `sha256` output), and `require-candidate`, which requires
  `status == success`, `evidence == candidate artifact`, installed == requested ==
  the release version and the verified digest == the built wheel's digest, and
  whose downloaded candidate report must name this package, request, run and
  repository,
  `release-dist`, the release commit and the build's file map. `publish` needs
  `require-candidate` and now also checks `dist/` and
  `release-meta/` against the `build` job outputs `sha256` and the new
  `meta_sha256` (`scripts/verify_dist.py`) before tagging. The gate is never
  skipped after a successful build, `resume` included: builds are not
  reproducible, so every run that publishes verifies its own bytes (a
  `gh run rerun --failed` of the same run keeps its earlier verification). A
  `dry-run` dispatch now verifies the freshly built wheel instead of the
  already-published version; the post-publication `verify-cookbook` is
  unchanged. Both cookbook calls use one pin, moved from `32e80c6` to `98866c2`,
  the same pin as pycubrid and sqlalchemy-cubrid. The candidate's drivers still
  come from PyPI. No runtime change.
- **The PyPI duplicate guard uses `hashlib.file_digest()` (#220)** —
  `scripts/pypi_duplicate_guard.py` hashes `dist/` files with the Python 3.11 stdlib
  helper instead of a hand-written chunked read loop; the digests are the same. The
  pycubrid and sqlalchemy-cubrid copies get the same change. No server change.
- **CI installs dependencies with a pinned uv (#229)** — the `lint-and-test`, `integration`, `lowest-direct` and `changelog-lint` jobs in `ci.yml` and the `integration-full` job install with `uv pip install --system` instead of `pip install`, after `astral-sh/setup-uv` v10.2.0 (pinned to its commit SHA, uv `0.12.17`) set up with the job's `python-version` and a per-job cache (`cache-suffix: ${{ github.job }}`, `enable-cache: auto` in the release-called `integration-full.yml`). Each install step logs `uv pip freeze --system`. pip and uv resolve the same `.[dev]` package set (107 packages on Python 3.12, 110 on 3.11, checked locally); `setup-python`'s unused pip cache is dropped. `release.yml` and `release-please.yml` (build tooling and the wheel/sdist smoke venvs), `docs.yml` and `upstream-canary.yml` keep pip. Matches cubrid-lab/pycubrid#763/#766 and cubrid-lab/sqlalchemy-cubrid#750/#752; `tests/test_workflow_installs.py` pins the setup. No runtime change.
- **Workflow edits other than `ci.yml` select the unit lane instead of live CUBRID (#232)** — `scripts/ci_scope.py` mapped `.github/workflows/*` (except `ci.yml`) to Python 3.11/3.12/3.14 plus CUBRID 11.2 + 11.4, but the live lanes only run `ci.yml`'s own `integration` job and cannot detect anything about another workflow. Those edits now select the representative unit lane (Python 3.12) only, plus `lowest-direct` and the endpoint lanes only when `pyproject.toml` also changes; `ci.yml` edits keep the full tier. A workflow-only PR starts no CUBRID container, and the workflow-contract tests all run in the unit lane. CONTRIBUTING gains a per-workflow impact table; `integration-full.yml` and `upstream-canary.yml` edits stay validated by a manual dispatch on the PR head, linked from the PR. `tests/test_workflow_path_impact.py` fails if any test module that reads a workflow file carries the `integration` marker.
- **Release PRs are prepared by release-please, matching pycubrid and sqlalchemy-cubrid (#254)** — the manual `prepare-release.yml` dispatch is removed. On every push to `main` (or a manual dispatch), `.github/workflows/release-please.yml` ("Prepare release") runs the pinned `googleapis/release-please-action` v5.0.0 in PR-only mode (`skip-github-release: true`), proposes the next version from Conventional Commits (`release-please-config.json`, `.release-please-manifest.json`, bootstrapped at the `v0.4.0` commit; pre-1.0, `bump-minor-pre-major` makes a breaking change propose the next minor version, and 1.0.0 needs an explicit `Release-As: 1.0.0`), bumps `__version__` and both `.mcpb/server.json` versions, and `scripts/compose_release_changelog.py` moves the curated `[Unreleased]` notes unchanged under the dated `## [X.Y.Z] - YYYY-MM-DD` section, merged with the generated notes under the standard headings, before `make release-check` and the push. `scripts/reconcile_release_labels.py` runs first and unconditionally: it marks a merged release PR `autorelease: tagged` only after `release.yml` proved the tag, the published GitHub Release and the PyPI and cookbook jobs at its merge SHA, and fails the run when a merged release is blocked instead of letting release-please abort silently. `autorelease: review` freezes a candidate under review. `release.yml` and its `release_detect.py` contract are unchanged, so merging the release PR publishes exactly as before. `scripts/prepare_release.py` stays as an offline utility without a workflow entry point. `RELEASING.md`, `CONTRIBUTING.md` and `AGENTS.md` describe the new preparation, the label lifecycle and the blocked-preparation recovery; offline tests cover the config, the composer, the reconciliation and the workflow step order. No runtime change.
- **Cookbook release verification pinned to the cookbook SHA with the PyPI wait** — the `verify-cookbook` call in `.github/workflows/release.yml` is pinned to `32e80c6ea9ae78324f764d7b873ffb64b000ddcc` (cubrid-cookbook-python#274), the same commit in pycubrid, sqlalchemy-cubrid and cubrid-mcp-server. The cookbook now waits up to 10 minutes for PyPI to serve the exact requested version before installing, and reports what PyPI served if it times out; this fixes the 1.10.0 post-publish stale-CDN failure that blocked release-please. No runtime change.
- **`scripts/lint_changelog.py` applies the duplicate-heading check only after the changelog cutoff** — ported from cubrid-lab/pycubrid#794 and cubrid-lab/sqlalchemy-cubrid#773. Rule 5 (a `###` heading repeated within one version) is now gated by `SECTION_POLICY_CUTOFF` like the section policy: it runs in `[Unreleased]` and in releases after 0.4.0, and released history up to 0.4.0 is never rewritten. This intentionally narrows the check added in #241, which applied to every version; the current CHANGELOG has no historical duplicates. The script now matches pycubrid's and sqlalchemy-cubrid's except for `SECTION_POLICY_CUTOFF`; `CONTRIBUTING.md` documents the cutoff.
- **`scripts/lint_changelog.py` rejects a release header inside an open code fence** — a `## [` line while a fence is open now fails with `ERROR: Release header inside an open code fence in CHANGELOG.md`, because `scripts/extract_release_notes.py` is not fence-aware and a fenced `## [x]` would truncate the GitHub Release body, and a fence opened in `[Unreleased]` and closed in older history would hide real releases. Fenced `###` lines remain entry content. Identical to cubrid-lab/pycubrid#793 apart from `SECTION_POLICY_CUTOFF`; documented in `CONTRIBUTING.md`.
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
- **create-release.yml: dropped `--target` from `gh release create`** — with an already-pushed tag (the normal tag-push trigger) `--verify-tag` already guarantees the tag exists, and passing `target_commitish` for an existing tag makes the Releases API return `422 Validation Failed`, so the first tag-triggered run of this workflow always failed. Verified live by the v0.4.0 tag attempt in cubrid-mcp-server.

### Tests

- **Release-please push guards are pinned (cubrid-lab/pycubrid#801)** —
  `tests/test_release_workflows.py` now asserts the exact, ordered guards of
  `release-please.yml`: the push is directly preceded by the stale-main `exit`
  and the `autorelease: review` re-check, the compose step starts with
  `set -euo pipefail`, the branch `case` guard runs before checkout and is
  followed by the generation-time stale-main `exit`, the freeze step counts the
  exact `autorelease: review` label, and the checkout keeps
  `persist-credentials: false`. Removing or weakening any of them now fails a
  test; before, these mutations passed. `RELEASING.md` gains the recovery row
  for abandoning a merged release (remove `autorelease: pending`, never add
  `autorelease: tagged`), and the blocked-preparation steps say to skip waiting
  for a green publisher run in that case. Test and docs only; the server and
  workflows are unchanged.
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
