#!/usr/bin/env python3
"""Review-gated body-only repair for five existing early MCP GitHub Releases.

Default is a read-only diff. This is deliberately not wired to a push or
release workflow. An authorized maintainer must arrange a serialized editing
window, approve a pinned canonical source and execute one tag at a time.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = "cubrid-lab/cubrid-mcp-server"
EARLY_TAGS = ("v0.1.0", "v0.2.1", "v0.3.0", "v0.3.1", "v0.4.0")
IDENTITY_FIELDS = (
    "id",
    "tag_name",
    "name",
    "draft",
    "prerelease",
    "published_at",
    "created_at",
    "target_commitish",
)
ASSET_FIELDS = ("id", "name", "label", "size", "state", "content_type", "digest")


def digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def identity(release: dict) -> dict:
    """Preserve public identity and asset metadata, not mutable update times."""
    return {
        **{field: release.get(field) for field in IDENTITY_FIELDS},
        "assets": sorted(
            (
                {field: asset.get(field) for field in ASSET_FIELDS}
                for asset in release.get("assets", [])
            ),
            key=lambda item: item["id"],
        ),
    }


def check_public(release: dict, tag: str) -> None:
    if (
        not isinstance(release, dict)
        or release.get("tag_name") != tag
        or release.get("draft") is not False
        or release.get("prerelease") is not False
        or not release.get("published_at")
        or not isinstance(release.get("id"), int)
        or not isinstance(release.get("body"), str)
        or not isinstance(release.get("assets"), list)
    ):
        raise ValueError(f"{tag}: expected a complete, published stable Release")


def api(path: str, body: dict | None = None) -> dict:
    command = ["gh", "api"]
    if body is not None:
        command.extend(("--method", "PATCH", "--input", "-"))
    command.append(path)
    completed = subprocess.run(
        command,
        input=json.dumps(body) if body is not None else None,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def source_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()


def source_is_clean() -> bool:
    return not subprocess.check_output(
        ["git", "status", "--porcelain"], text=True
    ).strip()


def canonical_body(tag: str) -> str:
    """Use the existing release extractor, not a second changelog parser."""
    script = Path(__file__).resolve().with_name("extract_release_notes.py")
    changelog = Path("CHANGELOG.md")
    with tempfile.TemporaryDirectory(prefix="mcp-release-body-") as directory:
        workdir = Path(directory)
        (workdir / "CHANGELOG.md").write_bytes(changelog.read_bytes())
        subprocess.run(
            [sys.executable, str(script), tag],
            cwd=workdir,
            text=True,
            capture_output=True,
            check=True,
        )
        return (workdir / "RELEASE_NOTES.md").read_text(encoding="utf-8")


def save_backup(release: dict, tag: str, directory: Path) -> Path:
    """Fail rather than overwrite a prior backup, and verify its contents."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{tag}-{release['id']}-original.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(release, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if json.loads(path.read_text(encoding="utf-8")) != release:
        raise ValueError(f"{tag}: written backup did not round-trip")
    return path


def run(args: argparse.Namespace) -> None:
    if args.apply:
        if not all((
            args.approved_body_only,
            args.source_sha,
            args.expected_remote_sha256,
            args.backup_dir,
            args.exclusive_edit_window,
        )):
            raise ValueError(
                "apply requires independently approved source SHA, expected "
                "remote body SHA-256, backup directory, body-only approval and "
                "a maintainer-confirmed exclusive editing window"
            )
        if source_head() != args.source_sha or not source_is_clean():
            raise ValueError("apply needs a clean checkout at the approved SHA")

    proposed = canonical_body(args.tag)
    public = api(f"repos/{REPO}/releases/tags/{args.tag}")
    check_public(public, args.tag)
    old_body = public["body"]
    print(
        f"{args.tag}: current body SHA-256={digest(old_body)}, "
        f"canonical SHA-256={digest(proposed)}"
    )
    if old_body == proposed:
        print("Already equal; no write is needed.")
        return

    print("".join(difflib.unified_diff(
        old_body.splitlines(keepends=True),
        proposed.splitlines(keepends=True),
        fromfile="published body",
        tofile="approved canonical body",
    )))

    if not args.apply:
        print("Dry-run only. Public GitHub Release was not changed.")
        return

    if digest(old_body) != args.expected_remote_sha256:
        raise ValueError("Published body differs from the reviewed digest")
    backup = save_backup(public, args.tag, args.backup_dir)
    print(f"Original public Release JSON backed up to {backup}")

    # Re-read immediately before mutation; GitHub REST PATCH has no atomic
    # compare-and-swap for Release bodies. The required exclusive editing
    # window must therefore be established by the maintainer externally.
    latest = api(f"repos/{REPO}/releases/{public['id']}")
    check_public(latest, args.tag)
    if (
        identity(latest) != identity(public)
        or latest["body"] != old_body
        or latest.get("updated_at") != public.get("updated_at")
    ):
        raise ValueError("Remote Release drifted since review; no PATCH sent")

    updated = api(f"repos/{REPO}/releases/{public['id']}", {"body": proposed})
    fetched = api(f"repos/{REPO}/releases/{public['id']}")
    for result in (updated, fetched):
        check_public(result, args.tag)
        if result["body"] != proposed or identity(result) != identity(public):
            raise ValueError(
                "Post-write verification failed; inspect the public Release "
                "and backup before any further edit"
            )
    print(f"{args.tag}: verified body-only PATCH and fresh remote readback")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, choices=EARLY_TAGS)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approved-body-only", action="store_true")
    parser.add_argument("--exclusive-edit-window", action="store_true")
    parser.add_argument("--source-sha")
    parser.add_argument("--expected-remote-sha256")
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    try:
        run(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
