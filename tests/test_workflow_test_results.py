"""CI publishes and uploads ``test-results/`` for every unit and integration run (#405).

The jobs that run ``make test`` or ``make integration`` append the one-line summary to
the step summary and upload ``test-results/`` as an artifact on every run, pass or
fail, without adding permissions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
UPLOAD = "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9"  # v7
SHA_PIN = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")

# (workflow, job, make target, lane, matrix keys the artifact name must carry)
JOBS = [
    ("ci.yml", "lint-and-test", "make test", "test", ["python-version"]),
    ("ci.yml", "integration", "make integration", "integration", ["cubrid"]),
    ("integration-full.yml", "integration-full", "make integration", "integration",
     ["python-version", "cubrid"]),
]  # fmt: skip
PARAMS = [pytest.param(*j, id=f"{j[0]}:{j[1]}") for j in JOBS]


def _steps(wf: str, job: str) -> list[dict[str, Any]]:
    data = yaml.safe_load((WORKFLOWS / wf).read_text())
    return list(data["jobs"][job]["steps"])


def _index(steps: list[dict[str, Any]], needle: str) -> int:
    return next(
        i for i, s in enumerate(steps) if needle in str(s.get("run", "")) + str(s.get("uses", ""))
    )


@pytest.mark.parametrize(("wf", "job", "make", "lane", "keys"), PARAMS)
def test_summary_step_follows_the_make_target_and_always_runs(
    wf: str, job: str, make: str, lane: str, keys: list[str]
) -> None:
    steps = _steps(wf, job)
    run = _index(steps, make)
    summary = steps[_index(steps, "report_results.py step-summary")]
    assert _index(steps, "report_results.py step-summary") > run
    assert summary["if"] == "always()"
    assert f"--results-dir test-results/{lane}" in summary["run"]
    assert summary["run"].rstrip().endswith('>> "$GITHUB_STEP_SUMMARY"')


@pytest.mark.parametrize(("wf", "job", "make", "lane", "keys"), PARAMS)
def test_upload_step_is_pinned_always_and_uniquely_named(
    wf: str, job: str, make: str, lane: str, keys: list[str]
) -> None:
    steps = _steps(wf, job)
    uploads = [s for s in steps if str(s.get("uses", "")).startswith("actions/upload-artifact@")]
    assert len(uploads) == 1
    upload = uploads[0]
    assert upload["uses"] == UPLOAD and SHA_PIN.match(upload["uses"])
    assert upload["if"] == "always()"
    assert _index(steps, "actions/upload-artifact@") > _index(steps, make)
    with_ = upload["with"]
    assert with_["path"] == "test-results/"
    assert with_["if-no-files-found"] == "warn"
    assert 1 <= with_["retention-days"] <= 14
    for key in keys:  # one artifact per matrix entry, or entries would collide
        assert f"matrix.{key}" in with_["name"]
    assert with_["name"].startswith(f"test-results-{lane}")


def test_codecov_upload_is_kept_for_the_unit_job() -> None:
    steps = _steps("ci.yml", "lint-and-test")
    codecov = steps[_index(steps, "codecov/codecov-action@")]
    assert "matrix.python-version == '3.12'" in codecov["if"]
    assert codecov["with"]["files"] == "./coverage.xml"


@pytest.mark.parametrize("wf", ["ci.yml", "integration-full.yml"])
def test_no_permissions_were_added(wf: str) -> None:
    data = yaml.safe_load((WORKFLOWS / wf).read_text())
    assert data["permissions"] == {"contents": "read"}
    for name, job in data["jobs"].items():
        assert "permissions" not in job or job["permissions"] == {"contents": "read"}, name
