#!/usr/bin/env python3
"""Turn ``## [Unreleased]`` into a dated release section and bump the version.

Historical offline utility: ``prepare-release.yml`` ran this before opening the release
PR until release-please took over preparation (#254); no workflow runs it now:

* ``CHANGELOG.md``: the entries under ``## [Unreleased]`` move under a new
  ``## [X.Y.Z] - YYYY-MM-DD`` heading; an empty ``## [Unreleased]`` stays on top.
* every ``--version-file``: the single ``__version__ = "..."`` assignment is
  set to ``X.Y.Z`` (repositories list their extra version files here). A
  ``.json`` version file is an MCP Registry ``server.json``: its top-level
  ``version`` and every ``packages[].version`` are set instead.

Refuses (exit 1, nothing written) when the version is not ``MAJOR.MINOR.PATCH``,
is not greater than the current ``__version__`` of the first version file, the
CHANGELOG already has a ``[X.Y.Z]`` section, ``[Unreleased]`` is missing or
empty, or a version file does not hold exactly one ``__version__`` string (a
``.json`` file: one version shared by all of those fields).

Standard library only; kept identical across pycubrid, sqlalchemy-cubrid and
cubrid-mcp-server (see RELEASING.md), except that cubrid-mcp-server adds the
``.json`` version file for ``.mcpb/server.json``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

VERSION_RE = re.compile(r"^([0-9]+)\.([0-9]+)\.([0-9]+)$")
ASSIGN_RE = re.compile(r"""^(__version__\s*=\s*)(["'])([^"']*)\2""", re.MULTILINE)
UNRELEASED_RE = re.compile(r"^## \[Unreleased\][^\n]*\n", re.MULTILINE)
SECTION_RE = re.compile(r"^## \[", re.MULTILINE)


class PrepareError(Exception):
    pass


def version_key(version: str) -> tuple[int, int, int]:
    match = VERSION_RE.match(version)
    if not match:
        raise PrepareError(f"{version!r} is not MAJOR.MINOR.PATCH")
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def bump_version_file(text: str, version: str, path: str) -> tuple[str, str]:
    matches = ASSIGN_RE.findall(text)
    if len(matches) != 1:
        raise PrepareError(f"{path}: expected exactly one __version__ string, found {len(matches)}")
    current = matches[0][2]
    return ASSIGN_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{version}{m.group(2)}", text), current


def bump_server_json(text: str, version: str, path: str) -> tuple[str, str]:
    try:
        data = json.loads(text)
        fields = [data] + list(data["packages"])
        found = {entry["version"] for entry in fields}
    except (ValueError, TypeError, KeyError) as exc:
        raise PrepareError(
            f"{path}: expected a top-level and a packages[] version ({exc!r})"
        ) from exc
    if len(fields) < 2 or len(found) != 1 or not all(isinstance(value, str) for value in found):
        raise PrepareError(
            f"{path}: expected one version string in version and packages[].version, "
            f"found {sorted(map(str, found))}"
        )
    for entry in fields:
        entry["version"] = version
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n", found.pop()


def date_changelog(text: str, version: str, date: str) -> str:
    if re.search(rf"^## \[{re.escape(version)}\]", text, re.MULTILINE):
        raise PrepareError(f"CHANGELOG already has a [{version}] section")
    header = UNRELEASED_RE.search(text)
    if not header:
        raise PrepareError("CHANGELOG has no '## [Unreleased]' section")
    following = SECTION_RE.search(text, header.end())
    end = following.start() if following else len(text)
    body = text[header.end() : end].strip("\n")
    if not body.strip():
        raise PrepareError("'## [Unreleased]' is empty; nothing to release")
    return (
        text[: header.end()]
        + f"\n## [{version}] - {date}\n\n"
        + body
        + ("\n\n" if following else "\n")
        + text[end:]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", required=True)
    parser.add_argument("--version-file", action="append", required=True)
    parser.add_argument("--changelog", default="CHANGELOG.md")
    parser.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"))
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        target = version_key(args.version)
        if not re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", args.date):
            raise PrepareError(f"--date {args.date!r} is not YYYY-MM-DD")
        updates: dict[Path, str] = {}
        for index, name in enumerate(args.version_file):
            path = Path(name)
            bump = bump_server_json if path.suffix == ".json" else bump_version_file
            new_text, current = bump(path.read_text(encoding="utf-8"), args.version, name)
            if index == 0 and version_key(current) >= target:
                raise PrepareError(
                    f"{args.version} is not greater than the current version {current}"
                )
            updates[path] = new_text
        changelog = Path(args.changelog)
        updates[changelog] = date_changelog(
            changelog.read_text(encoding="utf-8"), args.version, args.date
        )
    except (PrepareError, OSError) as exc:
        print(f"::error::{exc}")
        return 1
    for path, text in updates.items():
        path.write_text(text, encoding="utf-8")
        print(f"updated {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
