#!/usr/bin/env python3
"""Check editorial quality of one release candidate without publishing anything.

Older published versions remain untouched: release history requires its own
version-scoped review and safeguarded body-only synchronization.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HEAD = re.compile(r"^## \[([^\]]+)\][^\n]*$", re.MULTILINE)
SECTION = re.compile(r"^### (.+)$", re.MULTILINE)
BULLET = re.compile(r"^[-*] ", re.MULTILINE)
RAW = re.compile(r"^\* |^- \*\*(?:feat|fix|docs|ci|test|chore):", re.I)
PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|PLACEHOLDER)\b", re.I)
# 0.8.0 and older were published before this editorial gate. Their read-only
# audit and any body-only corrections are handled separately.
CUTOFF = (0, 8, 0)


def release_section(changelog: str, version: str) -> str:
    """Extract only the exact requested version and reject missing versions."""
    matches = list(HEAD.finditer(changelog))
    for i, match in enumerate(matches):
        if match.group(1) == version:
            end = matches[i + 1].start() if i + 1 < len(matches) else len(changelog)
            return changelog[match.end():end]
    raise ValueError(f"release [{version}] not found in CHANGELOG")


def violations(body: str) -> list[str]:
    """Return objective problems; a maintainer must also verify facts and credits."""
    errors: list[str] = []
    headings = list(SECTION.finditer(body))
    if not headings:
        return ["missing categorized ### changes"]
    intro = " ".join(body[:headings[0].start()].split())
    if not intro:
        errors.append("missing introductory user-impact summary")
    elif len(intro) > 900:
        errors.append("introductory summary exceeds 900 visible characters")
    seen: set[str] = set()
    count = 0
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        title = match.group(1)
        chunk = body[match.end():end]
        entries = [line.strip() for line in chunk.splitlines() if BULLET.match(line)]
        if not entries:
            errors.append(f"empty section {title}")
        for line in entries:
            count += 1
            if RAW.match(line):
                errors.append(f"uncurated generated bullet in {title}; summarize outcome and cite evidence")
            key = re.sub(r"\s+", " ", line.casefold())
            if key in seen:
                errors.append(f"duplicate bullet in {title}")
            seen.add(key)
    if not count:
        errors.append("no change entries")
    if PLACEHOLDER.search(body):
        errors.append("unresolved placeholder in release notes")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", required=True, help="exact X.Y.Z candidate")
    parser.add_argument("--changelog", default="CHANGELOG.md")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        parser.error("--version must be X.Y.Z")
    version = tuple(int(v) for v in args.version.split("."))
    if version <= CUTOFF:
        print(f"Historical v{args.version}: editorial gate not retroactive")
        return 0
    try:
        section = release_section(Path(args.changelog).read_text(encoding="utf-8"), args.version)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    errors = violations(section)
    for message in errors:
        print(f"ERROR: v{args.version}: {message}", file=sys.stderr)
    if errors:
        return 1
    print(f"OK: reviewed editorial structure for v{args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
