# Contributing to cubrid-mcp-server

Thanks for your interest in improving the CUBRID MCP server. This guide covers
the specifics of **this** repository — the Makefile targets, the checks CI
enforces, and how to run the integration suite against a live CUBRID.

For the organization-wide contribution guidelines (code of conduct, how to file
issues, DCO/sign-off, review flow), see the shared
[cubrid-lab/.github/CONTRIBUTING.md](https://github.com/cubrid-lab/.github/blob/main/CONTRIBUTING.md).
This document only adds what is repo-specific; it does not repeat the org guide.

## Prerequisites

- Python 3.10 or later
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
the issue or PR number — match the format of the existing entries. Do **not**
bump the version yourself; releases are cut with `make release VERSION=x.y.z`.

## Commit Style

This repo uses [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <description>
```

Types in use: `feat`, `fix`, `docs`, `chore`, `ci`, `style`, `test`,
`refactor`, `security`.

## A Note on stdout

The server speaks the MCP **stdio transport**, so `stdout` carries the JSON-RPC
protocol stream. **All logging must go to `stderr`** — never `print()` to
`stdout`, or you will corrupt the protocol stream. Use the standard `logging`
module (already configured to emit on `stderr`) instead.
