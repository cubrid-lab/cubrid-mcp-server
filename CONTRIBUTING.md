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
starts `cubrid/cubrid:11.2` in Docker and waits for `demodb` to be ready; you
can do the same locally, then point the tests at it:

```bash
export CUBRID_HOST=localhost
export CUBRID_USER=dba
export CUBRID_PASSWORD=""
export CUBRID_DATABASE=demodb
make integration
```

## What CI Enforces

A PR has to clear all of the following (see `.github/workflows/ci.yml`). None of
them are optional — the final `ci-gate` job requires every one to pass:

- **`ruff check .`** — linting.
- **`ruff format --check .`** — formatting (run `make format` to fix).
- **`mypy` in strict mode** — type checking of `cubrid_mcp_server/`.
- **Pytest with a 95% coverage floor** — `fail_under = 95` in `pyproject.toml`.
  This is the gate that most often fails a PR; add tests for new code paths.
- **`lowest-direct` job** — reinstalls with the lowest allowed direct
  dependency versions (`uv pip install --resolution lowest-direct`) and re-runs
  the unit tests, catching accidental use of newer-than-declared APIs.
- **`python scripts/lint_changelog.py`** — checks `CHANGELOG.md` structure and
  version ordering.

## CHANGELOG

Add an entry under `## [Unreleased]` in
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) style, in the
appropriate group (`Added` / `Changed` / `Fixed` / `Security`), and reference
the issue or PR number — match the format of the existing entries. Security
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
version change is what starts an automatic release. Maintainers open release
PRs with `prepare-release.yml`; see [`RELEASING.md`](RELEASING.md).

## A Note on stdout

The server speaks the MCP **stdio transport**, so `stdout` carries the JSON-RPC
protocol stream. **All logging must go to `stderr`** — never `print()` to
`stdout`, or you will corrupt the protocol stream. Use the standard `logging`
module (already configured to emit on `stderr`) instead.
