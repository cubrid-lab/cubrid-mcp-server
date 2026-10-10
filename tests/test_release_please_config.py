"""release-please changelog-sections map commit types to the standard headings."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lint_changelog", ROOT / "scripts/lint_changelog.py")
assert SPEC and SPEC.loader
LINT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LINT)

# type -> (section, hidden); hidden types never create a release on their own.
EXPECTED = {
    "feat": ("Added", False),
    "fix": ("Fixed", False),
    "perf": ("Performance", False),
    "deps": ("Changed", False),
    "revert": ("Changed", False),
    "docs": ("Documentation", False),
    "ci": ("CI", True),
    "test": ("Tests", True),
    "refactor": ("Changed", True),
    "chore": ("Changed", True),
    "build": ("Changed", True),
    "style": ("Changed", True),
}


def sections() -> list[dict[str, object]]:
    config = json.loads((ROOT / "release-please-config.json").read_text(encoding="utf-8"))
    return list(config["packages"]["."]["changelog-sections"])


def test_changelog_sections_table_is_exact() -> None:
    entries = sections()
    assert len(entries) == len({e["type"] for e in entries})
    for entry in entries:
        assert set(entry) <= {"type", "section", "hidden"}
    actual = {e["type"]: (e["section"], e.get("hidden", False)) for e in entries}
    assert actual == EXPECTED


def test_every_section_is_a_standard_changelog_section() -> None:
    assert {e["section"] for e in sections()} <= set(LINT.ALLOWED_SECTIONS)


def test_hidden_types_are_exactly_the_non_releasing_types() -> None:
    hidden = {e["type"] for e in sections() if e.get("hidden") is True}
    assert hidden == {"ci", "test", "refactor", "chore", "build", "style"}


# cubrid-mcp-server only: the MCP Registry metadata moves with __version__.
def package() -> dict[str, object]:
    config = json.loads((ROOT / "release-please-config.json").read_text(encoding="utf-8"))
    return dict(config["packages"]["."])


def test_package_identity_and_pr_only_mode() -> None:
    entry = package()
    assert entry["release-type"] == "python"
    assert entry["package-name"] == "cubrid-mcp-server"
    assert entry["skip-github-release"] is True
    assert entry["include-v-in-tag"] is True
    assert entry["include-component-in-tag"] is False
    assert entry["changelog-path"] == "RELEASE_CHANGELOG.md"


def test_pre_1_0_breaking_changes_bump_the_minor_version() -> None:
    # MCP-only (0.x): a breaking change proposes 0.Y+1.0, not 1.0.0; feat still
    # bumps the minor, so the patch-for-minor flag stays unset.
    entry = package()
    assert entry["bump-minor-pre-major"] is True
    assert "bump-patch-for-minor-pre-major" not in entry


def test_server_json_versions_are_extra_files() -> None:
    assert package()["extra-files"] == [
        {"type": "json", "path": ".mcpb/server.json", "jsonpath": "$.version"},
        {"type": "json", "path": ".mcpb/server.json", "jsonpath": "$.packages[*].version"},
    ]


def test_manifest_matches_the_released_version_files() -> None:
    manifest = json.loads((ROOT / ".release-please-manifest.json").read_text(encoding="utf-8"))
    assert set(manifest) == {"."}
    init = (ROOT / "cubrid_mcp_server/__init__.py").read_text(encoding="utf-8")
    server = json.loads((ROOT / ".mcpb/server.json").read_text(encoding="utf-8"))
    versions = {server["version"]} | {p["version"] for p in server["packages"]}
    assert f'__version__ = "{manifest["."]}"' in init
    assert versions == {manifest["."]}


def test_bootstrap_sha_is_the_v0_4_0_release_commit() -> None:
    config = json.loads((ROOT / "release-please-config.json").read_text(encoding="utf-8"))
    # The v0.4.0 release commit (`git rev-list -n1 v0.4.0`).
    assert config["bootstrap-sha"] == "b6305f1888753ee57e0878bf381d58ce10bb5ff4"
    assert config["always-update"] is True
