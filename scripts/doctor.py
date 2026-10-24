#!/usr/bin/env python3
"""Check the local development tooling (``make doctor``, #379).

Required: Python 3.11+, the ``ruff`` and ``mypy`` commands, and the ``pytest``,
``pytest_cov`` and ``pytest_asyncio`` modules from ``pip install -e . --group dev``.
Docker is reported but optional: only ``make integration`` needs it.

Exits 1 and prints no success line when anything required is missing.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys

MIN_PYTHON = (3, 11)
COMMANDS = ("ruff", "mypy")
MODULES = ("pytest", "pytest_cov", "pytest_asyncio")
OPTIONAL_COMMANDS = {"docker": "needed only for make integration"}


def problems() -> list[str]:
    found: list[str] = []
    if sys.version_info[:2] < MIN_PYTHON:
        version = ".".join(map(str, sys.version_info[:3]))
        found.append(f"Python {version} is older than {'.'.join(map(str, MIN_PYTHON))}")
    found += [f"command {c!r} not found" for c in COMMANDS if shutil.which(c) is None]
    found += [f"module {m!r} not installed" for m in MODULES if not importlib.util.find_spec(m)]
    return found


def main() -> int:
    for command, purpose in OPTIONAL_COMMANDS.items():
        if shutil.which(command) is None:
            print(f"note: optional command {command!r} not found ({purpose})")
    missing = problems()
    if missing:
        for problem in missing:
            print(f"MISSING: {problem}", file=sys.stderr)
        print(
            "Install the dev tools with: make install (pip install -e . --group dev)",
            file=sys.stderr,
        )
        return 1
    print("doctor: all required development tools found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
