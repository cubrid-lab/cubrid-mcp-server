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
- `make release VERSION=x.y.z` — release commit + tag

## Release Process

Version is single-sourced from `cubrid_mcp_server/__init__.py` → `__version__ = "x.y.z"`.

Steps:
1. Bump the version and add a dated changelog entry in `CHANGELOG.md` (`## [x.y.z] - YYYY-MM-DD`).
2. Open a PR and merge to `main`.
3. Push the tag on the merged commit: `git tag vx.y.z <merged-sha> && git push origin vx.y.z`.
4. The tag push triggers `.github/workflows/create-release.yml`, which extracts the
   `## [x.y.z] - YYYY-MM-DD` section from `CHANGELOG.md` (fail-closed — no fallback) and
   creates the GitHub Release titled `vx.y.z` with that body, after verifying the tag is
   an ancestor of `origin/main`.
5. Publishing the GitHub Release triggers `.github/workflows/publish-pypi.yml`, which
   rebuilds, verifies, and publishes to PyPI via Trusted Publisher (OIDC).

Release notes are never hand-written: `CHANGELOG.md` is the single source of truth and
`scripts/extract_release_notes.py` renders the Release body. To re-create a release body,
re-run `create-release.yml` via `workflow_dispatch` with `update_existing: true`.

## Development Workflow (cubrid-lab org standard)

All non-trivial work MUST follow this cycle:

1. **Oracle Design Review** — validate approach before implementation.
2. **Implementation** — build with tests, following existing patterns.
3. **Documentation Update** — update all affected docs (README tool table, configuration, CHANGELOG) in the same PR.
4. **Oracle Post-Implementation Review** — review correctness, edge cases, and consistency before merging.

Trivial changes (typos, single-line fixes) may skip phases 1 and 4.

## Issue Labeling (cubrid-lab org standard)

Every issue MUST carry a `size:` label estimating implementation effort, in addition
to `type` (`bug`/`enhancement`/`docs`/`chore`/`ci`/…) and, when applicable, `priority:`
and `area:` labels. The `size:` label sets contributor expectations up front and helps
newcomers pick appropriately scoped work.

| Label | Meaning | Rough guide |
|-------|---------|-------------|
| `size: XS` | Trivial change | < ~10 lines; single-file typo/config/one-liner |
| `size: S` | Small change | One file or one focused function; a single test or doc page |
| `size: M` | Medium change | A few files; a new test module, a bug fix with tests, a CI job |
| `size: L` | Large change | Cross-cutting change across many files; multi-artifact (e.g. demo GIF + video + docs) |
| `size: XL` | Very large | Consider splitting into smaller issues before starting |

Rules:

1. **Size reflects effort, not importance** — a one-line fix for a critical bug is still `size: XS`.
2. **Assign `size:` when the issue is filed or triaged.** If scope is unknown, apply
   `status: needs triage` (or the repo's equivalent) until it can be sized.
3. **`good first issue` should be `size: XS` or `size: S`.** If a good-first-issue grows
   past `size: S`, re-scope it or drop the `good first issue` label.
4. **`size: XL` is a signal to split**, not a green light to start a sprawling change.

## Documentation definition of done

Any change that affects public behavior, MCP tools, configuration/environment variables, read-only safety semantics, installation, or release semantics MUST update the matching documentation in the **same PR**. At minimum keep in sync: `README.md` (tool table + configuration) and `CHANGELOG.md`.

If no documentation change is needed, state the reason explicitly in the PR body as `Docs: not needed - <reason>` or apply the `docs-not-needed` label. This is enforced by the `docs-sync` CI check.

Do not mark work complete until code, tests, and documentation are consistent.

## Commit Convention

```
<type>: <description>

<body>
```

Types: `feat`, `fix`, `docs`, `chore`, `ci`, `style`, `test`, `refactor`

## Related Projects

- [pycubrid](https://github.com/cubrid-lab/pycubrid) — Pure Python DB-API 2.0 driver for CUBRID
- [sqlalchemy-cubrid](https://github.com/cubrid-lab/sqlalchemy-cubrid) — SQLAlchemy 2.0 dialect for CUBRID
- [cubrid-cookbook-python](https://github.com/cubrid-lab/cubrid-cookbook-python) — Production-ready Python examples for CUBRID
