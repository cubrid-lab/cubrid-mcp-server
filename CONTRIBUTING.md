# Contributing to cubrid-mcp-server

Thanks for your interest in improving the CUBRID MCP server. This guide covers
the specifics of **this** repository — the Makefile targets, the checks CI
enforces, and how to run the integration suite against a live CUBRID.

For the organization-wide contribution guidelines (code of conduct, how to file
issues, DCO/sign-off, review flow), see the shared
[cubrid-lab/.github/CONTRIBUTING.md](https://github.com/cubrid-lab/.github/blob/main/CONTRIBUTING.md).
This document only adds what is repo-specific; it does not repeat the org guide.

## Prerequisites

- Python 3.11 or later
- pip 25.1 or later (to install the `dev` dependency group; `python -m pip install --upgrade pip`)
- Git
- Docker (only needed for the integration tests)

## Development Setup

```bash
git clone https://github.com/cubrid-lab/cubrid-mcp-server.git
cd cubrid-mcp-server
python3 -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip   # the dev group needs pip >= 25.1

# Editable install plus the dev dependency group (ruff, mypy, pytest, ...)
make install
```

`make install` runs `python3 -m pip install -e . --group dev`. The contributor tools
live in the PEP 735 `[dependency-groups] dev` group of `pyproject.toml`, so they are
not an extra of the published package. The Makefile runs `pytest`, `ruff` and `mypy`
through the same interpreter (`$(PYTHON) -m ...`, `PYTHON ?= python3`); override
`PYTHON`, `PYTEST`, `RUFF` or `MYPY` on the command line to use another one, e.g.
`make lint PYTHON=.venv/bin/python`. `make doctor` then checks that
Python 3.11+, `ruff`, `mypy`, `pytest`, `pytest-cov` and `pytest-asyncio` are
available; it exits non-zero, without a success line, if any is missing. Docker
is reported but optional (only `make integration` and the `docker-*` targets need it). `make help` lists
every target, grouped by purpose.

## Local Checks Before Pushing

The Makefile is the canonical interface: CI's lint, type, unit and live jobs call
these same targets (#379), so passing them locally is the fastest way to avoid a
red build:

```bash
make lint          # ruff check .                (same scope as CI)
make format-check  # ruff format --check .
make typecheck     # mypy (strict) on cubrid_mcp_server
make check         # lint + format-check + typecheck (no tests)
make format        # ruff format . + ruff check --fix . (the only target that edits files)
```

## Tests

```bash
make test               # offline unit tests with coverage; fails below fail_under (95)
make verify             # make check, make test, then make integration (needs Docker); writes test-results/verify/
make integration        # integration tests on a Compose CUBRID it starts and removes
make integration-local  # integration tests against a CUBRID you already run
make docker-up          # a persistent local CUBRID for manual work (Docker Compose)
```

`make test` runs `pytest -m "not integration"` with `--cov=cubrid_mcp_server`,
so the `fail_under = 95` floor in `pyproject.toml` is enforced locally exactly as
in CI. It writes `coverage.xml` (CI uploads that file to Codecov); extra pytest
arguments go in `PYTEST_ARGS`, for example `make test PYTEST_ARGS="-k config -x"`.
`make clean` removes only generated, gitignored artifacts (build output, caches,
`.coverage`, `coverage.xml`, `htmlcov/`, `test-results/`).

### Test results

`make test` and `make integration` also write their results under the gitignored
`test-results/` directory, which each run replaces for its lane, and `make verify`
writes an aggregate of them (see [Verification summary](#verification-summary)):

| Path | Written by | Content |
|------|------------|---------|
| `test-results/test/junit.xml`, `coverage.xml`, `summary.json` | `make test` | pytest JUnit XML, the Cobertura coverage report (the root `coverage.xml` is a copy for Codecov) and the summary |
| `test-results/integration/junit.xml`, `summary.json`, `environment.json` | `make integration` | JUnit XML, the summary, and the Python, package and CUBRID versions, platform and command (credentials in it masked, see below) |
| `test-results/integration/logs/cubrid.log` | `make integration`, on a failure only | the service log |
| `test-results/verify/summary.json`, `junit/<lane>.xml`, `environment.json` | `make verify`, always | the aggregate summary and masked copies of the lanes' JUnit files and the live `environment.json` |

`scripts/report_results.py` writes `summary.json` (`schema_version`, `status`,
`counts` and, for `make test`, `coverage`) and each command ends with a one-line
summary of the same status and counts, for example
`test: PASS selected=1665 passed=1665 ... coverage=99.31% -> test-results/test/summary.json`.
The status is `PASS`, `FAIL` (a failed or errored test, or a non-zero exit status such
as a missed coverage floor) or `INCOMPLETE` (no JUnit file, nothing collected, or no
test passed because every selected test skipped); `INCOMPLETE` is never `PASS`. The
exit status of both commands is unchanged. `xpassed` is always 0 because JUnit XML
cannot distinguish an unexpected pass from a pass.

`environment.json` is never built from the process environment, so an exported
`CUBRID_PASSWORD` cannot reach it, but its `command` is the `--pytest` value of
`make integration` (`PYTEST=...`) or the `--command` of `report_results.py environment`.
Before writing it, `report_results.py` masks credentials embedded in that string: a URL
password (`cubrid://dba:***@host`) and the value of a `password`, `passwd`, `pwd`,
`token`, `secret`, `api_key` or `apikey` assignment or option (`PASSWORD=***`,
`CUBRID_PASSWORD=***`, `--password=***`, `--password ***`); everything else is kept as
given. This is a best-effort safety net, not a parser (a short option such as
`-p secret` is not recognized; the module docstring lists the limits), and the command
line is still visible to other processes, so supply secrets through environment
variables or the CI secret store, never on the command line.

CI publishes the same results on every run of `make test` (the `lint-and-test` job of
`ci.yml`) and `make integration` (`ci.yml` and `integration-full.yml`), pass or fail:
the one-line summary is appended to the run's job summary
(`scripts/report_results.py step-summary`), and the whole `test-results/` tree is
uploaded as the `test-results-test-py<python>`,
`test-results-integration-cubrid<cubrid>` or
`test-results-integration-py<python>-cubrid<cubrid>` artifact, kept for 7 days. This adds
no permissions: the workflows keep `contents: read` and the artifacts are readable by
anyone who can read the run.

#### Verification summary

`make verify` runs `scripts/run_verify.py`, which runs `make check`, `make test` and
`make integration` one after another, stops at the first failing phase and then always
writes `test-results/verify/` (after removing the previous `verify`, `test` and
`integration` results), also after a failure or a signal:

- `summary.json`: `schema_version`, `lane` (`verify`), the overall `status` and one
  entry per phase (`check`, `test`, `integration`) with its `status`, `exit_code`, the
  lane's own `summary` path and `summary_status`, and a list of `problems`. A phase is
  `PASS` only when it exited 0 and its lane summary says `PASS`, and `NOT_RUN` (exit
  code `null`) when it never started. The overall status is `FAIL` when a phase failed,
  `INCOMPLETE` when a phase did not run, a live lane proved nothing (every test
  skipped), a lane summary is missing, unreadable or has no string status, or a result
  file could not be copied, and `PASS` only otherwise.
- `junit/test.xml`, `junit/integration.xml`: copies of the JUnit files of the lanes
  that ran this time.
- `environment.json`: a copy of the live lane's `environment.json`.

Every copy has the configured connection passwords (`CUBRID_PASSWORD` and the
`CUBRID_<NAME>_PASSWORD` of each connection in `CUBRID_CONNECTIONS`, as the server reads
them, also percent-encoded and XML-escaped) replaced with `***`. The run ends with one
line that matches `summary.json`, for example
`verify: FAIL check=PASS test=FAIL integration=NOT_RUN [integration did not run] -> test-results/verify/summary.json`.
The exit status is the first failing phase's, 1 when every phase exited 0 but the
summary is not `PASS`, or 128 + the signal number: the first SIGINT, SIGTERM or SIGHUP
is forwarded to the running phase (the live lane still removes its Compose project),
no further phase starts and the summary is still written. `make -n verify` writes
nothing.

### Running the Integration Suite

`make integration` needs only Docker (with the Compose plugin). It starts the
`cubrid` service of the root `docker-compose.yml`, the same definition
`make docker-up` uses (`cubrid/cubrid:<CUBRID_VERSION>`, 11.4 by default, with
`demodb`), as a Compose project of its own named `cubrid-mcp-it-<random id>`,
publishes the broker on `127.0.0.1:<CUBRID_TEST_PORT>` (33000 by default) and
waits until the service's health check passes (`up --detach --wait`). It then runs
`pytest -m integration -v` against it and always takes that project down with
`down --volumes`, removing its container, network and volumes, on success,
failure, a readiness failure, Ctrl-C or a signal (SIGINT/SIGTERM/SIGHUP). On a failure it prints
the service log first. The exit status is the first failing step's (128 + the
signal number after a signal); a cleanup failure fails an otherwise successful
run. CI's live jobs run the same target with the matrix version:

```bash
make integration                                            # CUBRID 11.4 on port 33000
make integration CUBRID_VERSION=11.2 CUBRID_TEST_PORT=33524  # another version or a free port
```

`CUBRID_TEST_PORT` is the one port variable of `make integration` and
`make docker-up`. `INTEGRATION_PORT`, its older name for `make integration`, still
works and wins when set (`make integration INTEGRATION_PORT=33524`).

The test endpoint is pinned to `127.0.0.1:<port>/demodb` as `dba`, so exported
`CUBRID_*` variables cannot redirect the run, and the project name is passed
explicitly, so `COMPOSE_PROJECT_NAME` cannot either. Because every run has its own
project, two runs on different ports do not interfere, and a running
`make docker-up` lab (the default or your `COMPOSE_PROJECT_NAME` project) is never
stopped or emptied; only the host port has to differ. No other container, image or
volume is touched.

To run the suite against a CUBRID you manage yourself (with `demodb`), point the
tests at it and use `make integration-local`:

```bash
export CUBRID_HOST=localhost
export CUBRID_PORT=33000
export CUBRID_USER=dba
export CUBRID_PASSWORD=""
export CUBRID_DATABASE=demodb
make integration-local
```

### A Persistent Local CUBRID (Docker Compose)

For manual work (trying the server from an MCP client, exploring the catalog,
running `make integration-local` repeatedly), the root `docker-compose.yml`
defines one service, `cubrid`: `cubrid/cubrid:<CUBRID_VERSION>` (11.4 by default)
with `demodb`, its broker published only on `127.0.0.1:<CUBRID_TEST_PORT>`
(33000 by default) and its data in named volumes (both the 11.4 and the pre-11.4 database paths). The health check runs
`csql -u dba demodb -c 'SELECT 1;'` inside the container.

```bash
make docker-up                                             # start it and wait until healthy
make docker-up CUBRID_VERSION=11.2 CUBRID_TEST_PORT=33400  # another version or a free port
make docker-down                                           # remove the container and network; keep the data
make docker-clean                                          # also delete the data volume (and demodb)
```

`make docker-down` keeps the volume, so the next `make docker-up` opens the same
`demodb` with your tables in it; `make docker-clean` is the one target that
deletes it. The service has no fixed container name: Docker Compose names the
container, network and volume after the project (by default the checkout's
directory name), so set `COMPOSE_PROJECT_NAME` to keep two checkouts apart, and
use the same value for `docker-down` and `docker-clean`. Point the tests at it
with `make integration-local`:

```bash
make docker-up
export CUBRID_HOST=127.0.0.1 CUBRID_PORT=33000 CUBRID_USER=dba CUBRID_PASSWORD="" CUBRID_DATABASE=demodb
make integration-local
```

`make integration` and CI start this same service, but as a separate,
run-owned Compose project that they always remove, so they never touch your
Compose data; a running Compose service only matters to them if both use the same
host port (pick another `CUBRID_TEST_PORT` for one of them).

## What CI Enforces

CI is tiered (#223): every PR gets fast required feedback, and the expensive
compatibility evidence runs where it adds value. The `classify` job in
`.github/workflows/ci.yml` turns the event and the changed paths into explicit
scopes ([`scripts/ci_scope.py`](scripts/ci_scope.py)), and only the selected
lanes run:

| Change | Unit lane (ruff, mypy, pytest + coverage) | `lowest-direct` | Live CUBRID integration |
|---|---|---|---|
| Docs/metadata only (`*.md`, `docs/` except `docs/overrides/`, `LICENSE`, `NOTICE`, `llms.txt`) | — | — | — |
| Tooling (`scripts/`, `Makefile`, `codecov.yml`, `.gitignore`, `.mcpb/`, `glama.json`, `.github/dependabot.yml`, `docs-tools/`, issue templates, `demos/`, the site template `docs/overrides/`, `mkdocs.yml` and `agent-evals/`) | Python 3.12 | — | — |
| Runtime or tests (`cubrid_mcp_server/`, `tests/`) | Python 3.12 | — | CUBRID 11.4 |
| Connection / catalog SQL (`database.py`, `context.py`, `tests/conftest.py`, `tests/test_integration.py`) | Python 3.12 | — | CUBRID 11.2 + 11.4 |
| Other workflows (`.github/workflows/*` except `ci.yml`, see the impact table below) | Python 3.12 | — | — |
| Dependency metadata (`pyproject.toml`) | Python 3.11, 3.12, 3.14 | yes | CUBRID 11.2 + 11.4 |
| CI policy (`ci.yml`, `scripts/ci_scope.py`, `tests/test_ci_scope.py`) | Python 3.11, 3.12, 3.14 | yes | CUBRID 11.2 + 11.4 |
| Push to `main` (#417) | Python 3.11, 3.12, 3.14 | yes | CUBRID 11.4 |
| Any other path (fail-closed) | Python 3.12 | — | CUBRID 11.4 |

Workflow edits are routed by which lane can actually detect a problem in the
edited file (#232). `ci.yml`'s live `integration` job only runs the pytest live
suite against CUBRID; it never executes another workflow, so it cannot validate any
workflow other than `ci.yml`. The unit lane (`pytest -m "not integration"`) runs the
workflow-contract tests, and `tests/test_workflow_path_impact.py` fails if any test
module that reads a workflow file (by literal path, split path or constant) carries
the `integration` marker.

| Workflow | Validated by | Lanes selected on a PR that edits only this file |
|---|---|---|
| `ci.yml` | Itself (it is the policy and defines every lane); `test_ci_scope.py`, `test_ci_policy.py`, `test_workflow_installs.py`, `test_workflow_timeouts.py` | Full tier: unit (3.11, 3.12, 3.14), `lowest-direct`, live CUBRID 11.2 + 11.4 |
| `codeql.yml` | Runs itself on the PR; `test_ci_policy.py`, `test_workflow_timeouts.py` | Unit (3.12) |
| `dependabot-auto-merge.yml` | `test_workflow_timeouts.py` (and the other all-workflow scans) | Unit (3.12) |
| `docs-sync.yml` | Runs itself on the PR; the all-workflow scans | Unit (3.12) |
| `docs.yml` | `test_ci_policy.py`; builds docs on PRs touching docs paths | Unit (3.12) |
| `integration-full.yml` | `test_ci_scope.py`, `test_latest_server.py`, `test_release_workflows.py`, `test_workflow_installs.py`, `test_workflow_timeouts.py`, plus a **manual `workflow_dispatch` on the PR head, linked from the PR** (not automated; the release gate depends on it) | Unit (3.12) |
| `pr-title.yml` | Runs itself on the PR; `test_pr_title.py` | Unit (3.12) |
| `release-please.yml` | `test_release_workflows.py`, `test_release_please_config.py`, `test_workflow_timeouts.py` | Unit (3.12) |
| `publish-pypi.yml` | `test_release_workflows.py`, `test_pypi_duplicate_guard.py`, `test_prepare_release.py`, `test_workflow_timeouts.py` | Unit (3.12) |
| `upstream-canary.yml` | The all-workflow scans (`test_ci_policy.py`, `test_workflow_timeouts.py`), plus a **manual `workflow_dispatch` on the PR head, linked from the PR** | Unit (3.12) |

If the same PR also edits `pyproject.toml`, `lowest-direct` and the endpoint lanes
are added by that row, not by the workflow edit.

A PR takes the union of the rows its files match. `changelog-lint` runs on every
PR. The final `ci-gate` job is the one required check: it fails unless
`classify` and `changelog-lint` succeeded and every lane that `classify`
selected succeeded. A failed, cancelled or unexpectedly skipped lane, or a
failed classification, fails the gate; a lane may be skipped only when the
classification explicitly says it does not apply.

`ci.yml` and `codeql.yml` share a `concurrency` group per workflow and ref, and
only `pull_request` runs are cancelled: a newer push to a PR supersedes its older
run, while `main`, release and scheduled runs each get their own group and are
never cancelled. A cancelled superseded run cannot weaken the gate; the new run
reports the required `ci-gate` for the PR head.

The documentation build tools (`mkdocs`, `mkdocs-material`, `pymdown-extensions`)
are pinned in `docs-tools/requirements.txt`, installed by `docs.yml`, and updated
by Dependabot. `docs.yml` also runs `mkdocs build --strict` (build only, no
deploy, read-only permissions) on pull requests touching `docs-tools/`,
`mkdocs.yml` or `docs/`. Dependabot groups dev tools (`pytest*`, `pre-commit`,
`tox`, `build`, `twine`) and GitHub Actions minor/patch updates into one PR
each; the exact-pinned `ruff` and `mypy` each get their own group so a breaking
minor release of one never blocks the others; major updates and the runtime dependencies (`fastmcp`,
`pycubrid`, `sqlparse`) stay as separate PRs.

Every Python job in `ci.yml` and `integration-full.yml` installs with a pinned
uv instead of pip (#229): `astral-sh/setup-uv` (pinned to a commit SHA, with
`version` pinned) runs after `actions/setup-python` with the same
`python-version`, caches per job (`cache-suffix: ${{ github.job }}`, keyed on
`pyproject.toml`), installs with `uv pip install --system -e . --group dev` and logs the resolved
versions with `uv pip freeze --system`. uv resolves the same package set as pip
from the same `pyproject.toml` constraints; only the installer changes. The
release smoke venvs, the docs build and the upstream canary keep plain pip.
`tests/test_workflow_installs.py` pins this setup.

The lanes check:

- **`make lint`** (`ruff check .`) — linting.
- **`make format-check`** (`ruff format --check .`) — formatting (run `make format` to fix).
- **`make typecheck`** (`mypy` in strict mode) — type checking of `cubrid_mcp_server/`.
- **`make test`** (pytest with a 95% coverage floor) — `fail_under = 95` in
  `pyproject.toml`. This is the gate that most often fails a PR; add tests for new
  code paths. Only the Codecov upload of `coverage.xml` is CI-specific.
- **`lowest-direct` job** — reinstalls with the lowest allowed direct
  dependency versions (`uv pip install --resolution lowest-direct`) and re-runs
  the unit tests, catching accidental use of newer-than-declared APIs. It runs
  `pytest -m "not integration"` without coverage on purpose: it checks dependency
  floors, not the coverage gate, so it is a weaker lane than `make test`, not a
  replacement for it.
- **`integration`** — `make integration CUBRID_VERSION=<matrix version>`: a
  run-owned Compose project of the `docker-compose.yml` service, `pytest -m
  integration`, the service log on a failure and guaranteed `down --volumes`. `integration-full.yml` runs the same
  target for each matrix cell.
- **`python scripts/lint_changelog.py`** — checks `CHANGELOG.md` structure and
  version ordering. In `[Unreleased]` and in releases after 0.4.0 it also
  rejects a repeated `###` heading within one version and requires the standard
  `###` sections, each with content, in this order: Upgrade notes, Added, Changed,
  Deprecated, Removed, Fixed, Security, Performance, Documentation, CI, Tests.
  Releases up to 0.4.0 keep their historical headings, duplicates included.

Every executing job sets an integer `timeout-minutes` instead of GitHub's
360-minute default (#228): 2–5 minutes for gates and small jobs, 10–15 for
docs/release helpers, live lanes, `lowest-direct` and the upstream canaries, and 30
for the unit lane (observed maximum 8.6).
Jobs that call a reusable workflow cannot set a timeout; the repo-local callee
(`publish-pypi.yml` → `integration-full.yml`) is covered through its own jobs, and the
externally owned callees (the org CodeQL workflow and the cookbook smoke test) are
an explicit allowlist. `tests/test_workflow_timeouts.py` parses every workflow and
fails when an executing job lacks a bounded timeout, when a new external caller is
not allowlisted, or when a gate (`ci-gate`, `full-matrix-result`) loses
`if: always()` or its short timeout; it also runs the `full-matrix-result` script and
requires it to fail on any non-success planning or matrix result.

The full Python {3.11–3.14} × CUBRID {10.2, 11.0, 11.2, 11.4} matrix lives in
`.github/workflows/integration-full.yml`. It runs weekly (Sunday 03:00 UTC), on
manual dispatch (`scope` = `full` (default) or `corners`, Python 3.11 × CUBRID 10.2
and Python 3.14 × CUBRID 11.4), and always in full as the release gate
(`publish-pypi.yml` calls it at the release commit; a release run that is not full
or not fully green blocks publication). The advisory upstream canaries
(`upstream-canary.yml`, pycubrid@main and latest FastMCP) run weekly on Monday.

Which CUBRID versions run on which event (#417):

| Event | Live CUBRID |
|---|---|
| Ordinary PR | 11.4 for runtime/test changes; 11.2 + 11.4 for the connection/catalog, dependency and CI-policy paths above; none for docs-only |
| Push to `main` | 11.4 only, with the Python 3.11/3.12/3.14 unit lanes and `lowest-direct` |
| Weekly schedule (Sunday) | The full 4 × 4 matrix, plus the advisory newest-image check below |
| Manual `integration-full.yml` dispatch | The full 4 × 4 matrix (or the two corners when asked), plus the newest-image check |
| Release (`workflow_call` from `publish-pypi.yml`) | The full 4 × 4 matrix, fail-closed; never the advisory check |

So a push to `main` is representative 11.4 evidence; every-version evidence comes
from the PR lanes its paths selected, the weekly run and the release gate. Until
#417 a push also ran 11.2, and a Monday–Saturday schedule ran the two corner cells;
those 15 corner runs (2026-10-08 to 2026-10-24) all passed and their cells are in
every weekly and release run, so the daily schedule was removed rather than kept.
Measured on GitHub Actions before the change (median of the last 10 successful
`main` pushes; billed minutes round each job up): the `integration (11.2)` job of a
push took 55 s (1 billed minute) and there were 49 pushes to `main` from
2026-10-18 to 2026-10-25; the six weekday corner runs of 2026-10-19 to 2026-10-24
started 12 live cells, 9.5 job-minutes and 24 billed minutes in all.

Each matrix cell records the image it ran (`Record CUBRID image`: the
`cubrid/cubrid@sha256:…` digest and its `cubrid_rel` engine version) in its step
summary. The advisory `Newest CUBRID image (advisory)` job (`latest-server`,
[`scripts/latest_server.py`](scripts/latest_server.py), weekly and on manual
dispatch only, `continue-on-error`, never a need of the matrix result) pulls
`cubrid/cubrid:latest` and `cubrid/cubrid:11.4` once and compares their digests and
engine builds:

- same digest: no extra database starts; the summary names that digest, and the
  11.4 cells tested the newest-stable image only if their recorded digest matches;
- a different digest that is not a newer engine build: nothing more runs;
- a newer engine build (for example a future 11.5): a focused advisory canary runs
  `make integration` on that immutable digest. A failure is shown on the run but
  blocks nothing, and the image is never added to the supported versions or the
  release matrix automatically;
- a failed or malformed pull or lookup: reported as UNVERIFIED with a warning,
  never as passed.

## Main branch protection

Every change reaches `main` through a pull request. The maintainers apply this
baseline to `main` (the default branch) in the repository settings; it is not
stored in the repository, so a change to it is a maintainer decision recorded on
an issue, not a pull request:

- **No deletion** of `main`.
- **No force push** (non-fast-forward updates are rejected).
- **Pull request required.** Direct pushes to `main` are rejected. Merges are
  squash merges, so the pull request title becomes the commit title.
- **Required checks:** `ci-gate` (the aggregate gate described above) and
  `PR title` (from `pr-title.yml`). The branch must be up to date with `main`
  before merging. The advisory `agent-review` check (see
  [Agent-review evidence gate](#agent-review-evidence-gate)) runs on every pull
  request. It must not be made a required check while a pull request can
  publish a check with the same name.
- **No required human approval and no required code-owner approval.** The
  project has a small maintainer team. A mandatory approval would block a
  maintainer's own pull request whenever the other maintainers are away, and
  Dependabot updates would wait for a human approval instead of merging
  automatically once the required checks pass.
  `.github/CODEOWNERS` only routes review requests. Review expectations for
  maintainer and agent pull requests are in
  [Agent-authored PR review requirements](#agent-authored-pr-review-requirements).
- **No bypass actor.** The rules also apply to administrators. No workflow pushes
  to `main`: `release-please.yml` pushes only to its `release-please--branches--main`
  branch and opens a pull request, `publish-pypi.yml` creates only `v*` tags and the
  GitHub Release, and `dependabot-auto-merge.yml` merges through the pull request
  with the same required checks.

Renaming the `ci-gate` job or the `PR title` job changes the check name and
blocks every merge until the required checks are updated in the settings; change
both together.

## Documentation structure

The documentation site (`mkdocs.yml`, `docs/`) has one page per reader question.
The navigation groups pages by reader: **Start here** (one learning route), **How-to
guides** (a goal after the first route), **Reference** (exact tools, settings and
security limits), **Help** (troubleshooting and reporting) and a peer **한국어** tab
with the same groups. Every English page links its Korean page right below its title,
and every Korean page links the English page below its translation note.

| Source, site URL | Reader and question | Group | Before / after it | Owner of the content |
|---|---|---|---|---|
| `docs/index.md`, `/` | Anyone: what is this and where do I start? | Home | — / Quick Start | Navigation (#354) |
| `README.md` (GitHub and PyPI only) | A visitor: what is this project, and how is it configured? | Not in the site; the Reference group links its `#configure` section | — / Quick Start | Unchanged |
| `docs/quickstart.md`, `/quickstart/` | Newcomer: how do I prepare a lab and an account, register one client, see the tools, query, and clean up? | Start here | — / Tools reference | Steps, accounts and results: #352. Location and links: #354 |
| `docs/MULTI_CONNECTION.md`, `/MULTI_CONNECTION/` | User: how do I serve several databases from one process? | How-to guides, "Serve several databases" | Quick Start / Tools reference | Unchanged content |
| `docs/TOOLS.md`, `/TOOLS/` | User: what exactly does each tool, resource and prompt take and return? | Reference | Any page | Unchanged content (kept in sync by `tests/test_docs_alignment.py`) |
| `docs/SECURITY_MODEL.md`, `/SECURITY_MODEL/` | User or reviewer: what do the read-only checks protect, and what not? | Reference | Any page | Unchanged content; the Quick Start keeps its own least-privilege and data-exposure warnings |
| `docs/TROUBLESHOOTING.md`, `/TROUBLESHOOTING/` | User with a problem: what does this symptom mean? | Help | Any page / issue forms or `SECURITY.md` | Unchanged content |
| `docs/README.ko.md`, `docs/ko/*.md`, `/ko/...` | Korean reader: the same questions | 한국어 tab, same groups (moved from Project → Translations) | Same as English | Translators; the existing warning-level sync rule |

No file is renamed, so every existing page URL and heading anchor stays. The chat-client
configurations stay at the end of the Quick Start
(`/quickstart/#optional-use-the-same-server-from-a-chat-client`).

### Writing a walkthrough step

Give each step of a learning route these parts, in this order: the goal; what earlier
steps must have produced (never an open Python session); the exact file or
configuration and the command; the actual output from a recorded run; a short
explanation of what the output proves (process started, MCP tools discovered, database
query succeeded are three different checkpoints); and the next step. Keep alternatives,
optional clients and exhaustive settings out of the main route and link them instead.
Use the sample names of the Quick Start (`testdb`, `dba.mcp_quickstart_books`,
`mcp_reader`) everywhere. Keep the least-privilege and data-exposure warning that applies
to a step beside that step. When a step's command or output changes, run the route again
and record the platform and versions it ran on; a successful build or a screenshot of
tool discovery is not evidence that a query works. Preserve the original author of an
active translation fix.

## CHANGELOG

Add an entry under `## [Unreleased]` in
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) style, in the
appropriate standard group, and reference the issue or PR number — match the
format of the existing entries. The allowed `###` groups, in this order, are
Upgrade notes, Added, Changed, Deprecated, Removed, Fixed, Security, Performance,
Documentation, CI, Tests; use `Documentation`, not `Docs`, and file release
automation under `CI` or `Changed`. The GitHub Release body is the CHANGELOG
section plus one `**Full Changelog**` compare link; see the "GitHub Release
Policy" in [`AGENTS.md`](AGENTS.md). In `scripts/lint_changelog.py` a fenced
`###` line is entry content, never a heading; a fenced `## [` release header is an
error (`scripts/extract_release_notes.py` is not fence-aware and would truncate the
Release body); an unclosed fence is an error. Only fences that start at column 0
with three backticks are recognised, not tilde or indented/nested fences. A repeated
`###` heading within one version is rejected only in `[Unreleased]` and in releases
after 0.4.0: released history up to 0.4.0 is never rewritten, and different releases
may reuse the same heading names. `scripts/lint_changelog.py` is shared with pycubrid,
sqlalchemy-cubrid and the cookbook; once all four repositories adopt the rule-5
cutoff gating, only `SECTION_POLICY_CUTOFF` differs. Security
fixes use a `fix:` title plus the `security` label and go under `Security`. Do **not**
bump the version yourself; maintainers cut releases following
[`RELEASING.md`](RELEASING.md).

## Pull request review and validation

The same process applies to every contributor and every implementation tool,
including OpenCode, Codex, Claude Code, ChatGPT, Copilot and human-only work.
Local checks are encouraged but the required GitHub Actions checks on the
final PR head are authoritative. Oracle, Copilot and `agent-review` are
optional advisory reviews, not required evidence. Maintainers evaluate
behavior, correctness, security, tests and maintainability, disposition
findings and make the final merge decision.

Changes to `safety.py`, `database.py`, `audit.py`, `server.py`,
write-capable workflows or releases require a documented security/invariant
assessment and the independent maintainer review specified in `AGENTS.md`
for security-sensitive or publishing paths. This is a **human safety decision**,
not a required Oracle/Copilot/agent-review stage or a change to GitHub branch
protection settings. Existing tests, live CUBRID checks and release safeguards
remain authoritative.

### Agent-review evidence gate

The existing `agent-review` check can summarize submitted GitHub review
records using legacy tool-based classifications. It is **not a merge gate**
and its result is not an authoritative assessment of reviewer approval,
source correctness or readiness to merge. Reviewers may read useful
findings but make independent judgments; the owner/maintainer validates
required CI, security findings and final source. Do not protect this check
name as a required status: a pull request can spoof a similarly named
GitHub Actions check. First-time fork workflow approvals remain a GitHub
Actions safety control, not a contributor review requirement.

## Repository-local issue ownership

Issues own implementation and acceptance in the repository whose files change.
Provide a self-contained local problem, scope, owner, tests, and closure
decision. Sibling repositories may be cited with Refs owner/repo#N when they
supply a real dependency or compatibility contract; their priorities and
completion are not inherited. Close only this repository's issues (Closes #N).
PRs with no local issue may state N/A and a reason. The existing PR title check
rejects direct cross-repository issue-closing keywords, including emphasized or
linked ones, in the PR body, the PR title and commit messages. The title and
commit messages make up the squash commit and are read as plain text; an edit to
the squash message at merge time is not checked. In the body, the check ignores
fenced and indented code blocks and HTML comment blocks only where it can follow
the Markdown exactly, so anything uncertain is checked: code and comment blocks
inside list items, footnotes and block quotes are always checked; after a fence
it cannot track (in a list item, block quote or raw HTML, on an indented line,
or as a line that only looks like a fence), later fences and comments are
checked; after anything that may start an HTML tag, even in prose or inline
code, later comments are checked; and after a raw-text element name such as
`<textarea>` or `<select>`, nothing is ignored. Inline code and inline comments
are always checked. External contributors do not need to install internal agent
tools or create duplicate work.

### Good first issues and contribution claims

An unassigned `good first issue` is open to **human-led contributors**, including people who direct and review AI-assisted work. They can start work and submit a PR **without prior maintainer approval, GitHub Assignee access, or internal AI tooling**.

Before beginning, check Assignees, comments and open PRs. A brief comment expressing interest is welcome but optional, not a permission gate or exclusive reservation. Coordinate before overlapping claimed work. Maintainers manage issue assignments and labels.

**Maintainer-operated autonomous agents** are distinct from human-directed AI assistance. Before implementing a newcomer-reserved `good first issue`, an agent must obtain explicit maintainer authorization for **that specific issue** and assignment of the implementer. Broad backlog/release instructions do not suffice.

Existing security invariants, tests, docs requirements and PR review/merge policies remain unchanged.

## Pull request and commit titles

This repository uses the canonical CUBRID Lab title format for its issues,
pull requests and commit subjects. Its PRs are squash-merged and the pull
request title becomes the commit title on `main`, so the PR title must be
accurate. This repository's `PR title` check enforces that format; do not
assume other repositories share identical check names or release mechanics.

```text
type: description
type(scope): description
type!: description
type(scope)!: description
```

- **type** (lowercase, exactly one of): `feat`, `fix`, `docs`, `test`, `perf`,
  `refactor`, `ci`, `build`, `chore`, `style`, `revert`.
- **scope** is optional: lowercase letters, digits, `-` or `_`, such as
  `compiler`, `aio`, `deps` or `release`.
- **`!`** before the colon marks a breaking change. Follow the repository's
  release policy for breaking changes as well.
- Exactly **one space** after the colon.
- **description**: English and specific (name the function, type or behavior
  that changed). Start with a lowercase letter unless the first word is an API
  name, acronym or proper noun. No trailing period.
- No bracket, status or priority prefixes (`[Bug]`, `[WIP]`, `Track:`,
  `epic:`, `P1`). Open a draft pull request for unfinished work; priority and
  size are labels.
- No issue or pull request numbers in the title. Put `Closes #123` or
  `Refs #123` in the pull request body. GitHub appends the pull request
  number, for example `(#456)`, to the squash commit by itself.

| Type | Use for |
|------|---------|
| `feat` | A new user-facing capability |
| `fix` | Corrects wrong behavior, including security fixes |
| `docs` | Documentation only |
| `test` | Tests only |
| `perf` | Faster or lighter with no behavior change |
| `refactor` | Restructuring with no behavior change |
| `ci` | CI workflows and their configuration |
| `build` | Packaging and the build system |
| `chore` | Maintenance: releases, dependency bumps, housekeeping |
| `style` | Formatting only |
| `revert` | Reverts an earlier change; name it in the description |

Examples:

```text
fix(protocol): keep the CAS session after OUT_TRAN
feat(aio): add a charset connection option
docs: document JSON as_numeric() input limits
chore(deps): bump ruff from 0.16.8 to 0.16.9
chore: release v1.9.0
refactor(compiler)!: drop legacy LIMIT rendering
```

Issue forms prefill a type prefix; keep it and write the rest of the title the
same way. A tracking issue (epic) uses the type of the work it tracks.

Maintainers merge with **squash merge only** and keep the pull request title as
the commit title. Branch commits are squashed into the commit body, so keep
their messages meaningful and keep any `Co-authored-by:` trailers intact.

## Releases

Contributors never release. Add user-visible changes under `## [Unreleased]` in
`CHANGELOG.md`, and do not change `__version__`, the `.mcpb/server.json`
versions or add a dated `## [X.Y.Z]` section in an ordinary PR: a merged
version change is what starts an automatic release. Maintainers use the PR-only
`release-please.yml` generator; curated Unreleased and Upgrade notes remain
reviewed in CHANGELOG. Freeze the candidate with `autorelease: review` before
editing its notes, and start CI at the final bot-updated head; see
[`RELEASING.md`](RELEASING.md). Before merging a release PR, maintainers complete its
[release review checklist](RELEASING.md#release-review-checklist).

## A Note on stdout

The server speaks the MCP **stdio transport**, so `stdout` carries the JSON-RPC
protocol stream. **All logging must go to `stderr`** — never `print()` to
`stdout`, or you will corrupt the protocol stream. Use the standard `logging`
module (already configured to emit on `stderr`) instead.
