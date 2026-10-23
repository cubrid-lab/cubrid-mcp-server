"""Makefile target semantics and CI parity (#379).

The Makefile is the canonical local and CI interface: CI's lint, type, unit and live
jobs call its targets instead of re-implementing them. Recipes are read with
``make -n`` (print, do not run), so these tests need no database or Docker.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
MAKE = shutil.which("make")

needs_make = pytest.mark.skipif(MAKE is None, reason="make is not installed")


def dry_run(*args: str) -> list[str]:
    assert MAKE is not None
    out = subprocess.run(
        [MAKE, "--no-print-directory", "-n", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line.strip()]


def jobs(name: str) -> dict[str, Any]:
    return dict(yaml.safe_load((WORKFLOWS / name).read_text())["jobs"])


def runs(job: dict[str, Any]) -> list[str]:
    return [str(step["run"]).strip() for step in job["steps"] if "run" in step]


@needs_make
@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("lint", ["ruff check ."]),
        ("format-check", ["ruff format --check ."]),
        ("typecheck", ["mypy cubrid_mcp_server"]),
        ("format", ["ruff format .", "ruff check --fix ."]),
    ],
)
def test_quality_targets_use_the_ci_paths_and_flags(target: str, expected: list[str]) -> None:
    assert dry_run(target) == expected


@needs_make
def test_check_runs_lint_format_check_and_typecheck() -> None:
    assert dry_run("check") == dry_run("lint") + dry_run("format-check") + dry_run("typecheck")


@needs_make
def test_test_collects_coverage_and_enforces_fail_under() -> None:
    (line,) = dry_run("test")
    argv = shlex.split(line)
    assert argv[:3] == ["python3", "-m", "pytest"]
    assert argv[argv.index("-m", 3) + 1] == "not integration"
    assert "--cov=cubrid_mcp_server" in argv
    assert "--cov-report=xml" in argv  # the file CI uploads to Codecov
    # Nothing may weaken the pyproject floor that pytest-cov enforces.
    assert not [a for a in argv if a.startswith("--cov-fail-under") or a == "--no-cov"]
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["tool"]["coverage"]["report"]["fail_under"] == 95


@needs_make
def test_test_accepts_extra_pytest_args() -> None:
    (line,) = dry_run("test", "PYTEST_ARGS=-k config -x")
    assert line.endswith("--cov-report=xml -k config -x")


@needs_make
def test_verify_is_check_plus_test_without_docker() -> None:
    lines = dry_run("verify")
    assert lines == dry_run("check") + dry_run("test")
    assert not [line for line in lines if "docker" in line or "run_integration" in line]


@needs_make
def test_only_format_mutates_sources() -> None:
    mutating = re.compile(r"ruff format (?!--check)|--fix|\bsed -i\b")
    for target in ("lint", "format-check", "typecheck", "check", "test", "verify"):
        assert not [line for line in dry_run(target) if mutating.search(line)], target


@needs_make
@pytest.mark.parametrize(
    ("overrides", "version", "port"),
    [([], "11.4", "33000"), (["CUBRID_VERSION=11.2", "INTEGRATION_PORT=33524"], "11.2", "33524")],
    ids=["defaults", "overrides"],
)
def test_integration_owns_a_docker_database(overrides: list[str], version: str, port: str) -> None:
    (line,) = dry_run("integration", *overrides)
    argv = shlex.split(line)
    assert argv[:2] == ["python3", "scripts/run_integration.py"]
    assert argv[argv.index("--cubrid-version") + 1] == version
    assert argv[argv.index("--port") + 1] == port
    assert argv[argv.index("--pytest") + 1] == "python3 -m pytest"


@needs_make
def test_integration_local_uses_an_already_running_database() -> None:
    assert dry_run("integration-local") == ['python3 -m pytest -m "integration" -q']


@needs_make
def test_clean_only_removes_generated_ignored_artifacts() -> None:
    (line,) = dry_run("clean")
    argv = shlex.split(line)
    assert argv[:2] == ["rm", "-rf"]
    paths = [p.replace("*", "example") for p in argv[2:]]
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", *paths], capture_output=True, text=True
    )
    assert tracked.stdout == ""
    for path in paths:
        assert not path.startswith((".venv", "venv", "/", "..", ".git")), path
        # Probe as a file and as a directory: `*.egg-info/` only matches directories.
        probes = [path, path.rstrip("/") + "/"]
        ignored = [
            subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", probe]).returncode == 0
            for probe in probes
        ]
        assert any(ignored), f"{path} is not a gitignored generated artifact"


@needs_make
def test_help_groups_every_documented_target() -> None:
    assert MAKE is not None
    out = subprocess.run(
        [MAKE, "--no-print-directory", "-C", str(ROOT), "help"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    groups: dict[str, list[str]] = {}
    current = None
    for line in out.splitlines():
        if line and not line.startswith(" "):
            current = line
            groups[current] = []
        elif line.strip():
            assert current is not None, f"target listed before any group: {line!r}"
            groups[current].append(line.split()[0])
    assert len(groups) >= 4
    listed = {target for targets in groups.values() for target in targets}
    phony = re.search(r"^\.PHONY:(.*)$", (ROOT / "Makefile").read_text(), re.M)
    assert phony is not None
    assert listed == set(phony.group(1).split())
    quality = next(targets for name, targets in groups.items() if name.startswith("Quality"))
    assert {"lint", "format-check", "format", "typecheck", "check"} <= set(quality)


def _load_doctor() -> Any:
    spec = importlib.util.spec_from_file_location("_doctor", ROOT / "scripts" / "doctor.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_doctor_passes_when_every_required_tool_is_present(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    doctor = _load_doctor()
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert doctor.main() == 0
    assert "doctor: all required development tools found" in capsys.readouterr().out


def test_doctor_fails_closed_without_a_success_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    doctor = _load_doctor()
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    assert doctor.main() == 1
    captured = capsys.readouterr()
    assert "all required" not in captured.out
    assert "MISSING: command 'ruff' not found" in captured.err
    assert "MISSING: command 'mypy' not found" in captured.err


def test_doctor_fails_on_a_python_older_than_the_minimum(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    doctor = _load_doctor()
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(doctor.sys, "version_info", (3, 10, 14))
    assert doctor.main() == 1
    captured = capsys.readouterr()
    assert "all required" not in captured.out
    assert "MISSING: Python 3.10.14 is older than 3.11" in captured.err


@pytest.mark.parametrize("module", ["pytest", "pytest_cov", "pytest_asyncio"])
def test_doctor_fails_on_a_missing_dev_module(
    module: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    doctor = _load_doctor()
    find_spec = doctor.importlib.util.find_spec
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        doctor.importlib.util, "find_spec", lambda name: None if name == module else find_spec(name)
    )
    assert doctor.main() == 1
    captured = capsys.readouterr()
    assert "all required" not in captured.out
    assert f"MISSING: module '{module}' not installed" in captured.err
    assert "MISSING: command" not in captured.err


def test_doctor_only_notes_a_missing_docker(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    doctor = _load_doctor()
    monkeypatch.setattr(
        doctor.shutil, "which", lambda name: None if name == "docker" else f"/usr/bin/{name}"
    )
    assert doctor.main() == 0
    captured = capsys.readouterr()
    assert "note: optional command 'docker' not found" in captured.out
    assert "doctor: all required development tools found" in captured.out
    assert captured.err == ""


@needs_make
def test_make_doctor_exits_non_zero_when_tools_are_off_path(tmp_path: Path) -> None:
    assert MAKE is not None
    result = subprocess.run(
        [MAKE, "--no-print-directory", "-C", str(ROOT), "doctor", f"PYTHON={sys.executable}"],
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": str(tmp_path)},
    )
    assert result.returncode != 0
    assert "all required" not in result.stdout


def test_ci_unit_jobs_call_make_targets() -> None:
    unit = runs(jobs("ci.yml")["lint-and-test"])
    for target in ("make lint", "make format-check", "make typecheck", "make test"):
        assert target in unit
    # No step re-implements (a stronger variant of) a Make target.
    direct = re.compile(r"^\s*(ruff|mypy|pytest|python3? -m (pytest|mypy|ruff))\b", re.M)
    assert not [run for run in unit if direct.search(run)]
    (upload,) = [
        s for s in jobs("ci.yml")["lint-and-test"]["steps"] if "codecov" in s.get("uses", "")
    ]
    assert upload["with"]["files"] == "./coverage.xml"


@pytest.mark.parametrize(
    ("workflow", "job"), [("ci.yml", "integration"), ("integration-full.yml", "integration-full")]
)
def test_live_jobs_pass_the_matrix_to_make_integration(workflow: str, job: str) -> None:
    steps = runs(jobs(workflow)[job])
    assert "make integration CUBRID_VERSION=${{ matrix.cubrid }}" in steps
    assert not [run for run in steps if "docker" in run or re.search(r"\bpytest\b", run)]
