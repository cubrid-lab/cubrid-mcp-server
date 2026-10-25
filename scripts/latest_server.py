#!/usr/bin/env python3
"""Weekly newest-stable CUBRID image check and per-cell image evidence (#417).

``integration-full.yml`` tests the reviewed supported series (``cubrid/cubrid:10.2``
to ``cubrid/cubrid:11.4``). Two pieces of evidence come from this script:

* ``record`` - each matrix cell, after ``make integration``, writes the exact image
  it ran (``cubrid/cubrid@sha256:...`` digest) and that image's engine version
  (``cubrid_rel``) to its step summary. Evidence only: it always exits 0.
* ``resolve`` - the advisory ``latest-server`` job pulls the moving ``latest`` tag
  and the newest supported series tag (``SERIES_TAG``) once, reads each digest and
  engine version, and classifies them:

  - ``same-image`` - same digest: the newest published image is that digest and no
    duplicate database starts. The run's CUBRID 11.4 cells record the image they
    actually ran; they tested the newest image only if they show the same digest
    (they pull the tag separately).
  - ``not-newer`` - another digest whose engine build is not newer than 11.4 (for
    example a ``latest`` alias that has not moved yet): nothing extra to test.
  - ``newer`` - ``latest`` is a newer engine build: an advisory canary runs the
    live suite on its immutable digest reference. It never changes the required
    cells, the documented support set or the release matrix.
  - ``unverified`` - a pull, digest or version lookup failed or was malformed: the
    newest-server check is inconclusive and never reported as passed.

  ``resolve`` prints the Markdown summary and writes ``status``, ``canary`` and
  ``image`` to ``--output`` (``$GITHUB_OUTPUT``).
* ``report`` - appends the canary step's outcome to ``--summary``, annotates an
  unverified lookup or a failed canary, and fails only when a newer image was found
  and its canary did not pass. The job is ``continue-on-error``, so a failure shows
  on the run without failing the matrix result or any release.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

IMAGE = "cubrid/cubrid"
SERIES_TAG = "11.4"
DIGEST_REF = re.compile(rf"{re.escape(IMAGE)}@sha256:[0-9a-f]{{64}}")
# cubrid_rel: "CUBRID 11.4.6 (11.4.6.1963-0e7d3c1) (64bit release build for Linux) ..."
BUILD = re.compile(r"\((\d+)\.(\d+)\.(\d+)\.(\d+)-[0-9a-f]+\)")
DOCKER_TIMEOUT = 600


def _docker(*args: str) -> str:
    """``docker <args>`` stdout, or "" when docker is missing, fails or times out."""
    try:
        completed = subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=DOCKER_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def inspect(image: str) -> tuple[str, str]:
    """The local image's digest reference and its ``cubrid_rel`` output ("" if unknown)."""
    ref = _docker("image", "inspect", "--format", "{{index .RepoDigests 0}}", image)
    if not DIGEST_REF.fullmatch(ref):
        return "", ""
    rel = _docker("run", "--rm", "--entrypoint", "bash", ref, "-lc", "cubrid_rel")
    return ref, " ".join(rel.split())


def pull(tag: str) -> tuple[str, str]:
    """Pull ``IMAGE:tag`` and return its digest reference and ``cubrid_rel`` output."""
    image = f"{IMAGE}:{tag}"
    if not _docker("pull", "-q", image):
        return "", ""
    return inspect(image)


def build(rel: str) -> tuple[int, ...] | None:
    """The four-part engine build from ``cubrid_rel`` output, or None."""
    match = BUILD.search(rel)
    return tuple(int(part) for part in match.groups()) if match else None


def version(rel: str) -> str:
    found = build(rel)
    return ".".join(map(str, found)) if found else "unknown"


def decide(latest_ref: str, latest_rel: str, series_ref: str, series_rel: str) -> dict[str, str]:
    """Classify the resolved images; see the module docstring for the statuses."""
    latest, series = build(latest_rel), build(series_rel)
    valid_refs = DIGEST_REF.fullmatch(latest_ref) and DIGEST_REF.fullmatch(series_ref)
    if not valid_refs or latest is None or series is None:
        status = "unverified"
    elif latest_ref == series_ref:
        status = "same-image"
    elif latest > series:
        status = "newer"
    else:
        status = "not-newer"
    return {
        "status": status,
        "canary": "true" if status == "newer" else "false",
        "image": latest_ref if status == "newer" else "",
    }


def describe(
    decision: dict[str, str],
    latest_ref: str,
    latest_rel: str,
    series_ref: str,
    series_rel: str,
    date: str,
) -> str:
    status = decision["status"]
    lines = [
        "### Newest CUBRID image (advisory)",
        "",
        f"Checked {date or 'unknown date'}.",
        "",
        "| Tag | Image | Engine |",
        "|-----|-------|--------|",
        f"| `latest` | `{latest_ref or 'not resolved'}` | {version(latest_rel)} |",
        f"| `{SERIES_TAG}` | `{series_ref or 'not resolved'}` | {version(series_rel)} |",
        "",
    ]
    if status == "same-image":
        lines.append(
            f"`latest` and `{SERIES_TAG}` resolved to the same image: the newest-stable image"
            f" is `{latest_ref}`. This run's CUBRID {SERIES_TAG} matrix cells record the image"
            " they actually ran in their own summaries; they tested the newest-stable image"
            " only if they show this same digest. No extra database started."
        )
    elif status == "not-newer":
        lines.append(
            f"`latest` is a different image but not a newer engine build than `{SERIES_TAG}`;"
            " nothing extra to test."
        )
    elif status == "newer":
        lines.append(
            f"`latest` is a newer engine build than `{SERIES_TAG}`: an advisory canary tests"
            f" `{decision['image']}`. It is not part of the supported versions or the release"
            " matrix and is never promoted automatically."
        )
    else:
        lines.append(
            "UNVERIFIED: the newest-image lookup failed or returned malformed data, so"
            " the newest CUBRID release was not checked this run. The supported-version"
            " matrix cells are unaffected."
        )
    return "\n".join(lines) + "\n"


def report(status: str, image: str, outcome: str) -> tuple[int, str, str]:
    """Exit code, summary line and annotation for a ``resolve`` status and canary outcome."""
    if status == "newer":
        if outcome == "success":
            return 0, f"Advisory canary on `{image}`: passed.", ""
        return (
            1,
            (
                f"Advisory canary on `{image}`: did not pass (outcome: {outcome or 'none'});"
                " the newer CUBRID release is NOT verified."
            ),
            "::error::Advisory canary on the newer CUBRID image did not pass",
        )
    if status in ("same-image", "not-newer"):
        return 0, "No advisory canary needed.", ""
    return (
        0,
        "Newest CUBRID image: UNVERIFIED this run; no newest-server result is claimed.",
        "::warning::Newest CUBRID image lookup is unverified this run",
    )


def record_line(tag: str, ref: str, rel: str) -> str:
    return f"CUBRID image: `{IMAGE}:{tag}` -> `{ref or 'unresolved'}` (engine {version(rel)})\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Newest CUBRID image check (#417)")
    commands = parser.add_subparsers(dest="command", required=True)
    record = commands.add_parser("record", help="record the image a matrix cell ran")
    record.add_argument("--tag", required=True, help="cubrid/cubrid tag the cell used")
    record.add_argument("--summary", type=Path, required=True, help="$GITHUB_STEP_SUMMARY")
    resolve = commands.add_parser("resolve", help="pull and classify latest and the series")
    resolve.add_argument("--date", default="")
    resolve.add_argument("--output", type=Path, required=True, help="$GITHUB_OUTPUT")
    final = commands.add_parser("report", help="report the canary outcome")
    final.add_argument("--status", default="")
    final.add_argument("--image", default="")
    final.add_argument("--outcome", default="")
    final.add_argument("--summary", type=Path, required=True, help="$GITHUB_STEP_SUMMARY")
    args = parser.parse_args(argv)

    if args.command == "record":
        line = record_line(args.tag, *inspect(f"{IMAGE}:{args.tag}"))
        with args.summary.open("a", encoding="utf-8") as summary:
            summary.write(line)
        sys.stdout.write(line)
        return 0
    if args.command == "resolve":
        refs = (*pull("latest"), *pull(SERIES_TAG))
        decision = decide(*refs)
        with args.output.open("a", encoding="utf-8") as output:
            output.writelines(f"{key}={value}\n" for key, value in decision.items())
        sys.stdout.write(describe(decision, *refs, args.date))
        return 0
    code, line, annotation = report(args.status, args.image, args.outcome)
    with args.summary.open("a", encoding="utf-8") as summary:
        summary.write(f"\n{line}\n")
    print(annotation or line)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
