"""README translation-sync policy regressions."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "check_translation_sync",
    Path(__file__).resolve().parents[1] / "scripts/check_translation_sync.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write_workspace(tmp_path: Path, *languages: str) -> None:
    """Create the canonical README and the requested translation files."""
    (tmp_path / "README.md").write_text("# English\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    for language in languages:
        (docs / f"README.{language}.md").write_text(f"# {language}\n")


def test_readme_change_requires_korean_translation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path, "ko")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(MODULE, "changed_files", lambda: {"README.md"})

    assert MODULE.main() == 1
    output = capsys.readouterr().out
    assert "::error::" in output
    assert "docs/README.ko.md" in output


def test_missing_community_translation_warns_without_failing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path, "ko", "de")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        MODULE,
        "changed_files",
        lambda: {"README.md", "docs/README.ko.md"},
    )

    assert MODULE.main() == 0
    output = capsys.readouterr().out
    assert "::warning file=README.md::" in output
    assert "docs/README.de.md" in output
    assert output.rstrip().endswith("translation sync OK")


def test_unchanged_readme_passes_without_translation_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path, "ko")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(MODULE, "changed_files", lambda: {"docs/README.ko.md"})

    assert MODULE.main() == 0
    assert "README.md unchanged in this PR" in capsys.readouterr().out


def test_no_translations_passes_without_inspecting_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "README.md").write_text("# English\n")
    monkeypatch.chdir(tmp_path)

    def unexpected_changed_files() -> set[str]:
        pytest.fail("changed_files should not run when no translations are present")

    monkeypatch.setattr(MODULE, "changed_files", unexpected_changed_files)

    assert MODULE.main() == 0
    assert "no translations present" in capsys.readouterr().out
