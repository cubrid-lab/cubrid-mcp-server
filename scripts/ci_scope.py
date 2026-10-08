"""Classify a CI run into explicit validation scopes (#223).

Reads changed paths (one per line) on stdin and prints ``key=value`` lines for
``$GITHUB_OUTPUT``. ``ci.yml`` runs only the lanes these scopes select and its
``ci-gate`` requires every selected lane to succeed.

Tiers:

* ``docs``  - docs/metadata-only PR: no unit job, no live CUBRID, changelog lint only.
* ``pr``    - ordinary PR: representative Python unit lane, plus risk-selected lanes
  (one default live CUBRID lane for runtime/test changes, lowest-direct for
  dependency metadata, Python/CUBRID endpoints for compatibility changes).
* ``full``  - push to main, manual dispatch, or a change to the CI policy itself:
  Python endpoints, both primary CUBRID endpoints and lowest-direct.

Unknown paths fail closed: they select the unit lane and the default live lane.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from fnmatch import fnmatchcase

REPRESENTATIVE_PYTHON = "3.12"
PYTHON_ENDPOINTS = ["3.11", "3.12", "3.14"]
DEFAULT_CUBRID = "11.4"
CUBRID_ENDPOINTS = ["11.2", "11.4"]

# Changing the CI policy itself runs every lane so the change is self-tested.
SELF = (".github/workflows/ci.yml", "scripts/ci_scope.py", "tests/test_ci_scope.py")
# Dependency metadata: lowest-direct plus endpoint lanes (requires-python, driver pins).
DEPS = ("pyproject.toml",)
# Other workflows (shared pinned actions, matrix definitions): endpoint lanes.
COMPAT = (".github/workflows/*",)
# Connection / catalog SQL / live suite: both primary CUBRID endpoints.
LIVE_ENDPOINTS = (
    "cubrid_mcp_server/database.py",
    "cubrid_mcp_server/context.py",
    "tests/conftest.py",
    "tests/test_integration.py",
)
# Runtime and tests: unit plus one default live CUBRID lane.
RUNTIME = ("cubrid_mcp_server/*", "tests/*")
# Tooling and metadata exercised by unit tests only; never starts CUBRID.
TOOLING = (
    "scripts/*",
    "Makefile",
    "codecov.yml",
    ".gitignore",
    ".mcpb/*",
    "glama.json",
    ".github/dependabot.yml",
    ".github/ISSUE_TEMPLATE/*",
    "demos/*",
    # Checked against pyproject.toml by tests/test_third_party_licenses.py (#218).
    "THIRD_PARTY_LICENSES.md",
)
# Docs-only: no unit job, no CUBRID.
DOCS = ("*.md", "docs/*", "LICENSE", "NOTICE", "llms.txt", "mkdocs.yml")

FULL_EVENTS = {"push", "workflow_dispatch", "schedule"}


def _match(path: str, patterns: Iterable[str]) -> bool:
    # fnmatch's ``*`` also crosses ``/``, so ``docs/*`` covers the whole tree.
    return any(fnmatchcase(path, pattern) for pattern in patterns)


def classify(event: str, paths: Iterable[str]) -> dict[str, object]:
    files = sorted({p.strip() for p in paths if p.strip()})
    unit = lowest = live = py_endpoints = cubrid_endpoints = False
    full = event in FULL_EVENTS

    if event != "pull_request" and not full:
        full = True  # unknown event: fail closed to the widest tier
    if event == "pull_request" and not files:
        full = True  # an empty diff is unexpected: fail closed

    for path in files:
        if _match(path, SELF):
            full = True
        elif _match(path, DEPS):
            unit = lowest = live = py_endpoints = cubrid_endpoints = True
        elif _match(path, COMPAT):
            unit = live = py_endpoints = cubrid_endpoints = True
        elif _match(path, LIVE_ENDPOINTS):
            unit = live = cubrid_endpoints = True
        elif _match(path, RUNTIME):
            unit = live = True
        elif _match(path, TOOLING):
            unit = True
        elif _match(path, DOCS):
            pass
        else:
            unit = live = True  # unknown path: fail closed

    if full:
        unit = lowest = live = py_endpoints = cubrid_endpoints = True

    if full:
        tier = "full"
    elif unit or live or lowest:
        tier = "pr"
    else:
        tier = "docs"

    return {
        "tier": tier,
        "unit": unit,
        "python": PYTHON_ENDPOINTS if py_endpoints else [REPRESENTATIVE_PYTHON],
        "lowest": lowest,
        "live": live,
        "cubrid": CUBRID_ENDPOINTS if cubrid_endpoints else [DEFAULT_CUBRID],
    }


def render(scope: dict[str, object]) -> str:
    lines = []
    for key, value in scope.items():
        if isinstance(value, bool):
            value = "true" if value else "false"
        elif isinstance(value, list):
            value = json.dumps(value, separators=(",", ":"))
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify CI validation scopes (#223)")
    parser.add_argument("--event", required=True, help="github.event_name")
    args = parser.parse_args(argv)
    sys.stdout.write(render(classify(args.event, sys.stdin.read().splitlines())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
