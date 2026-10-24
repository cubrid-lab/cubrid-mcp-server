#!/usr/bin/env python3
"""Write ``test-results/<lane>/summary.json`` and ``environment.json`` (#405).

``make test`` and ``make integration`` write their pytest JUnit XML (and, for
``make test``, ``coverage.xml``) under ``test-results/<lane>/``. This helper turns
those files into one machine-readable ``summary.json`` and prints the same status and
counts as a single console line. It never changes a command's exit status: callers
keep the status pytest returned and pass it in with ``--exit-code``.

Status:

- ``FAIL``: a test failed or errored, or pytest/the run exited non-zero (a coverage
  floor miss, a service that never started, a missing JUnit file after a failure).
- ``INCOMPLETE``: nothing proves the lane ran: no JUnit file, nothing collected, or no
  test passed (every selected test skipped or xfailed). Never ``PASS``.
- ``PASS``: at least one test passed, none failed or errored, and the exit status is 0.

JUnit XML cannot tell an unexpected pass of a non-strict xfail from an ordinary pass,
so ``xpassed`` is always 0 (a strict xpass is reported as a failure by pytest).

``environment.json`` records the Python, package and CUBRID versions, the platform and
the command. It is built from those values only, never from the process environment,
so it cannot carry ``CUBRID_PASSWORD`` or any other secret.

Usage::

    python3 scripts/report_results.py summarize --lane test --results-dir test-results/test \
        --exit-code 0 [--coverage test-results/test/coverage.xml]
    python3 scripts/report_results.py step-summary --results-dir test-results/test \
        --title "Unit tests (Python 3.12)" >> "$GITHUB_STEP_SUMMARY"
    python3 scripts/report_results.py environment --lane integration \
        --results-dir test-results/integration --command "..." --cubrid-version 11.4
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
COUNTS = ("selected", "passed", "failed", "errors", "skipped", "xfailed", "xpassed")


def _outcome(case: ET.Element) -> str:
    if case.find("error") is not None:
        return "errors"
    if case.find("failure") is not None:
        return "failed"
    if (skipped := case.find("skipped")) is not None:
        return "xfailed" if skipped.get("type") == "pytest.xfail" else "skipped"
    return "passed"


# When a test fails and its teardown also errors, pytest writes two <testcase>
# records for it; count each test once, with its worst outcome.
_SEVERITY = {"passed": 0, "xfailed": 1, "skipped": 2, "failed": 3, "errors": 4}


def parse_junit(path: Path) -> dict[str, int] | None:
    """Count the tests of a JUnit file; None if it is missing or unreadable."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    outcomes: dict[tuple[str, str], str] = {}
    for case in root.iter("testcase"):
        key = (case.get("classname", ""), case.get("name", ""))
        outcome = _outcome(case)
        if key not in outcomes or _SEVERITY[outcome] > _SEVERITY[outcomes[key]]:
            outcomes[key] = outcome
    counts = dict.fromkeys(COUNTS, 0)
    counts["selected"] = len(outcomes)
    for outcome in outcomes.values():
        counts[outcome] += 1
    return counts


def parse_coverage(path: Path) -> float | None:
    """Line coverage percent from a Cobertura ``coverage.xml``; None if unavailable."""
    try:
        rate = ET.parse(path).getroot().get("line-rate")
        return None if rate is None else round(float(rate) * 100, 2)
    except (OSError, ET.ParseError, ValueError):
        return None


def decide(counts: dict[str, int] | None, exit_code: int) -> str:
    if counts is None:
        return "FAIL" if exit_code else "INCOMPLETE"
    if counts["failed"] or counts["errors"]:
        return "FAIL"
    if counts["passed"] == 0:
        return "INCOMPLETE"
    return "FAIL" if exit_code else "PASS"


def build_summary(lane: str, junit: Path, coverage: Path | None, exit_code: int) -> dict[str, Any]:
    counts = parse_junit(junit)
    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "lane": lane,
        "status": decide(counts, exit_code),
        "exit_code": exit_code,
        "counts": counts if counts is not None else dict.fromkeys(COUNTS, 0),
    }
    if coverage is not None:
        percent = parse_coverage(coverage)
        if percent is not None:
            summary["coverage"] = {"line_percent": percent}
    return summary


def console_line(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    parts = [f"{name}={counts[name]}" for name in COUNTS]
    if "coverage" in summary:
        parts.append(f"coverage={summary['coverage']['line_percent']:.2f}%")
    return f"{summary['lane']}: {summary['status']} " + " ".join(parts)


def step_summary(results: Path, title: str | None) -> str:
    """Markdown for ``$GITHUB_STEP_SUMMARY``: the console line of ``summary.json``."""
    heading = f"### {title or 'Test results'}\n\n"
    try:
        summary = json.loads((results / "summary.json").read_text())
        line = console_line(summary)
    except (OSError, ValueError, KeyError, TypeError):
        return f"{heading}No readable `{results / 'summary.json'}` was written (the run stopped early).\n"
    return f"{heading}`{line}`\n"


def package_version() -> str:
    text = (ROOT / "cubrid_mcp_server" / "__init__.py").read_text()
    match = re.search(r'^__version__ = "([^"]+)"', text, re.M)
    return match.group(1) if match else "unknown"


def build_environment(lane: str, command: str, cubrid_version: str | None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lane": lane,
        "command": command,
        "python": platform.python_version(),
        "package": {"name": "cubrid-mcp-server", "version": package_version()},
        "cubrid_version": cubrid_version,
        "platform": platform.platform(),
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    sub = parser.add_subparsers(dest="action", required=True)
    summarize = sub.add_parser("summarize", help="write summary.json and print one line")
    environment = sub.add_parser("environment", help="write environment.json")
    step = sub.add_parser("step-summary", help="print summary.json as Markdown")
    step.add_argument("--results-dir", required=True, type=Path)
    step.add_argument("--title", help="heading, e.g. the matrix entry")
    for p in (summarize, environment):
        p.add_argument("--lane", required=True)
        p.add_argument("--results-dir", required=True, type=Path)
    summarize.add_argument("--exit-code", required=True, type=int)
    summarize.add_argument("--junit", type=Path, help="default: <results-dir>/junit.xml")
    summarize.add_argument("--coverage", type=Path, help="coverage.xml, when measured")
    environment.add_argument("--command", required=True)
    environment.add_argument("--cubrid-version")
    args = parser.parse_args(argv)

    results: Path = args.results_dir
    if args.action == "step-summary":
        print(step_summary(results, args.title), end="")
        return 0
    if args.action == "environment":
        data = build_environment(args.lane, args.command, args.cubrid_version)
        _write_json(results / "environment.json", data)
        return 0
    summary = build_summary(
        args.lane, args.junit or results / "junit.xml", args.coverage, args.exit_code
    )
    _write_json(results / "summary.json", summary)
    print(f"{console_line(summary)} -> {results / 'summary.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
