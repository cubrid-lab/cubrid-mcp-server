# AGENTS.md

Guidance for AI agents and contributors working in this repository.

## Project Overview

`cubrid-mcp-server` is a [Model Context Protocol](https://modelcontextprotocol.io) server for the [CUBRID](https://www.cubrid.org/) database. It lets LLM clients safely inspect schemas and run **read-only** queries via the pure-Python [pycubrid](https://pypi.org/project/pycubrid/) driver.

- Package: `cubrid_mcp_server/`
- Entry point: `python -m cubrid_mcp_server`
- Tool surface (see `README.md`): schema inspection, index/serial/class-hierarchy listing, `explain_query`, `execute_query` (read-only), `health_check`.

## Architecture

```
cubrid_mcp_server/
├── server.py     # MCP server + tool definitions
├── database.py   # pycubrid connection + query execution
├── safety.py     # read-only SQL enforcement / whitelist
├── config.py     # environment-variable configuration
├── context.py    # request/connection context
└── __main__.py   # module entry point
```

## Code Conventions

- Python 3.10+, fully typed (`py.typed`); keep `mypy` and `ruff` clean.
- **All logging MUST be routed to stderr.** stdout is reserved for the MCP protocol stream — never print to stdout.
- Read-only safety is a core invariant: any change touching `safety.py` / query execution must preserve read-only enforcement and ship tests.

## Development

- `make install` — install in development mode
- `make check` — ruff lint + mypy typecheck
- `make test` — unit tests (excludes integration)
- `make integration` — integration tests (requires a live CUBRID)
- `make release-check VERSION=x.y.z` — read-only release consistency gate (run by `prepare-release.yml` and `release.yml`)

## Release Process

Version is single-sourced from `cubrid_mcp_server/__init__.py` → `__version__ = "x.y.z"`
(`pyproject.toml` reads it dynamically; `.mcpb/server.json` mirrors it for the MCP Registry).
Merging a reviewed release PR is the only normal way to release: `prepare-release.yml`
opens it (dated CHANGELOG section + `__version__` and `.mcpb/server.json` bump, checked by
`make release-check VERSION=x.y.z`), and after the squash-merge `release.yml` detects the
version change and runs consistency → full matrix → build → tag/Release/PyPI → cookbook
verification (the cookbook smoke test called as a pinned reusable workflow, no token) →
summary on its own. Ordinary PRs never change `__version__` or date a
CHANGELOG section. Never push tags or publish by hand; the only manual entry point is the
narrow recovery dispatch of `release.yml`. Procedure, failure matrix and recovery:
[`RELEASING.md`](RELEASING.md).

## Development Workflow (cubrid-lab org standard)

All non-trivial work MUST follow this cycle:

1. **Oracle Design Review** — validate approach before implementation.
2. **Implementation** — build with tests, following existing patterns.
3. **Documentation Update** — update all affected docs (README tool table, configuration, CHANGELOG) in the same PR.
4. **Oracle Post-Implementation Review** — review correctness, edge cases, and consistency before merging.

Trivial changes (typos, single-line fixes) may skip phases 1 and 4.

## Issue Labeling (cubrid-lab org standard)

When creating an issue in **any cubrid-lab repository**, assign exactly one
`priority: <value>` label and exactly one `size: <value>` label at creation time,
alongside a type label (`bug`/`enhancement`/`documentation`/`chore`/`ci`/…) and an
`area:` label when applicable. These must be GitHub labels, not just text in the
issue title or body.

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

## Documentation definition of done

Any change that affects public behavior, MCP tools, configuration/environment variables, read-only safety semantics, installation, or release semantics MUST update the matching documentation in the **same PR**. At minimum keep in sync: `README.md` (tool table + configuration) and `CHANGELOG.md`.

If no documentation change is needed, state the reason explicitly in the PR body as `Docs: not needed - <reason>` or apply the `docs-not-needed` label. This is enforced by the `docs-sync` CI check.

Do not mark work complete until code, tests, and documentation are consistent.

## Commit Convention

Issue titles, pull request titles and commit subjects follow
[CONTRIBUTING.md - Pull request and commit titles](CONTRIBUTING.md#pull-request-and-commit-titles):
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
