"""Every test that reads a workflow file must run in the unit lane (#232).

A workflow-only PR (other than ``ci.yml``) selects the unit lane and no live CUBRID
lane, so a test that reads a workflow but carries the ``integration`` marker would be
deselected by ``pytest -m "not integration"`` and never validate the edit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

# Module-level on purpose: workflow paths usually live in a module constant
# (``ROOT / ".github" / "workflows"``), not in the test function body.
WORKFLOW_REF = re.compile(r"\.github['\"]?\s*[/,]\s*['\"]?workflows")
INTEGRATION_MARK = re.compile(r"\bmark\.integration\b|\bpytestmark\b[^\n]*integration")


def _workflow_modules_with_integration_marks(test_dir: Path) -> list[str]:
    return sorted(
        path.name
        for path in test_dir.glob("test_*.py")
        if WORKFLOW_REF.search(source := path.read_text()) and INTEGRATION_MARK.search(source)
    )


def test_tests_that_read_workflows_run_in_the_unit_lane() -> None:
    found = _workflow_modules_with_integration_marks(ROOT / "tests")
    # This module's own probe strings contain both patterns by design.
    assert [name for name in found if name != Path(__file__).name] == []


def test_unit_lane_deselects_only_integration_tests() -> None:
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    runs = [s.get("run", "") for s in ci["jobs"]["lint-and-test"]["steps"]]
    assert any('pytest -m "not integration"' in run for run in runs)


def test_workflow_readers_exist() -> None:
    # Guards the guard: the scan must find the known workflow-contract modules.
    readers = [
        p.name for p in (ROOT / "tests").glob("test_*.py") if WORKFLOW_REF.search(p.read_text())
    ]
    assert {"test_release_workflows.py", "test_workflow_timeouts.py"} <= set(readers)


@pytest.mark.parametrize(
    "body",
    [
        'P = ROOT / ".github" / "workflows" / "ci.yml"\n\n@pytest.mark.integration\ndef test_x(): ...',
        'W = ".github/workflows/ci.yml"\n\nclass TestX:\n    @pytest.mark.integration\n    def test_x(self): ...',
        'W = ".github/workflows/x.yml"\npytestmark = [pytest.mark.integration]\n\ndef test_x(): ...',
        'W = ".github/workflows/x.yml"\npytestmark = pytest.mark.integration\n\ndef test_x(): ...',
    ],
    ids=["split-path-constant", "class-method", "module-mark-list", "module-mark"],
)
def test_guard_catches_indirect_workflow_readers(tmp_path: Path, body: str) -> None:
    (tmp_path / "test_probe.py").write_text("import pytest\n" + body + "\n")
    assert _workflow_modules_with_integration_marks(tmp_path) == ["test_probe.py"]
