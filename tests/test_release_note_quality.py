"""Candidate release-note editorial gate regression tests (no DB or GitHub calls)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_release_note_quality",
    ROOT / "scripts" / "check_release_note_quality.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

GOOD = """
This patch fixes authentication diagnostics without changing the existing database read-only default.

### Fixed

- **Authentication** — Invalid credentials now produce a clear diagnostic ([#10](https://github.com/cubrid-lab/cubrid-mcp-server/pull/10)) by @maintainer.

### Documentation

- **Setup** — Clarified broker configuration ([#11](https://github.com/cubrid-lab/cubrid-mcp-server/pull/11)) by @maintainer.
"""


def test_accepts_small_curated_patch() -> None:
    assert MODULE.violations(GOOD) == []


def test_rejects_missing_intro() -> None:
    assert any("summary" in e for e in MODULE.violations(GOOD[GOOD.index("### Fixed"):]))


def test_rejects_generated_raw_bullet() -> None:
    bad = GOOD.replace("- **Authentication** —", "* fix: authentication")
    assert any("uncurated" in e for e in MODULE.violations(bad))


def test_rejects_exact_duplicate() -> None:
    entry = "- **Authentication** — Invalid credentials now produce a clear diagnostic ([#10](https://github.com/cubrid-lab/cubrid-mcp-server/pull/10)) by @maintainer."
    assert any("duplicate" in e for e in MODULE.violations(GOOD.replace(entry, entry + "\n" + entry)))


def test_rejects_missing_candidate_version() -> None:
    sample = "## [0.8.1] - 2026-11-17\n" + GOOD + "\n## [0.8.0] - 2026-11-05\nOld"
    assert "release [0.8.2]" in str(_missing(sample))


def _missing(sample: str) -> Exception:
    try:
        MODULE.release_section(sample, "0.8.2")
    except ValueError as exc:
        return exc
    raise AssertionError("missing release section was accepted")


def test_version_scoped_extraction() -> None:
    sample = "## [0.8.1] - 2026-11-17\n" + GOOD + "\n## [0.8.0] - 2026-11-05\nOld"
    assert MODULE.release_section(sample, "0.8.1").strip() == GOOD.strip()
