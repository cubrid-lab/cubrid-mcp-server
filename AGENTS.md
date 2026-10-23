# AGENTS.md

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
- `make verify` — `check` + `test`; no Docker
- `make integration` — integration tests on a run-owned Docker CUBRID that is always removed
  (`CUBRID_VERSION`, default 11.4; `INTEGRATION_PORT`, default 33000)
- `make integration-local` — integration tests against an already-running CUBRID (`CUBRID_*` variables)
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

The required review route is selected by the tool that **actually developed**
the change, and recorded in the PR. Review requested, green CI, self-review
and an automated "approval recommended" summary are not completed reviews.

**OpenCode with Oracle**, for non-trivial work:
1. Obtain Oracle pre-implementation **design** review before editing.
2. Implement the agreed scope, preserving read-only/write-mode, audit,
   connection/timeout and MCP stdout invariants, with tests.
3. Update only affected documentation, such as `README.md`, `docs/TOOLS.md`,
   `docs/SECURITY_MODEL.md` and `CHANGELOG.md`, under the existing docs policy.
4. Obtain Oracle post-implementation **code** review, disposition findings,
   and record both reviews plus executed validation.

Trivial OpenCode changes may omit phases 1 and 4 only with a recorded reason.
Oracle pre/post reviews satisfy this route; a further Copilot review is not
required. Existing branch/maintainer and required CI conditions
still apply.

**Standalone agents (Claude Code, Codex, ChatGPT, or other agent tools):**
open a PR after implementation, tests and docs, then **wait for a substantive
submitted GitHub Copilot review or a review by a maintainer**, recorded on the
PR, before merging (maintainer decision, 2026-10-15). A maintainer is a code
owner in `.github/CODEOWNERS` other than the PR's author. Reviews by other
people, and reviews by AI agents other than Copilot, are welcome but do not
satisfy this route. A Copilot COMMENTED review with an actual code assessment
counts; it is not GitHub APPROVED status. Requested/pending reviews, Copilot
suggestion summaries without substantive assessment, self-review and passing
CI are insufficient. Evaluate findings against the final relevant head. Without
the required review, leave the PR unmerged (Draft/pending review). No CI check
enforces this today; whether to add one is pending a maintainer decision
(#317).

**Security-sensitive paths, under every route:** changes to `safety.py`,
`database.py`, `audit.py`, `server.py`, or to workflows that hold write
permissions or perform releases, get stricter scrutiny. Their review must
explicitly assess the read-only/write-mode, audit-redaction and MCP stdout
invariants they carry, and a maintainer confirms that disposition before
merge.

**`agent-review` check (advisory only):** `.github/workflows/agent-review.yml`
reports from GitHub's own review records whether this route is met (rules in
[CONTRIBUTING.md](CONTRIBUTING.md#agent-review-evidence-gate)). It counts a
substantive Copilot review of the head within the two-round budget, or a
maintainer's `APPROVED` review, or `COMMENTED` review that opens an inline
thread; never PR-body checkboxes, pending requests, self-review, other people's
or other AI agents' reviews, summary-only bot text or a review of an older
commit (unless the PR's change against `main` is identical at both commits).
Protected paths (`safety.py`, `database.py`, `audit.py`, `server.py`,
`config.py`, `__main__.py`, `context.py`, every workflow and the gate itself)
need a maintainer's `APPROVED` review. Oracle output is private and is not
GitHub evidence: an OpenCode + Oracle PR passes the check when a maintainer,
after checking the recorded Oracle reviews, approves the head. A PR can publish
a check with the same name, so the check is a reading aid and must not be made
a required status check until it is posted from an identity a PR cannot
impersonate, such as a GitHub App. A run triggered by Copilot's review waits as
"action required": re-run it, or edit the PR body, after Copilot reviews.

**Human contributions:** follow ordinary contributor requirements;
maintainers arrange any project-specific tooling and integration. This route
is not a fallback for unnamed standalone agent tools, which use the route above.
Installing OpenCode, Oracle, Copilot, Claude Code or Codex is never an
outside-contributor prerequisite. Preserve original authorship and use
attribution only for tools actually involved.

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

- Before editing, record one acceptance contract, affected files, non-goals and the
  validation plan. Keep each PR to one independently reviewable change.
- AI severity is not authority to expand scope. Out-of-scope findings become
  separate issues unless the maintainer explicitly expands the contract.
- Default to two published AI review rounds per scoped PR/task (initial review plus
  one corrective re-review). Further rounds or scope expansion require explicit
  maintainer direction.
- Never merge with unresolved critical/security defects or failed required CI. Keep
  incomplete work Draft and report blockers and a proposed split.
- Preserve contributor history. Do not repeatedly re-review an external PR until its
  author updates the head.

## Review disposition and merge evidence

- Record the development route, Oracle pre/post evidence or the Copilot or
  maintainer review, reviewer, reviewed head SHA and pending/complete status
  in the PR.
- Classify findings as fixed (commit + focused test), rejected with
  contract/reproduction evidence, or deferred with a linked issue. Keep
  confirmed security-sensitive reproductions in the private reporting path.
- Leave one **final** reply per inline review finding. A maintainer or reviewer
  resolves its thread only after validating the updated code and evidence;
  an outdated diff or "Fixed" reply alone is not resolution. Do not bulk-resolve
  historical threads or spam requests for another AI review.
- Keep one editable agent-owned English PR status comment for the aggregate
  findings, outstanding threads, verification results and unrun checks.
- Apply the existing two-published-AI-review-round budget. If review is still
  pending or unresolved at that limit, retain Draft and request a maintainer
  decision rather than bypassing review or endlessly revising.
- Never merge with the required review still pending, failed required
  CI, or unresolved critical/security findings. Record a maintainer decision
  for any other open finding. These are process rules, not an auto-merge or
  branch-protection change.

## Issue Labeling (cubrid-lab org standard)

Maintainers and triagers own the canonical priority/size policy. When creating or
triaging an issue in **any cubrid-lab repository** (including authorized agents acting
for maintainers), assign exactly one `priority: <value>` label and exactly one
`size: <value>` label, alongside a type label (`bug`/`enhancement`/`documentation`/`chore`/`ci`/…) and an
`area:` label when applicable. These must be GitHub labels, not just text in the
issue title or body. Outside reporters only describe urgency and effort and do not
need label-write permission; maintainer-created issues are labeled at creation and
permissionless reports during initial maintainer triage.

Issue titles use the same `type(scope): description` format as pull request
titles (see [CONTRIBUTING.md](CONTRIBUTING.md#pull-request-and-commit-titles)).

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
2. **Assign both `priority:` and `size:` when filing the issue.** If scope or impact
   is uncertain, use a provisional estimate, explain the uncertainty in the body,
   and add `status: needs triage` (or the repo's equivalent). Refine the estimates
   during triage rather than omitting either required label.
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

Issue titles, pull request titles and commit subjects follow
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
