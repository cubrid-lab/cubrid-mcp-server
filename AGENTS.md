# AGENTS.md

## Organization-wide writing standard

Issue titles use **type only** (such as `feat: ...`, `bug: ...`), with no required module scope. Explain a clear human-readable problem or goal and verifiable acceptance criteria; separate verified observations from assumptions and omit personal comments/internal IDs. Triage evaluates validity, duplication, scope, priority and size; PRs/commits follow local Conventional Commits and existing PR validation gates. See [cubrid-lab's writing standard](https://github.com/cubrid-lab/.github/blob/main/docs/ISSUE_PR_COMMIT_STANDARD.md).


Guidance for AI agents and contributors working in this repository.

## Project Overview

`cubrid-mcp-server` is a [Model Context Protocol](https://modelcontextprotocol.io) server for the [CUBRID](https://www.cubrid.org/) database. It lets LLM clients safely inspect schemas and run **read-only** queries via the pure-Python [pycubrid](https://pypi.org/project/pycubrid/) driver, with an opt-in, separately registered write tool.

- Package: `cubrid_mcp_server/`
- Entry points: `cubrid-mcp-server` console script or `python -m cubrid_mcp_server`
- Tool, resource and prompt surface: [`docs/TOOLS.md`](docs/TOOLS.md) is authoritative
  (schema inspection, index/serial/class-hierarchy listing, `explain_query`,
  `table_row_counts`, read-only `execute_query`, `health_check`, and `execute_write`
  only when write mode is enabled). Security boundaries: [`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md).

## Architecture

```
cubrid_mcp_server/
├── server.py     # MCP server: tools, resources, prompts
├── database.py   # pycubrid connection + query execution
├── safety.py     # read-only SQL enforcement / whitelist, write-mode checks
├── audit.py      # opt-in, redacted stderr audit log (CUBRID_MCP_AUDIT_LOG)
├── config.py     # environment-variable configuration
├── context.py    # request/connection context
├── __main__.py   # module / console-script entry point
└── py.typed      # PEP 561 marker
```

`.mcpb/server.json` holds the MCP Registry metadata (its versions mirror `__version__`).

## Code Conventions

- Python 3.11+, fully typed (`py.typed`); keep `mypy` and `ruff` clean.
- **All logging MUST be routed to stderr.** stdout is reserved for the MCP protocol stream — never print to stdout.
- Read-only safety is a core invariant: any change touching `safety.py` / query execution must preserve read-only enforcement (and the opt-in write-mode checks) and ship tests.
- Audit output stays redacted: never log raw SQL, bound values or raw error messages from `audit.py`.

## Development

The Makefile is the canonical local and CI interface (CI's lint, type, unit and live
jobs call these targets); `make help` lists them by group.

- `make install` — install in development mode; `make doctor` — check the required tools (fails closed)
- `make check` — `lint` (`ruff check .`) + `format-check` (`ruff format --check .`) + `typecheck` (mypy)
- `make format` — the only target that rewrites files
- `make test` — offline unit tests with coverage, enforcing `fail_under` (95); no database
- `make verify` — `check`, `test`, then the live `integration` lane (needs Docker; fails closed); always writes
  `test-results/verify/summary.json`, `junit/<lane>.xml` and `environment.json` (masked), with `NOT_RUN` phases
- `make integration` — integration tests on a run-owned Compose project of the `docker-compose.yml`
  service, always removed with `down --volumes` (`CUBRID_VERSION`, default 11.4; `CUBRID_TEST_PORT`,
  default 33000; the older `INTEGRATION_PORT` still works and wins when set)
- `make integration-local` — integration tests against an already-running CUBRID (`CUBRID_*` variables)
- `make docker-up` / `docker-down` / `docker-clean` — the persistent local CUBRID of `docker-compose.yml`
  (service `cubrid`, `demodb` on `127.0.0.1:$CUBRID_TEST_PORT`) for manual work; `docker-down` keeps
  the data volume, `docker-clean` deletes it. `make integration` never touches that project.
- `make agent-eval-check` — re-grade the opt-in agent evaluation fixtures in [`agent-evals/`](agent-evals/README.md) (offline; no model, no database)
- `make release-check VERSION=x.y.z` — read-only release consistency gate (run by `release-please.yml` and `publish-pypi.yml`)

## Release Process

Version is single-sourced from `cubrid_mcp_server/__init__.py` → `__version__ = "x.y.z"`
(`pyproject.toml` reads it dynamically; `.mcpb/server.json` mirrors it for the MCP Registry).
Merging a reviewed release PR is the only normal way to release: `release-please.yml`
opens it (curated + Conventional Commit dated CHANGELOG section + `__version__` and
`.mcpb/server.json` bump, checked by `make release-check VERSION=x.y.z`), and after the
squash-merge `publish-pypi.yml` detects the version change and runs consistency → full matrix →
build → candidate verification (the cookbook smoke test in candidate mode on the built
wheel; `publish` needs it) → tag/Release/PyPI → cookbook verification (the cookbook smoke
test called as a pinned reusable workflow, no token) → summary on its own.
Freeze a release candidate with `autorelease: review` before branch-only note edits; wait for in-flight preparation to finish. Unfrozen notes come from main Unreleased. GITHUB_TOKEN updates require maintainer-triggered CI at the final head; before merging a release PR, complete the release review checklist in `RELEASING.md` (candidate head, per-check CI state, impact, release purpose). Pending labels are reconciled only after successful publication and cookbook verification.
Ordinary PRs never change `__version__` or date a
CHANGELOG section. Never push tags or publish by hand; the only manual entry point is the
narrow recovery dispatch of `publish-pypi.yml`. Procedure, failure matrix and recovery:
[`RELEASING.md`](RELEASING.md).

## GitHub Release Policy

These rules add to the release procedure above; the procedures and gates in
`RELEASING.md` stay authoritative.

### Titles

- A Release title equals its tag exactly. Stable tags and titles are `vMAJOR.MINOR.PATCH`.
- No package name, feature, date or suffix in a title (not `cubrid-mcp-server 1.2.3`,
  `v1.2.3 — Foo`, `v1.2.3 (corrected)` or `Release v1.2.3`). Drafts follow the same rule.
- Never move, delete or recreate a tag to fix a title. Never delete and recreate a
  published Release.
- Metadata edits keep the notes, assets, published state and prerelease state. When
  editing a draft through the API, always resend `tag_name`: a PATCH without it resets
  the draft's tag to `untagged-…`. `gh release edit` resends `tag_name` automatically;
  raw `gh api` PATCHes must include it.
- Automation enforces these rules: `publish-pypi.yml` creates Releases with
  `--title "$TAG"` and, on resume or recovery, fails closed through
  `scripts/check_release_title.py` when an existing Release has another title. It never
  renames one. Agents verify these rules whenever they touch release automation.

### Stale drafts

- Inspect drafts before preparing a release. Never assume a draft is pending.
- Classify each draft against its tag and the PyPI history:
  - Already shipped (tag and PyPI version both exist): publish it with
    `make_latest=false`, or remove it, only after maintainer approval.
  - Never shipped: never publish it. Delete it only after maintainer approval.
- Never delete drafts automatically. Preserve their notes and assets.

### Release notes

- `CHANGELOG.md` is the single source of truth. The Release body is the extracted
  CHANGELOG section plus one `**Full Changelog**` compare link
  (`scripts/extract_release_notes.py`).
- Allowed `###` sections, in this order, only when they have content: Upgrade notes,
  Added, Changed, Deprecated, Removed, Fixed, Security, Performance, Documentation, CI,
  Tests. `scripts/lint_changelog.py` enforces this for `[Unreleased]` and for releases
  after 0.4.0.
- Use `Documentation`, not `Docs`. Put release automation and tooling entries under
  `CI` or `Changed`.
- Never bulk-rewrite historical notes or regenerate them from current `main`. A
  selective fix needs a dry-run diff and maintainer approval. Never invent PR or commit
  references. Note formatting never changes tags, dates, artifacts or publish state.

## Development Workflow (cubrid-lab org standard)

Use the same PR review and merge criteria for human-authored changes and
OpenCode, Codex, Claude Code, ChatGPT, Copilot or other agents. No special
Oracle design/post review or Copilot sign-off is required solely because
a particular coding tool was used.

1. **Implement:** scope a focused PR, provide tests and affected docs.
2. **Validate:** required GitHub Actions CI is the authoritative evidence
   at the final PR head, including offline, integration/live CUBRID, docs,
   security and applicable release checks. Local checks are recommended
   but never replace CI or create an extra merge gate.
3. **Review:** assess correctness, safety, behavior, maintainability and
   residual risk. Oracle, Copilot and `agent-review` may add useful
   **advisory** observations, never automatic approval or rejection.
4. **Merge:** disposition findings and confirm required checks on the final
   code. A responsible maintainer makes the decision. Preserve separate
   scrutiny and independent review for security-sensitive and high-impact
   workflow/release paths.

For this MCP server specifically, preserve the read-only/write-mode controls,
SQL execution restrictions, audit records, timeout/connection safety and MCP
stdout protocol. Changes to `safety.py`, `database.py`, `audit.py`,
`server.py`, workflow permissions and publishing require explicit
security/invariant assessment irrespective of implementation tool.

## PR overlap and execution precedence

- Before creating a PR, check its linked issue's current decision and
  dependencies, open PRs that affect the same behavior and relevant changes
  merged to `main`. Record `Supersedes #N`, `Depends on #N` or
  `Parallel to #N` with a brief reason, or `None`.
- Select the canonical implementation by accepted behavior, safety, test
  evidence and maintainer direction, not PR number or creation time. Check
  again against current `main` before merge. A passing CI job or optional
  AI review does not waive unresolved prerequisites, read-only/write-mode
  security reviews, protected-path approval or a release decision.
- After merging, reconcile displaced open PRs and linked issues: comment
  and close truly superseded work with its replacement link, or explain why
  valid parallel work remains. Preserve external contributor discussion and
  ownership.
- A policy decision also requires checking open issue/PR instructions and
  contributor templates for conflicting older text; fix it in the same review
  cycle or record a focused follow-up.
- Issue `priority: ...` is urgency, `size: ...` is effort, and PR readiness
  depends on satisfied prerequisites, required final-head CI, safety and
  maintainer judgment. Prioritize the next executable item and explain an
  exception in its local issue. Do not create a new check, bot or merge gate.

## Issue specification and ownership

Issues and implementation acceptance are repository-local: file work in the
repository whose code, workflow, or documentation must change. Each repository
owns its scope, priority, assignee, validation, release decision and closure.
Every issue must be understandable without opening another repository's issue.
When several repositories need changes, create a separate, self-contained issue
and PR in each repository. Never use an issue here as an organization-wide
tracker, a shared implementation contract or an approval gate for other projects.
Link another repository's issue only when its concrete technical behavior is
essential evidence for local reproduction or verification; do not cross-link
implementation issues by default or inherit another repository's acceptance
criteria, ownership or closure requirements.

Before publishing or editing an issue, inspect its title and full body:
- Describe this repository's problem, evidence, affected files and actual Make
  targets, expected behavior and checkable completion criteria.
- Exclude contest/judging, assessment, submission, presentation rehearsal,
  evaluation-tag/SHA freezes and event-timed implementation gates. Commit or
  release identifiers belong only where needed to reproduce technical behavior.
- Do not invent `make spec-*` targets, assume a sibling project's commands apply
  here or prescribe a universal command/report format without checking this
  repository's Makefile and CI.
- Search for duplicate issues and conflicting target semantics before posting;
  reread the saved title/body and correct misplaced scope or references.
Never use issue auto-closing keywords with another repository's issue; its
maintainer controls closure. The existing required PR title check rejects
direct foreign-repository closing references in the PR body, the PR title and
commit messages while allowing Refs links. `main` is squash-merged with the PR
title and the commit messages; an edit to the squash message at merge time is
not checked, so do not add foreign closing keywords there.

An issue body is the current work specification, not a session transcript. Before
implementing a non-trivial issue, ensure it states the problem and impact, evidence
with a revision/environment, reproduction steps or the investigation question,
expected behavior, scope/non-goals, relevant files, verifiable completion criteria,
validation method and real dependencies. Say "not verified" when evidence is missing;
never invent a reproduction, result, release availability or test command. Small
docs tasks need only the applicable fields.

- Put dated progress, pause/resume notes and review outcomes in comments. Keep
  historical evidence in the body with its original revision/date and evidence limits.
- For maintainer-operated autonomous agents and internally assigned work, set the actual implementer in GitHub Assignees before implementation. A comment is not a substitute for agent assignment; newcomer-reserved issues also require specific authorization.
- Human-led outside contributors (including AI-assisted human work) may start an unclaimed issue or submit a PR without maintainer preapproval or self-assignment rights. Check Assignees, comments and open PRs, and coordinate before overlapping someone else's claimed work; comments are encouraged but optional.
- Maintainers manage assignments, labels and handoffs while preserving existing contributor evidence and open PRs.
- Reconcile stale dependencies and checklists before closing. A merged child or
  upstream PR is not proof of integrated acceptance or of a released dependency.
- This server has SQL-safety, write-mode, audit and MCP protocol invariants: stdout
  is reserved for the MCP protocol (logs go to stderr), read-only is the default with
  opt-in write safety, audit output stays redacted, timeout/cancellation and
  connection cleanup are preserved, and releases follow the guarded flow. Changes
  must not weaken them.

## Agent PR scope and review guardrails

- Define scope, acceptance criteria, tests and explicit non-goals before
  implementation; avoid widening scope to satisfy speculative AI findings.
- AI review is optional for every author; avoid repeated bot review requests
  and apply the same evidence-based defect triage to all PRs.
- Preserve contributor history; do not re-review outside PRs without a
  changed head, and do not merge with unresolved critical/security defects
  or failing required GitHub CI.

## Review disposition and merge evidence

- Record the tested PR head, GitHub CI results, unrun checks and relevant
  issues, with a responsible maintainer's final decision.
- Classify each finding as fixed with verification, rejected with evidence,
  or deferred to an explicit issue. Keep sensitive security reports private.
- Reply once with final disposition to each relevant inline thread; only
  resolve after reviewing updated code, not merely a bot reply or stale diff.
- Oracle, Copilot and `agent-review` findings can inform this process but
  are not mandatory evidence or separate approval routes.
- For safety, workflow permissions and release changes, document the
  invariant/security assessment and obtain independent maintainer review.

## Issue triage lifecycle

Every newly opened issue in this repository starts with `status: needs triage`.
The issue forms include it, and `issues: opened` automation adds it for
external submissions. Tools using `GITHUB_TOKEN` must supply it at creation,
as these issue events may not trigger an additional workflow.

1. **Validate:** verify evidence, read-only/write/security impact, duplicates,
   overlap with open PRs, issue type, owning repository, scope, acceptance
   criteria and real dependencies. Close invalid or duplicated work with a
   reason rather than assigning speculative severity.
2. **Compare:** inspect **all open issues here**, including paginated results,
   and compare impact, existing priorities, blocked prerequisites and work in
   progress. Record why any older issue needs reprioritization.
3. **Classify:** confirm one `priority: critical/high/medium/low` and one
   existing `size: XS/S/M/L/XL`. Split oversized work when it cannot be
   independently verified; keep contributor ownership and unrelated labels.
4. **Complete:** re-read the saved issue and its actual labels, scope and
   duplication decision. Remove `status: needs triage` only after checking
   type, priority, size and relative queue position. If still uncertain, leave
   the label. Do not auto-score severity or auto-remove it from a workflow.

Existing MCP safety, required CI, independent protected-path review and
release controls are unchanged. Issue triage is not a new PR gate.

## Issue Labeling (cubrid-lab org standard)

Maintainers and triagers own the canonical priority/size policy. When creating or
triaging an issue in **any cubrid-lab repository** (including authorized agents acting
for maintainers), assign exactly one `priority: <value>` label and exactly one
`size: <value>` label, alongside a type label (`bug`/`enhancement`/`documentation`/`chore`/`ci`/…) and an
`area:` label when applicable. These must be GitHub labels, not just text in the
issue title or body. Outside reporters only describe urgency and effort and do not
need label-write permission; all new issues first get `status: needs triage`
and receive final priority/size labels during maintainer review.

Issue titles use `type: description` without a module scope (see [organization standard](https://github.com/cubrid-lab/.github/blob/main/docs/ISSUE_PR_COMMIT_STANDARD.md)).

Use the following exact names, with **one space after the colon**:

- Priority: `priority: critical`, `priority: high`, `priority: medium`, `priority: low`.
- Size: `size: XS`, `size: S`, `size: M`, `size: L`, `size: XL`.

Do not introduce variants such as `priority:high`, `priority-high`, `P1`, or
`size:S`. Reuse the repository's canonical labels; if a required label is missing,
create it with the exact name above before filing the issue. This policy governs
new issue creation, not bulk renaming or relabeling existing issues unless
explicitly requested.

Priority reflects urgency and impact; size estimates implementation effort and
helps contributors pick appropriately scoped work.

| Label | Meaning | Rough guide |
|-------|---------|-------------|
| `size: XS` | Trivial change | < ~10 lines; single-file typo/config/one-liner |
| `size: S` | Small change | One file or one focused function; a single test or doc page |
| `size: M` | Medium change | A few files; a new test module, a bug fix with tests, a CI job |
| `size: L` | Large change | Cross-cutting change across many files; multi-artifact (e.g. demo GIF + video + docs) |
| `size: XL` | Very large | Consider splitting into smaller issues before starting |

Rules:

1. **Size reflects effort, not importance** — a one-line fix for a critical bug is still `size: XS`.
2. **Finalize exactly one `priority:` and one `size:` after triage.**
   Keep `status: needs triage` while the evidence, scope or classification
   remains undecided, even if a provisional label already exists.
3. **`good first issue` should be `size: XS` or `size: S`.** If a good-first-issue grows
   past `size: S`, re-scope it or drop the `good first issue` label.
4. **`size: XL` is a signal to split**, not a green light to start a sprawling change.

### Good first issue lifecycle

- **Human-led community contributors (including people directing and reviewing AI-assisted work)** may start an unassigned `good first issue` and submit a PR without prior maintainer authorization, GitHub Assignee permission, or internal agent tooling.
- First check current Assignees, comments, and open PRs. An interest comment is welcome but optional: it is not an approval requirement or exclusive ownership. Coordinate before overlapping or taking over claimed work.
- **Maintainer-operated autonomous coding agents** must have explicit permission naming that specific newcomer-reserved issue and an actual GitHub assignment before implementation. Broad backlog/release requests are not authorization.
- Maintainers manage Assignees and labels; ordinary CI/review/merge requirements continue for every contribution.
- Unclaimed: retain `good first issue`.
- A PR is opened: maintainers remove `good first issue` and add `status: in progress`, coordinating ownership.
- A PR is merged: close the issue.
- A PR closes unmerged: check that no other open PR still owns the task before restoring `good first issue` and removing `status: in progress`.
- Keep at least three genuinely unclaimed XS/S newcomer issues with a small blast radius and a reference pattern.
- A release-blocker handoff to an autonomous agent requires a recorded maintainer decision after checking Assignees, comments and open PRs.

## Documentation definition of done

Any change that affects public behavior, MCP tools, configuration/environment variables, read-only safety semantics, installation, or release semantics MUST update the matching documentation in the **same PR**. At minimum keep in sync: `README.md` (tool table + configuration) and `CHANGELOG.md`.

If no documentation change is needed, state the reason explicitly in the PR body as `Docs: not needed - <reason>` or apply the `docs-not-needed` label. This is enforced by the `docs-sync` CI check.

Do not mark work complete until code, tests, and documentation are consistent.

## Commit Convention

Pull request titles and commit subjects follow
[CONTRIBUTING.md](CONTRIBUTING.md#pull-request-and-commit-titles):
`type(scope)!: description` with types `feat`, `fix`, `docs`, `test`, `perf`,
`refactor`, `ci`, `build`, `chore`, `style`, `revert`; English, lowercase start
unless the first word is an API name, acronym, or proper noun; no trailing
period, no issue numbers in pull request titles (use `Closes #N` /
`Refs #N` in the body). Pull requests are squash-merged and the pull request
title becomes the commit title. The `PR title` check enforces it.

There is no `security` type: security fixes use `fix:` plus the `security` label.

## Related Projects

- [pycubrid](https://github.com/cubrid-lab/pycubrid) — Pure Python DB-API 2.0 driver for CUBRID
- [sqlalchemy-cubrid](https://github.com/cubrid-lab/sqlalchemy-cubrid) — SQLAlchemy 2.0 dialect for CUBRID
- [cubrid-cookbook-python](https://github.com/cubrid-lab/cubrid-cookbook-python) — Production-ready Python examples for CUBRID
