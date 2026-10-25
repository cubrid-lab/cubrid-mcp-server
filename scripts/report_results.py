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
so an exported ``CUBRID_PASSWORD`` or other secret variable never reaches it. The
command is the caller's own string (``make integration`` passes its ``--pytest``
value), so before it is written ``redact_command`` masks credentials embedded in it
(#426): the password of URL userinfo (``scheme://user:***@host``) and the value of a
``password``, ``passwd``, ``pwd``, ``token``, ``secret``, ``api_key`` or ``apikey``
assignment or option, case-insensitively and also as a key suffix (``PASSWORD=***``,
``CUBRID_PASSWORD=***``, ``--password=***``, ``--password ***``, ``--api-key ***``).
Everything else is kept byte for byte. The masking is a regular-expression safety net,
not a shell parser: a bare token or a short option (``-p secret``), a URL user name or
a user-only ``scheme://token@host``, a URL password with an unencoded ``/``, ``?`` or
``#`` (``scheme://user:p/ss@host``), and a quoted value that contains whitespace after
an unquoted key (``"--password=a b"``) are not recognized, and a dashed credential flag
that takes no value masks the next word (``--no-token tests`` -> ``--no-token ***``).
Supply secrets through environment variables or the CI secret store, never on the
command line, which other processes and logs can also see.

``aggregate`` writes ``make verify``'s ``test-results/verify/summary.json`` (#449) from
its phases, in order: ``--phase NAME=EXIT`` (or ``NAME=not-run``), optionally with
``:SUMMARY`` naming the phase's own ``summary.json``. A phase is ``PASS`` only when it
exited 0 and its summary (when it has one) has the status ``PASS``; ``NOT_RUN`` when it
never started. ``verify`` is ``FAIL`` when a phase failed, ``INCOMPLETE`` when one did
not run, proved nothing or has a missing, unreadable or non-string summary status, and
``PASS`` otherwise. ``--copy-junit NAME=PATH`` copies a lane's JUnit file to
``junit/NAME.xml`` and ``--environment PATH`` the live lane's ``environment.json``; the
configured connection passwords (``CUBRID_PASSWORD`` and the ``CUBRID_<NAME>_PASSWORD``
of every connection in ``CUBRID_CONNECTIONS``, as the server reads them, also
percent-encoded and XML-escaped) are replaced with ``***`` in every copy, and a file
that cannot be copied keeps the summary from ``PASS``. It exits 0 only for ``PASS``.

Usage::

    python3 scripts/report_results.py summarize --lane test --results-dir test-results/test \
        --exit-code 0 [--coverage test-results/test/coverage.xml]
    python3 scripts/report_results.py step-summary --results-dir test-results/test \
        --title "Unit tests (Python 3.12)" >> "$GITHUB_STEP_SUMMARY"
    python3 scripts/report_results.py environment --lane integration \
        --results-dir test-results/integration --command "..." --cubrid-version 11.4
    python3 scripts/report_results.py aggregate --output test-results/verify/summary.json \
        --phase check=0 --phase test=1:test-results/test/summary.json \
        --phase integration=not-run --copy-junit test=test-results/test/junit.xml
"""

from __future__ import annotations

import argparse
import html
import json
import os
import platform
import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
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
    if "phases" in summary:
        return aggregate_line(summary)
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


MASK = "***"
# scheme://user:password@ -> keep the scheme, the user and "@"; the password ends at the
# last "@" before whitespace, a quote, "/", "?" or "#" (RFC 3986 requires those, and any
# "@" inside it, to be percent-encoded, so an encoded "%40" stays part of the password).
_URL_PASSWORD = re.compile(
    r"(?P<head>(?<![A-Za-z0-9+.-])[A-Za-z][A-Za-z0-9+.-]*://[^\s'\"/?#@:]*:)[^\s'\"/?#]+(?=@)"
)
# A key that is, or ends with, a credential word: at the start of the command or after
# whitespace, a quote, ";", "&" or "?", with or without leading dashes.
_KEY = r"(?<![^\s'\";&?])-{0,2}[A-Za-z0-9_.-]*?(?:password|passwd|pwd|token|secret|api[_-]?key)"
# An unquoted value ends where the shell would end the word: whitespace, a quote, ";" or
# "&" (so a URL query keeps its other parameters).
_VALUE = r"""(?P<value>'[^']*'|"[^"]*"|[^\s'";&]+)"""
# KEY=value, --key=value and, only for a dashed option, "--key value".
_ASSIGNMENT = re.compile(rf"(?P<key>{_KEY}=|(?=-){_KEY}\s+(?=[^\s-]))" + _VALUE, re.IGNORECASE)


def _mask_value(match: re.Match[str]) -> str:
    value = match["value"]
    quote = value[0] if value[0] in "'\"" else ""
    return f"{match['key']}{quote}{MASK}{quote}"


def redact_command(command: str) -> str:
    """Mask URL passwords and credential assignments; leave everything else unchanged."""
    command = _ASSIGNMENT.sub(_mask_value, command)
    if "://" not in command:
        return command
    return _URL_PASSWORD.sub(lambda m: m["head"] + MASK, command)


def build_environment(lane: str, command: str, cubrid_version: str | None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lane": lane,
        "command": redact_command(command),
        "python": platform.python_version(),
        "package": {"name": "cubrid-mcp-server", "version": package_version()},
        "cubrid_version": cubrid_version,
        "platform": platform.platform(),
    }


STATUSES = ("PASS", "FAIL", "INCOMPLETE")


def _phase_status(path: Path) -> tuple[str | None, str]:
    """The ``status`` of a lane's ``summary.json`` and a problem when it is unusable."""
    try:
        status = json.loads(path.read_text())["status"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, f"cannot read {path}: {exc}"
    if not isinstance(status, str) or status not in STATUSES:
        return None, f"{path} has an unknown status {status!r}"
    return status, ""


def build_aggregate(
    phases: Sequence[tuple[str, int | None, Path | None]], problems: Sequence[str] = ()
) -> dict[str, Any]:
    """``make verify``'s summary: one entry per phase, in the order given.

    *problems* (a result file that could not be copied) keep it from ``PASS``.
    """
    entries: list[dict[str, Any]] = []
    found = list(problems)
    for name, exit_code, summary_path in phases:
        lane_status: str | None = None
        if exit_code is None:
            status = "NOT_RUN"
            found.append(f"{name} did not run")
        else:
            if summary_path is not None:
                lane_status, problem = _phase_status(summary_path)
                if problem:
                    found.append(f"{name}: {problem}")
            if exit_code != 0 or lane_status == "FAIL":
                status = "FAIL"
            elif summary_path is not None and lane_status != "PASS":
                status = "INCOMPLETE"
                if lane_status == "INCOMPLETE":
                    found.append(f"{name} is INCOMPLETE")
            else:
                status = "PASS"
        entries.append(
            {
                "name": name,
                "status": status,
                "exit_code": exit_code,
                "summary": None if summary_path is None else str(summary_path),
                "summary_status": lane_status,
            }
        )
    statuses = {entry["status"] for entry in entries}
    if not entries:
        overall = "INCOMPLETE"
        found.append("no phase was given")
    elif "FAIL" in statuses:
        overall = "FAIL"
    elif statuses == {"PASS"} and not problems:
        overall = "PASS"
    else:
        overall = "INCOMPLETE"
    return {
        "schema_version": SCHEMA_VERSION,
        "lane": "verify",
        "status": overall,
        "phases": entries,
        "problems": found,
    }


def aggregate_line(summary: dict[str, Any]) -> str:
    parts = [f"{phase['name']}={phase['status']}" for phase in summary["phases"]]
    line = f"{summary['lane']}: {summary['status']} " + " ".join(parts)
    if summary["problems"]:
        line += " [" + "; ".join(str(p) for p in summary["problems"]) + "]"
    return line


def configured_secrets(environ: Mapping[str, str]) -> list[str]:
    """Every configured connection password in each written form, longest first.

    The password variables are the ones the server reads (``ConnectionRegistry.from_env``):
    ``CUBRID_PASSWORD`` and ``CUBRID_<NAME>_PASSWORD`` for each name in
    ``CUBRID_CONNECTIONS``.
    """
    names = ["CUBRID_PASSWORD"]
    for part in environ.get("CUBRID_CONNECTIONS", "").split(","):
        if part.strip():
            names.append(f"CUBRID_{part.strip().upper()}_PASSWORD")
    forms: set[str] = set()
    for secret in filter(None, (environ.get(name, "") for name in names)):
        for form in (secret, urllib.parse.unquote(secret), urllib.parse.quote(secret, safe="")):
            forms.update((form, html.escape(form), html.escape(form, quote=False)))
    return sorted(filter(None, forms), key=len, reverse=True)


def scrub(data: bytes, secrets: Sequence[str]) -> bytes:
    """Replace every form of the configured secrets in *data* with ``***``."""
    for secret in secrets:
        data = data.replace(secret.encode(), MASK.encode())
    return data


def _parse_phase(text: str) -> tuple[str, int | None, Path | None]:
    name, sep, rest = text.partition("=")
    if not name or not sep:
        raise argparse.ArgumentTypeError(f"expected NAME=EXIT[:SUMMARY], got {text!r}")
    code, _, path = rest.partition(":")
    if code == "not-run":
        return name, None, Path(path) if path else None
    try:
        return name, int(code), Path(path) if path else None
    except ValueError:
        raise argparse.ArgumentTypeError(f"bad exit status in {text!r}") from None


def _parse_pair(text: str) -> tuple[str, Path]:
    name, sep, path = text.partition("=")
    if not name or not sep or not path:
        raise argparse.ArgumentTypeError(f"expected NAME=PATH, got {text!r}")
    return name, Path(path)


def aggregate(
    output: Path,
    phases: Sequence[tuple[str, int | None, Path | None]],
    junits: Sequence[tuple[str, Path]],
    environment: Path | None,
) -> dict[str, Any]:
    """Copy the lanes' files next to *output* (masked) and write the aggregate summary."""
    directory = output.parent
    directory.mkdir(parents=True, exist_ok=True)
    secrets = configured_secrets(os.environ)
    copies = [(junit, directory / "junit" / f"{name}.xml") for name, junit in junits]
    if environment is not None:
        copies.append((environment, directory / "environment.json"))
    problems = []
    for source, target in copies:
        if not source.exists():
            continue
        try:
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(scrub(source.read_bytes(), secrets))
        except OSError as exc:
            target.unlink(missing_ok=True)
            problems.append(f"could not copy {source}: {exc}")
    summary = build_aggregate(phases, problems)
    _write_json(output, summary)
    return summary


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    sub = parser.add_subparsers(dest="action", required=True)
    summarize = sub.add_parser("summarize", help="write summary.json and print one line")
    environment = sub.add_parser("environment", help="write environment.json")
    agg = sub.add_parser("aggregate", help="write make verify's summary.json")
    agg.add_argument("--output", required=True, type=Path, help="summary.json to write")
    agg.add_argument("--phase", action="append", default=[], type=_parse_phase)
    agg.add_argument("--copy-junit", action="append", default=[], type=_parse_pair)
    agg.add_argument("--environment", type=Path, help="the live lane's environment.json")
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

    if args.action == "aggregate":
        summary = aggregate(args.output, args.phase, args.copy_junit, args.environment)
        print(f"{console_line(summary)} -> {args.output}", flush=True)
        return 0 if summary["status"] == "PASS" else 1
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
