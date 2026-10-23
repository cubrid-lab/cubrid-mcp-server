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

`make install` runs `pip install -e ".[dev]"`. `make doctor` then checks that
Python 3.11+, `ruff`, `mypy`, `pytest`, `pytest-cov` and `pytest-asyncio` are
available; it exits non-zero, without a success line, if any is missing. Docker
is reported but optional (only `make integration` needs it). `make help` lists
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
make verify             # make check + make test; no Docker, no database
make integration        # integration tests on a Docker CUBRID it starts and removes
make integration-local  # integration tests against a CUBRID you already run
```

`make test` runs `pytest -m "not integration"` with `--cov=cubrid_mcp_server`,
so the `fail_under = 95` floor in `pyproject.toml` is enforced locally exactly as
in CI. It writes `coverage.xml` (CI uploads that file to Codecov); extra pytest
arguments go in `PYTEST_ARGS`, for example `make test PYTEST_ARGS="-k config -x"`.
`make clean` removes only generated, gitignored artifacts (build output, caches,
`.coverage`, `coverage.xml`, `htmlcov/`).

### Running the Integration Suite

`make integration` needs only Docker. It starts its own uniquely named
`cubrid/cubrid:<CUBRID_VERSION>` container (11.4 by default) with `demodb`,
publishes the broker on host port `INTEGRATION_PORT` (33000 by default), waits
for `demodb` to answer, runs `pytest -m integration -v` against it and then
always removes that container and its anonymous volumes, on success, failure or
Ctrl-C (SIGINT/SIGTERM). On a failure it prints the container log first. The
exit status is the first failing step's; a cleanup failure fails an otherwise
successful run. CI's live jobs run the same target with the matrix version:

```bash
make integration                                            # CUBRID 11.4 on port 33000
make integration CUBRID_VERSION=11.2 INTEGRATION_PORT=33524  # another version or a free port
```

The test endpoint is pinned to `127.0.0.1:$INTEGRATION_PORT/demodb` as `dba`, so
exported `CUBRID_*` variables cannot redirect the run. No other container, image
or named volume is touched.

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
| `ci.yml` | Itself (it is the policy and defines every lane); `test_ci_scope.py`, `test_ci_policy.py`, `test_workflow_installs.py`, `test_workflow_timeouts.py` | Full tier: unit (3.11, 3.12, 3.14), `lowest-direct`, live CUBRID 11.2 + 11.4 |
| `codeql.yml` | Runs itself on the PR; `test_ci_policy.py`, `test_workflow_timeouts.py` | Unit (3.12) |
| `dependabot-auto-merge.yml` | `test_workflow_timeouts.py` (and the other all-workflow scans) | Unit (3.12) |
| `docs-sync.yml` | Runs itself on the PR; the all-workflow scans | Unit (3.12) |
| `docs.yml` | `test_ci_policy.py`; builds docs on PRs touching docs paths | Unit (3.12) |
| `integration-full.yml` | `test_ci_scope.py`, `test_release_workflows.py`, `test_workflow_installs.py`, `test_workflow_timeouts.py`, plus a **manual `workflow_dispatch` on the PR head, linked from the PR** (not automated; the release gate depends on it) | Unit (3.12) |
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
`pyproject.toml`), installs with `uv pip install --system` and logs the resolved
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
  run-owned CUBRID container, `pytest -m integration`, the container log on a
  failure and guaranteed container removal. `integration-full.yml` runs the same
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
manual dispatch (`scope` = `full` or `corners`), and always in full as the
release gate (`publish-pypi.yml` calls it at the release commit; a release run that
is not full or not fully green blocks publication). Monday–Saturday it runs only
the corners — Python 3.11 × CUBRID 10.2 and Python 3.14 × CUBRID 11.4 — to
catch compatibility drift between weekly runs. The advisory upstream canaries
(`upstream-canary.yml`, pycubrid@main and latest FastMCP) run weekly on Monday.

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

## Agent-authored PR review requirements

Maintainer/agent PRs use the review route in
[AGENTS.md](AGENTS.md#development-workflow-cubrid-lab-org-standard).
Non-trivial OpenCode work records Oracle design and post-implementation reviews;
trivial OpenCode changes may omit those reviews with a recorded reason.
Standalone Claude Code, Codex, ChatGPT or other agent tools wait for a substantive
submitted GitHub Copilot review or a review by a maintainer (a code owner other
than the PR's author), recorded on the PR (maintainer decision, 2026-10-15).
Other people's reviews and other AI agents' reviews do not satisfy that route.
A pending request, CI pass, self-review or an automated approval suggestion
alone does not complete it. Under every route, changes to `safety.py`,
`database.py`, `audit.py`, `server.py` or workflows that hold write permissions
or perform releases need a review that explicitly assesses their invariants,
confirmed by a maintainer.
Record dispositions at the final relevant head and close inline threads only
after verification. Human contributions follow ordinary contributor review;
no contributor must install internal agent or Oracle tooling. Existing safety,
integration and release checks remain mandatory.

### Agent-review evidence gate

> **Advisory only. Never make `agent-review` a required status check in its
> current form.** It is a GitHub Actions check, and a pull request can publish a
> passing check with the same name: by editing `agent-review.yml` (GitHub runs
> the PR's copy of the workflow) or by adding another workflow with an
> `agent-review` job. The check cannot prove who produced it. It can become a
> required check only once its verdict is posted from an identity a pull request
> cannot impersonate. The GitHub App publisher below is that identity (#345,
> #393); until it runs and the ruleset requires the App's check, `agent-review`
> is a reading aid for the reviewer and the maintainer who merges.

#### App-owned verdict

`.github/workflows/agent-review-app.yml` posts the same verdict as an
`agent-review` check run owned by a GitHub App (decision in #345, implementation
#393). A required status check matches its context and its `integration_id`, and
a pull request's workflows can only publish as GitHub Actions (`15368`), so a
check required with the App's ID cannot be forged by a pull request.

- **Default-branch code only.** It runs on `pull_request_target`, on
  `workflow_run` when an advisory `agent-review` run completes (a review event),
  on a 15-minute `schedule` and on `workflow_dispatch`; all of them use the
  workflow file and scripts from `main`, and the pull request is re-read from
  the API, never taken from an event payload. The job checks out `main`, never the pull
  request, and `scripts/agent_review_publish.py` runs the unchanged
  `fetch`/`evaluate` of `scripts/agent_review_gate.py` and posts a completed
  check run on the head it evaluated, only while that is still the head.
  Every run shares one concurrency group, so an older evaluation is never
  posted after a newer one.
- **The schedule** picks up what sends no usable event: Copilot's review (its
  run waits for approval) and thread resolutions. A verdict whose conclusion and
  summary equal the App's latest `agent-review` run on that head is not posted
  again.
- **Credentials.** The App needs `checks: write`, `pull_requests: read` and
  `contents: read`. Its ID is the repository variable `AGENT_REVIEW_APP_ID`; its
  private key is the secret `AGENT_REVIEW_APP_KEY` of the `agent-review-app`
  environment, whose deployment-branch policy allows only `main`, so a job on a
  pull request branch cannot read it. The job is skipped until the variable is
  set, and for Dependabot events (Dependabot runs cannot read environment
  secrets; the schedule covers those pull requests).
- **Fails closed.** Missing API data for a pull request posts a failing check;
  any other API error fails the run.
- **Rollback.** Remove the App's check from the required checks, delete the
  workflow, the variable and the environment, and uninstall the App. The
  advisory workflow keeps working throughout.

Requiring the App's `agent-review` in the `main protection` ruleset is a
separate change, made only after the App posts verdicts and a pilot shows that a
forged `agent-review` job does not satisfy the App-pinned check.

#### The advisory check

`.github/workflows/agent-review.yml` publishes the `agent-review` check. It runs
`scripts/agent_review_gate.py` from the base branch and decides only from the
review records GitHub keeps for the pull request. It applies the review route
of 2026-10-15: a substantive Copilot review or a maintainer's review. The PR
body, its checkboxes and its declared development route, review requests, and CI
results are never evidence; the route is only shown in the check summary. Every
pull request is evaluated the same way, whichever tool or person wrote it, except
the two exemptions below.

A review counts only when it is submitted (not pending or dismissed), comes from
an account that still exists, is not a self-review (the reviewer is not the PR
author and authored no commit in the PR other than a merge commit that only
brings in `main`), covers the current head, and comes from GitHub Copilot code
review or a maintainer: a code owner listed in `MAINTAINERS`, which a test keeps
equal to `.github/CODEOWNERS`. Other people, other bots and other AI agents are
listed in the summary but never count.

| Evidence at the head | Ordinary change | Protected path changed |
|---|---|---|
| Maintainer, `APPROVED` | passes | passes (the explicit authorization) |
| Maintainer, `COMMENTED` that opens at least one inline thread | passes | not enough |
| Maintainer, `COMMENTED` with body text only | not enough | not enough |
| Copilot `COMMENTED`, substantive, AI round 1 or 2 | passes | not enough |
| Copilot past the AI review budget, summary-only, or error/quota notice | not enough | not enough |
| Nothing, a pending request, PR-body checkboxes, a self-review, anyone else | fails | fails |

- **COMMENTED is not APPROVED.** A maintainer's `COMMENTED` review counts as an
  assessment only when it opens an inline thread; the gate cannot judge body
  text, so a maintainer who accepts a change without comments approves it.
- **Substantive Copilot review.** It has inline comments, or its overview states
  a verdict, an assessment sentence and an open-findings count. A summary of what
  changed, or an error or quota notice, is not an assessment. A notice is not an
  AI review round, so a quota failure may be re-requested; neither is an empty
  record with no new thread, such as a reply to an existing thread.
- **Stale reviews.** A review of an older commit counts only when the PR's change
  against `main` is identical at that commit and at the head: the same files,
  statuses and exact patches, hunk line numbers included, and for a file without
  a patch (binary, too large, or a pure rename) the same blob SHA. An edit moved
  to another place never inherits a review. An "Update branch" sync, needed
  because `main` requires branches to be up to date, or a rebase that changes
  nothing of the PR carries the review forward. When `main` changed lines above
  or next to the PR's own change, the patch differs and the review is stale, and
  the merge commit's author counts as a committer: fail closed, and ask for a new
  review of the final head.
- **AI review budget.** Each published Copilot review is one round, stale or not
  (error and quota notices excepted). Rounds 1 and 2 can satisfy the gate. A
  Copilot review does not count on its own once a PR has more than two Copilot
  rounds, even an earlier round of the same head: at the budget limit the final
  head needs a maintainer's review. A carry-forward spends no round.
- **Protected paths (no bypass).** A change to `cubrid_mcp_server/safety.py`,
  `database.py`, `audit.py`, `server.py`, `config.py`, `__main__.py` or
  `context.py`, to any file under `.github/workflows/`, or to the gate itself
  (`scripts/agent_review_gate.py`, `tests/test_agent_review_gate.py`) needs a
  maintainer's `APPROVED` review of the head.
- **Blocking findings.** A maintainer whose latest decision is
  `CHANGES_REQUESTED` blocks, even one who also committed to the PR. Only threads
  opened by Copilot or a maintainer are weighed. Among them, an unresolved
  Copilot critical or high-severity finding, or a thread whose comments (replies
  included) mention security, a vulnerability, an injection, credentials,
  secrets, privileges or a bypass, blocks even when outdated, and so does such a
  thread that the PR author resolved. Resolving a thread sends no workflow
  event: re-run the `agent-review` job afterwards.
- **Missing data fails closed.** Any API error, missing field or truncated
  listing (250 or more commits, 3000 or more files, a compare of 300 or more
  files) fails the check; re-run it. A review whose account was deleted is
  ignored instead.
- **Copilot's review does not start a run by itself.** GitHub holds a workflow
  run that Copilot's review event triggers as "action required" and creates no
  check for it. After Copilot reviews, re-run that waiting `agent-review` run
  (Actions, or `gh api -X POST repos/cubrid-lab/cubrid-mcp-server/actions/runs/<id>/rerun`)
  or edit the PR body; both evaluate the current records. Each event adds
  another `agent-review` check run on the same head. GitHub does not document
  which of several same-named check runs a required check would use, which is a
  second reason the check stays advisory: read the newest run.

Exemptions, so release and dependency automation behave as before:

- **release-please candidates** (author `github-actions[bot]`, a
  `release-please--` branch in this repository) pass with a notice only when
  every changed file is one release-please writes here (`CHANGELOG.md`,
  `RELEASE_CHANGELOG.md`, `.release-please-manifest.json`, `.mcpb/server.json`,
  `cubrid_mcp_server/__init__.py`) and no protected path is touched. Otherwise
  they are evaluated like any pull request. Their review, freeze and CI rules
  stay in [`RELEASING.md`](RELEASING.md).
- **Dependabot updates** (author `dependabot[bot]`, a `dependabot/` branch in this
  repository) pass when every commit was created by Dependabot through GitHub
  (author `dependabot[bot]`, committer `web-flow`, verified signature) or is a
  merge that leaves the PR's change identical. Any other commit, an amended
  Dependabot commit included, makes the pull request an ordinary one.

Outside contributors' pull requests pass with a maintainer's review. A
maintainer's own pull request needs Copilot code review or the other maintainer.

**Fork pull requests.** The workflow uses `pull_request` and
`pull_request_review` with a read-only token, never `pull_request_target`, and
checks out nothing: no fork code runs with write access or secrets. Fork pull
requests never get an exemption and never run their own copy of the script.
`pull_request_target` would read the workflow from the base branch, but it runs
with the repository's secrets and, unless every job narrows it, a write-capable
token next to attacker-controlled input, and review events do not trigger it. A
`workflow_run` relay would need a status-writing token, loses the PR number for
forks, and its status context can still be posted by a same-repository PR. A
first-time fork contributor's runs wait for a maintainer's approval as usual.

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
[`RELEASING.md`](RELEASING.md). Before merging a release PR, maintainers complete its
[release review checklist](RELEASING.md#release-review-checklist).

## A Note on stdout

The server speaks the MCP **stdio transport**, so `stdout` carries the JSON-RPC
protocol stream. **All logging must go to `stderr`** — never `print()` to
`stdout`, or you will corrupt the protocol stream. Use the standard `logging`
module (already configured to emit on `stderr`) instead.
