"""Offline tests for scripts/prepare_release.py (the release PR content).

Kept identical across pycubrid, sqlalchemy-cubrid and cubrid-mcp-server, except
for the ``.mcpb/server.json`` tests at the end (cubrid-mcp-server only).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "_prepare_release", ROOT / "scripts" / "prepare_release.py"
)
assert _spec is not None and _spec.loader is not None
prepare = importlib.util.module_from_spec(_spec)
sys.modules["_prepare_release"] = prepare
_spec.loader.exec_module(prepare)

CHANGELOG = """# Changelog

Intro.

## [Unreleased]

### Upgrade notes
- Behavior note.

### Fixed
- A fix (#1).

## [1.8.0] - 2026-09-29

### Added
- Old.
"""


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text(
        '"""Pkg."""\n\n__version__ = "1.8.0"\n__all__ = ["__version__"]\n'
    )
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG)
    return tmp_path


def run(*args: str) -> int:
    return prepare.main(["--version-file", "pkg/__init__.py", "--date", "2026-10-01", *args])


def test_moves_unreleased_under_a_dated_heading(tree: Path) -> None:
    assert run("--version", "1.9.0") == 0
    assert (
        (tree / "CHANGELOG.md").read_text()
        == """# Changelog

Intro.

## [Unreleased]

## [1.9.0] - 2026-10-01

### Upgrade notes
- Behavior note.

### Fixed
- A fix (#1).

## [1.8.0] - 2026-09-29

### Added
- Old.
"""
    )
    assert (
        '__version__ = "1.9.0"\n__all__ = ["__version__"]'
        in (tree / "pkg" / "__init__.py").read_text()
    )


def test_first_release_without_older_sections(tree: Path) -> None:
    (tree / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n\n- First.\n")
    assert run("--version", "1.9.0") == 0
    assert (tree / "CHANGELOG.md").read_text() == (
        "# Changelog\n\n## [Unreleased]\n\n## [1.9.0] - 2026-10-01\n\n- First.\n"
    )


def test_extra_version_files_are_bumped(tree: Path) -> None:
    (tree / "server.py").write_text("__version__ = '1.8.0'\n")
    assert run("--version", "1.9.0", "--version-file", "server.py") == 0
    assert (tree / "server.py").read_text() == "__version__ = '1.9.0'\n"


@pytest.mark.parametrize(
    ("version", "message"),
    [
        ("1.8.0", "not greater than the current version 1.8.0"),
        ("1.7.9", "not greater than the current version 1.8.0"),
        ("1.9", "is not MAJOR.MINOR.PATCH"),
        ("v1.9.0", "is not MAJOR.MINOR.PATCH"),
    ],
)
def test_refuses_invalid_versions(tree: Path, version: str, message: str, capsys) -> None:
    assert run("--version", version) == 1
    assert message in capsys.readouterr().out
    assert (tree / "CHANGELOG.md").read_text() == CHANGELOG


@pytest.mark.parametrize(
    ("changelog", "message"),
    [
        ("# Changelog\n\n## [Unreleased]\n\n## [1.8.0] - 2026-09-29\n- x\n", "is empty"),
        ("# Changelog\n\n## [1.8.0] - 2026-09-29\n- x\n", "no '## [Unreleased]'"),
        (
            CHANGELOG.replace("## [1.8.0]", "## [1.9.0] - 2026-09-30\n\n## [1.8.0]"),
            "already has a [1.9.0]",
        ),
    ],
)
def test_refuses_bad_changelogs_and_writes_nothing(
    tree: Path, changelog: str, message: str, capsys
) -> None:
    (tree / "CHANGELOG.md").write_text(changelog)
    assert run("--version", "1.9.0") == 1
    assert message in capsys.readouterr().out
    assert '__version__ = "1.8.0"' in (tree / "pkg" / "__init__.py").read_text()


def test_refuses_ambiguous_version_file(tree: Path, capsys) -> None:
    (tree / "pkg" / "__init__.py").write_text('__version__ = "1.8.0"\n__version__ = "1.8.0"\n')
    assert run("--version", "1.9.0") == 1
    assert "expected exactly one __version__ string, found 2" in capsys.readouterr().out


def test_refuses_bad_date(tree: Path) -> None:
    assert (
        prepare.main(["--version", "1.9.0", "--version-file", "pkg/__init__.py", "--date", "10/01"])
        == 1
    )


def test_result_passes_the_release_gates(tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import runpy

    assert run("--version", "1.9.0") == 0
    monkeypatch.setattr(sys, "argv", ["extract_release_notes.py", "v1.9.0"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(ROOT / "scripts" / "extract_release_notes.py"), run_name="__main__")
    assert exit_info.value.code == 0
    assert (tree / "RELEASE_NOTES.md").read_text().startswith("### Upgrade notes\n")


# cubrid-mcp-server: .mcpb/server.json mirrors __version__ for the MCP Registry.
SERVER_JSON = {
    "name": "io.example/pkg",
    "version": "1.8.0",
    "packages": [{"registryType": "pypi", "identifier": "pkg", "version": "1.8.0"}],
    "_meta": {"publisher": {"tool": "mcp-publisher", "version": "1.0.0"}},
}


def write_server_json(tree: Path, data: dict[str, object]) -> Path:
    path = tree / "server.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return path


def test_server_json_versions_are_bumped(tree: Path) -> None:
    path = write_server_json(tree, SERVER_JSON)
    # The same order as VERSION_FILES in the retired prepare-release.yml: __init__.py first.
    assert run("--version", "1.9.0", "--version-file", "server.json") == 0
    assert '__version__ = "1.9.0"' in (tree / "pkg" / "__init__.py").read_text()
    data = json.loads(path.read_text())
    assert data["version"] == "1.9.0"
    assert data["packages"][0]["version"] == "1.9.0"
    # Other "version" keys (the publisher tool) are left alone.
    assert data["_meta"]["publisher"]["version"] == "1.0.0"
    expected = json.loads(json.dumps(SERVER_JSON))
    expected["version"] = expected["packages"][0]["version"] = "1.9.0"
    assert path.read_text() == json.dumps(expected, indent=2, ensure_ascii=False) + "\n"


@pytest.mark.parametrize(
    "data",
    [
        {**SERVER_JSON, "version": "1.7.0"},
        {**SERVER_JSON, "packages": []},
        {key: value for key, value in SERVER_JSON.items() if key != "version"},
        {key: value for key, value in SERVER_JSON.items() if key != "packages"},
        {**SERVER_JSON, "packages": [{"identifier": "pkg"}]},
    ],
)
def test_refuses_inconsistent_server_json_and_writes_nothing(
    tree: Path, data: dict[str, object], capsys
) -> None:
    path = write_server_json(tree, data)
    before = path.read_text()
    assert run("--version", "1.9.0", "--version-file", "server.json") == 1
    assert "server.json: expected" in capsys.readouterr().out
    assert path.read_text() == before
    assert (tree / "CHANGELOG.md").read_text() == CHANGELOG
    assert '__version__ = "1.8.0"' in (tree / "pkg" / "__init__.py").read_text()


def test_repository_server_json_round_trips() -> None:
    # The bump rewrites the file with json.dumps(indent=2); the repository file
    # must already be in that form so a release PR only changes the versions.
    text = (ROOT / ".mcpb" / "server.json").read_text()
    new_text, current = prepare.bump_server_json(text, "0.0.0", "x")
    data = json.loads(text)
    assert current == data["version"]
    data["version"] = "0.0.0"
    for package in data["packages"]:
        package["version"] = "0.0.0"
    assert new_text == json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    assert prepare.bump_server_json(new_text, current, "x")[0] == text
