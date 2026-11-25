"""Guards for historical MCP Release body repair; all API effects are mocked."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "reconcile_historical_release_bodies",
    ROOT / "scripts" / "reconcile_historical_release_bodies.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def release(body: str = "old") -> dict:
    return {
        "id": 308336131,
        "tag_name": "v0.1.0",
        "name": "v0.1.0",
        "body": body,
        "draft": False,
        "prerelease": False,
        "published_at": "2026-04-13T13:03:23Z",
        "created_at": "2026-04-13T13:01:00Z",
        "updated_at": "2026-11-18T00:00:00Z",
        "target_commitish": "main",
        "assets": [
            {
                "id": 12,
                "name": "original.zip",
                "label": None,
                "size": 55,
                "state": "uploaded",
                "content_type": "application/zip",
            }
        ],
    }


def args(tmp_path, **changes):
    options = {
        "tag": "v0.1.0",
        "apply": True,
        "approved_body_only": True,
        "exclusive_edit_window": True,
        "source_sha": "a" * 40,
        "expected_remote_sha256": MODULE.digest("old"),
        "expected_canonical_sha256": MODULE.digest("new"),
        "backup_dir": tmp_path,
    }
    options.update(changes)
    return argparse.Namespace(**options)


def test_does_not_target_versions_without_an_existing_release() -> None:
    assert MODULE.EARLY_TAGS == ("v0.1.0", "v0.2.1", "v0.3.0", "v0.3.1", "v0.4.0")
    assert "v0.2.0" not in MODULE.EARLY_TAGS


def test_identity_includes_assets_but_excludes_body() -> None:
    original = release()
    changed = release("new")
    assert MODULE.identity(original) == MODULE.identity(changed)
    changed["assets"][0]["size"] = 56
    assert MODULE.identity(original) != MODULE.identity(changed)


def test_refuses_unpublished_draft_or_wrong_tag() -> None:
    original = release()
    MODULE.check_public(original, "v0.1.0")
    for change in ({"draft": True}, {"tag_name": "v0.3.0"}):
        changed = {**original, **change}
        with pytest.raises(ValueError, match="published stable Release"):
            MODULE.check_public(changed, "v0.1.0")


def test_backup_cannot_overwrite_and_round_trips(tmp_path) -> None:
    original = release()
    path = MODULE.save_backup(original, "v0.1.0", tmp_path)
    assert json.loads(path.read_text(encoding="utf-8")) == original
    with pytest.raises(FileExistsError):
        MODULE.save_backup(original, "v0.1.0", tmp_path)


def test_apply_without_explicit_approval_aborts_before_network(tmp_path) -> None:
    with pytest.raises(ValueError, match="apply requires"):
        MODULE.run(args(tmp_path, approved_body_only=False))


def test_apply_without_canonical_digest_aborts_before_network(tmp_path) -> None:
    with pytest.raises(ValueError, match="apply requires"):
        MODULE.run(args(tmp_path, expected_canonical_sha256=None))


def test_canonical_digest_mismatch_aborts_before_network(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "canonical_body", lambda tag: "unreviewed")
    monkeypatch.setattr(MODULE, "source_head", lambda: "a" * 40)
    monkeypatch.setattr(MODULE, "source_is_clean", lambda: True)

    def unexpected_api(*args, **kwargs):
        pytest.fail("No API access is allowed for an unreviewed canonical body")

    monkeypatch.setattr(MODULE, "api", unexpected_api)
    with pytest.raises(ValueError, match="canonical body differs"):
        MODULE.run(args(tmp_path))
    assert not list(tmp_path.iterdir())


def test_remote_drift_aborts_before_patch(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "canonical_body", lambda tag: "new")
    monkeypatch.setattr(MODULE, "source_head", lambda: "a" * 40)
    monkeypatch.setattr(MODULE, "source_is_clean", lambda: True)
    requests = []

    def api(path, body=None):
        requests.append((path, body))
        return release("old") if len(requests) == 1 else release("other")

    monkeypatch.setattr(MODULE, "api", api)
    with pytest.raises(ValueError, match="drifted"):
        MODULE.run(args(tmp_path))
    assert len(requests) == 2
    assert all(payload is None for _, payload in requests)
    assert len(list(tmp_path.glob("*-original.json"))) == 1


def test_patch_changes_body_only_and_reads_back(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "canonical_body", lambda tag: "new")
    monkeypatch.setattr(MODULE, "source_head", lambda: "a" * 40)
    monkeypatch.setattr(MODULE, "source_is_clean", lambda: True)
    requests = []

    def api(path, body=None):
        requests.append((path, body))
        if body is not None:
            return release("new")
        return release("old") if len(requests) <= 2 else release("new")

    monkeypatch.setattr(MODULE, "api", api)
    MODULE.run(args(tmp_path))
    assert [payload for _, payload in requests if payload is not None] == [{"body": "new"}]
    assert len(requests) == 4
    assert json.loads(next(tmp_path.glob("*-original.json")).read_text()) == release("old")


def test_metadata_change_after_patch_is_reported(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "canonical_body", lambda tag: "new")
    monkeypatch.setattr(MODULE, "source_head", lambda: "a" * 40)
    monkeypatch.setattr(MODULE, "source_is_clean", lambda: True)
    count = 0

    def api(path, body=None):
        nonlocal count
        count += 1
        response = release("new" if count >= 3 else "old")
        if count == 4:
            response = copy.deepcopy(response)
            response["name"] = "unexpectedly changed"
        return response

    monkeypatch.setattr(MODULE, "api", api)
    with pytest.raises(ValueError, match="Post-write verification"):
        MODULE.run(args(tmp_path))
