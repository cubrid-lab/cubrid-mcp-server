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
- Git
- Docker (only needed for the integration tests)

## Development Setup

```bash
git clone https://github.com/cubrid-lab/cubrid-mcp-server.git
cd cubrid-mcp-server
python3 -m venv .venv && source .venv/bin/activate

# Editable install with dev extras (ruff, mypy, pytest, ...)
make install
```

`make install` runs `pip install -e ".[dev]"`.

## Local Checks Before Pushing

Run these before opening a PR — they mirror what CI runs, so passing them
locally is the fastest way to avoid a red build:

```bash
make lint        # ruff check
make format      # ruff format + ruff check --fix
make typecheck   # mypy (strict) on cubrid_mcp_server/
make check       # lint + typecheck in one go (no tests)
```

## Tests

```bash
make test         # unit tests only (pytest -m "not integration")
make integration  # integration tests — requires a live CUBRID (see below)
```

### Running the Integration Suite

The integration tests need a running CUBRID with the `demodb` database. CI
starts `cubrid/cubrid:<version>` (11.4 by default, see the tiers below) in
Docker and waits for `demodb` to be ready; you can do the same locally, then
point the tests at it:

```bash
export CUBRID_HOST=localhost
export CUBRID_USER=dba
export CUBRID_PASSWORD=""
export CUBRID_DATABASE=demodb
make integration
```

## What CI Enforces

CI is tiered (#223): every PR gets fast required feedback, and the expensive
compatibility evidence runs where it adds value. The `classify` job in
`.github/workflows/ci.yml` turns the event and the changed paths into explicit
scopes ([`scripts/ci_scope.py`](scripts/ci_scope.py)), and only the selected
lanes run:

| Change | Unit lane (ruff, mypy, pytest + coverage) | `lowest-direct` | Live CUBRID integration |
|---|---|---|---|
| Docs/metadata only (`*.md`, `docs/`, `LICENSE`, `NOTICE`, `llms.txt`, `mkdocs.yml`) | — | — | — |
| Tooling (`scripts/`, `Makefile`, `codecov.yml`, `.gitignore`, `.mcpb/`, `glama.json`, `.github/dependabot.yml`, `docs-tools/`, issue templates, `demos/`) | Python 3.12 | — | — |
| Runtime or tests (`cubrid_mcp_server/`, `tests/`) | Python 3.12 | — | CUBRID 11.4 |
| Connection / catalog SQL (`database.py`, `context.py`, `tests/conftest.py`, `tests/test_integration.py`) | Python 3.12 | — | CUBRID 11.2 + 11.4 |
| Other workflows (`.github/workflows/*` except `ci.yml`, see the impact table below) | Python 3.12 | — | — |
| Dependency metadata (`pyproject.toml`) | Python 3.11, 3.12, 3.14 | yes | CUBRID 11.2 + 11.4 |
| CI policy (`ci.yml`, `scripts/ci_scope.py`, `tests/test_ci_scope.py`), push to `main`, manual dispatch | Python 3.11, 3.12, 3.14 | yes | CUBRID 11.2 + 11.4 |
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
| `ci.yml` | Itself (it is the policy and defines every lane); `test_ci_scope.py`, `test_ci_policy.py`, `test_workflow_timeouts.py` | Full tier: unit (3.11, 3.12, 3.14), `lowest-direct`, live CUBRID 11.2 + 11.4 |
| `codeql.yml` | Runs itself on the PR; `test_ci_policy.py`, `test_workflow_timeouts.py` | Unit (3.12) |
| `dependabot-auto-merge.yml` | `test_workflow_timeouts.py` (and the other all-workflow scans) | Unit (3.12) |
| `docs-sync.yml` | Runs itself on the PR; the all-workflow scans | Unit (3.12) |
| `docs.yml` | `test_ci_policy.py`; builds docs on PRs touching docs paths | Unit (3.12) |
| `integration-full.yml` | `test_ci_scope.py`, `test_release_workflows.py`, `test_workflow_timeouts.py`, plus a **manual `workflow_dispatch` on the PR head, linked from the PR** (not automated; the release gate depends on it) | Unit (3.12) |
| `pr-title.yml` | Runs itself on the PR; `test_pr_title.py` | Unit (3.12) |
| `release-please.yml` | `test_release_workflows.py`, `test_release_please_config.py`, `test_workflow_timeouts.py` | Unit (3.12) |
| `release.yml` | `test_release_workflows.py`, `test_pypi_duplicate_guard.py`, `test_prepare_release.py`, `test_workflow_timeouts.py` | Unit (3.12) |
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

The lanes check:

- **`ruff check .`** — linting.
- **`ruff format --check .`** — formatting (run `make format` to fix).
- **`mypy` in strict mode** — type checking of `cubrid_mcp_server/`.
- **Pytest with a 95% coverage floor** — `fail_under = 95` in `pyproject.toml`.
  This is the gate that most often fails a PR; add tests for new code paths.
- **`lowest-direct` job** — reinstalls with the lowest allowed direct
  dependency versions (`uv pip install --resolution lowest-direct`) and re-runs
  the unit tests, catching accidental use of newer-than-declared APIs.
- **`integration`** — `pytest -m integration` against a live CUBRID container.
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
(`release.yml` → `integration-full.yml`) is covered through its own jobs, and the
externally owned callees (the org CodeQL workflow and the cookbook smoke test) are
an explicit allowlist. `tests/test_workflow_timeouts.py` parses every workflow and
fails when an executing job lacks a bounded timeout, when a new external caller is
not allowlisted, or when a gate (`ci-gate`, `full-matrix-result`) loses
`if: always()` or its short timeout; it also runs the `full-matrix-result` script and
requires it to fail on any non-success planning or matrix result.

The full Python {3.11–3.14} × CUBRID {10.2, 11.0, 11.2, 11.4} matrix lives in
`.github/workflows/integration-full.yml`. It runs weekly (Sunday 03:00 UTC), on
manual dispatch (`scope` = `full` or `corners`), and always in full as the
release gate (`release.yml` calls it at the release commit; a release run that
is not full or not fully green blocks publication). Monday–Saturday it runs only
the corners — Python 3.11 × CUBRID 10.2 and Python 3.14 × CUBRID 11.4 — to
catch compatibility drift between weekly runs. The advisory upstream canaries
(`upstream-canary.yml`, pycubrid@main and latest FastMCP) run weekly on Monday.

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

## Pull request and commit titles

This rule covers issue titles, pull request titles and commit subjects in every
cubrid-lab repository. Pull requests are squash-merged and the pull request
title becomes the commit title on `main`, so the pull request title is the one
that must be right. The `PR title` check enforces it.

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
[`RELEASING.md`](RELEASING.md).

## A Note on stdout

The server speaks the MCP **stdio transport**, so `stdout` carries the JSON-RPC
protocol stream. **All logging must go to `stderr`** — never `print()` to
`stdout`, or you will corrupt the protocol stream. Use the standard `logging`
module (already configured to emit on `stderr`) instead.
