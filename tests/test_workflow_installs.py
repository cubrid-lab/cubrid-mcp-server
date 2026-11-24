"""CI and full-matrix jobs install dependencies with a pinned uv (#229).

Resolution is unchanged from pip (same pyproject constraints); uv only replaces the
installer. Release, docs and canary workflows keep plain ``pip`` on purpose: the
release smoke venvs prove the built wheel and sdist install with the tool end users
run, and the docs build installs from its own Dependabot-pinned requirements file.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

UV_ACTION = "astral-sh/setup-uv"
# Dependabot moves every setup-uv ref to a new commit SHA together, so the test asks for one
# shared full SHA instead of hard-coding it (#523).
FULL_SHA = re.compile(r"[0-9a-f]{40}")
UV_VERSION = "0.12.17"
# The release gate (integration-full.yml is called by publish.yml) keeps setup-uv's
# event guard (`auto`); routine CI always caches.
WORKFLOWS = {"ci.yml": True, "integration-full.yml": "auto"}
EXPECTED_JOBS = {"ci.yml": 4, "integration-full.yml": 2}
PIP_INSTALL = re.compile(r"\bpip3?\s+install\b")


def _python_jobs() -> list[Any]:
    params = []
    for wf in WORKFLOWS:
        jobs = yaml.safe_load((ROOT / ".github/workflows" / wf).read_text())["jobs"]
        for name, job in jobs.items():
            steps = job.get("steps", [])
            if any("actions/setup-python@" in str(s.get("uses", "")) for s in steps):
                params.append(pytest.param(wf, name, steps, id=f"{wf}:{name}"))
    return params


PYTHON_JOBS = _python_jobs()


def _uv_steps(steps: list[Any]) -> list[Any]:
    return [s for s in steps if str(s.get("uses", "")).startswith(f"{UV_ACTION}@")]


def _shared_full_sha(uses: list[str]) -> str:
    """The one ref every ``setup-uv`` step uses; fails unless it is shared and a full commit SHA."""
    refs = sorted({u.partition("@")[2] for u in uses})
    assert len(refs) == 1, f"every job must pin {UV_ACTION} to the same ref, found {refs}"
    assert FULL_SHA.fullmatch(refs[0]), (
        f"{UV_ACTION} must be pinned to a full commit SHA, found {refs[0]!r}"
    )
    return refs[0]


def test_python_jobs_are_found() -> None:
    for wf, expected in EXPECTED_JOBS.items():
        assert sum(1 for p in PYTHON_JOBS if p.values[0] == wf) == expected, wf


def test_every_job_pins_setup_uv_to_one_full_sha() -> None:
    _shared_full_sha([s["uses"] for p in PYTHON_JOBS for s in _uv_steps(p.values[2])])


SHA_A = "68559e99cc807c1eb7e9238fd43a15bba460eec2"
SHA_B = "0123456789abcdef0123456789abcdef01234567"


def test_a_dependabot_bump_of_every_ref_to_one_new_sha_passes() -> None:
    assert _shared_full_sha([f"{UV_ACTION}@{SHA_B}"] * 6) == SHA_B


@pytest.mark.parametrize(
    ("refs", "message"),
    [
        pytest.param([SHA_A, SHA_B], "same ref", id="two-shas"),
        pytest.param(["v10.3.3"], "full commit SHA", id="tag"),
        pytest.param([SHA_A[:7]], "full commit SHA", id="short-sha"),
        pytest.param([SHA_A.upper()], "full commit SHA", id="uppercase"),
    ],
)
def test_mixed_or_non_sha_setup_uv_refs_fail(refs: list[str], message: str) -> None:
    with pytest.raises(AssertionError, match=message):
        _shared_full_sha([f"{UV_ACTION}@{ref}" for ref in refs])


@pytest.mark.parametrize(("wf", "name", "steps"), PYTHON_JOBS)
def test_job_sets_up_pinned_uv_with_cache(wf: str, name: str, steps: list[Any]) -> None:
    uv = _uv_steps(steps)
    assert len(uv) == 1, f"{wf}:{name} needs exactly one setup-uv step"
    assert uv[0]["with"]["version"] == UV_VERSION
    assert uv[0]["with"]["enable-cache"] == WORKFLOWS[wf]
    assert uv[0]["with"]["cache-dependency-glob"] == "pyproject.toml"
    # One cache per job (different install sets). setup-uv follows setup-python and
    # both share one python-version spec, so UV_PYTHON resolves to setup-python's
    # interpreter.
    assert uv[0]["with"]["cache-suffix"] == "${{ github.job }}"
    python = next(s for s in steps if "actions/setup-python@" in str(s.get("uses", "")))
    assert steps.index(python) < steps.index(uv[0]), f"{wf}:{name} set up Python first"
    # The cache key must carry the job's Python spec (e.g. "3.12"), not the patch
    # release `uv python find` reports, which drifts across runner images.
    assert uv[0]["with"]["python-version"] == python["with"]["python-version"]
    assert "cache" not in python.get("with", {}), "pip cache is unused once uv installs"


@pytest.mark.parametrize(("wf", "name", "steps"), PYTHON_JOBS)
def test_job_installs_with_uv_and_logs_versions(wf: str, name: str, steps: list[Any]) -> None:
    runs = [s["run"] for s in steps if "run" in s]
    lines = [line.strip() for run in runs for line in run.splitlines()]
    assert any(line.startswith("uv pip install --system ") for line in lines), name
    # The project and its contributor tools come from the PEP 735 `dev` group (#398).
    project = [line for line in lines if line.startswith("uv pip install ") and " -e " in line]
    assert all(line.endswith("-e . --group dev") for line in project), project
    assert "uv pip freeze --system" in lines, f"{wf}:{name} must log resolved versions"
    for line in lines:
        if PIP_INSTALL.search(line):
            assert line.startswith("uv pip "), f"{wf}:{name} still uses pip: {line}"
