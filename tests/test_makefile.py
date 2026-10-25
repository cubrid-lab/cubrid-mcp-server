"""Makefile target semantics and CI parity (#379).

The Makefile is the canonical local and CI interface: CI's lint, type, unit and live
jobs call its targets instead of re-implementing them. Recipes are read with
``make -n`` (print, do not run), so these tests need no database or Docker.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
MAKE = shutil.which("make")

needs_make = pytest.mark.skipif(MAKE is None, reason="make is not installed")
COMPOSE = ["docker", "compose", "--file", "docker-compose.yml"]


# An outer make (`make verify CUBRID_TEST_PORT=...` runs these tests) passes its
# command-line variables down in MAKEFLAGS and also exports them to its recipes; the
# recipes read here must inherit neither, so the defaults stay the Makefile's own.
OUTER_MAKE = {
    "MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES", "MAKELEVEL",
    "PYTHON", "PYTEST", "RUFF", "MYPY", "PYTEST_ARGS", "RESULTS", "COMPOSE",
    "CUBRID_VERSION", "CUBRID_TEST_PORT", "INTEGRATION_PORT",
}  # fmt: skip


def dry_run(*args: str) -> list[str]:
    assert MAKE is not None
    out = subprocess.run(
        [MAKE, "--no-print-directory", "-n", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
        env={k: v for k, v in os.environ.items() if k not in OUTER_MAKE},
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
        ("lint", ["python3 -m ruff check ."]),
        ("format-check", ["python3 -m ruff format --check ."]),
        ("typecheck", ["python3 -m mypy cubrid_mcp_server"]),
        ("format", ["python3 -m ruff format .", "python3 -m ruff check --fix ."]),
    ],
)
def test_quality_targets_use_the_ci_paths_and_flags(target: str, expected: list[str]) -> None:
    assert dry_run(target) == expected


@needs_make
def test_check_runs_lint_format_check_and_typecheck() -> None:
    assert dry_run("check") == dry_run("lint") + dry_run("format-check") + dry_run("typecheck")


@needs_make
def test_test_collects_coverage_and_enforces_fail_under() -> None:
    argv = shlex.split(_test_recipe()[0])
    assert argv[:3] == ["python3", "-m", "pytest"]
    assert argv[argv.index("-m", 3) + 1] == "not integration"
    assert "--cov=cubrid_mcp_server" in argv
    # CI uploads the root coverage.xml to Codecov; the same report is kept in test-results/.
    assert "--cov-report=xml:test-results/test/coverage.xml" in argv
    # Nothing may weaken the pyproject floor that pytest-cov enforces.
    assert not [a for a in argv if a.startswith("--cov-fail-under") or a == "--no-cov"]
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["tool"]["coverage"]["report"]["fail_under"] == 95


def _test_recipe() -> list[str]:
    """The `make test` pytest command and the shell steps that follow it."""
    lines = dry_run("test")
    assert lines[0] == 'rm -rf "./test-results/test" && mkdir -p "./test-results/test"'
    joined = " ".join(line.removesuffix("\\").strip() for line in lines[1:])
    pytest_command, *steps = (part.strip() for part in joined.split(";"))
    return [pytest_command, *steps]


@needs_make
def test_test_writes_test_results_and_keeps_the_exit_status() -> None:
    pytest_command, *steps = _test_recipe()
    assert "--junitxml=test-results/test/junit.xml" in shlex.split(pytest_command)
    assert steps[0] == "status=$?"
    assert steps[1].startswith("cp -f test-results/test/coverage.xml coverage.xml")
    report = shlex.split(steps[2])
    assert report[:3] == ["python3", "scripts/report_results.py", "summarize"]
    assert report[report.index("--exit-code") + 1] == "$status"
    assert report[report.index("--coverage") + 1] == "test-results/test/coverage.xml"
    assert steps[-1] == "exit $status"


@needs_make
def test_test_accepts_extra_pytest_args() -> None:
    pytest_command = dry_run("test", "PYTEST_ARGS=-k config -x")[1].split(";")[0]
    assert pytest_command.endswith("--junitxml=test-results/test/junit.xml -k config -x")


def test_test_results_are_gitignored_and_cleaned() -> None:
    assert "test-results/" in (ROOT / ".gitignore").read_text().splitlines()
    assert "test-results" in " ".join(dry_run("clean")).split()


@needs_make
def test_verify_execs_the_runner_and_a_dry_run_writes_nothing(tmp_path: Path) -> None:
    # Not prerequisites, so `make -j` cannot start a later phase early (#404).
    assert re.search(r"^verify:\s*##\s", (ROOT / "Makefile").read_text(), re.M)
    lines = dry_run("verify", f"RESULTS={tmp_path}/results")
    runner = [line for line in lines if line.startswith("exec python3 scripts/run_verify.py ")]
    assert runner == [f'exec python3 scripts/run_verify.py --make "{MAKE}" \\']
    assert not [line for line in lines if "run_integration" in line or "-m pytest" in line]
    assert not list(tmp_path.iterdir())


@needs_make
@pytest.mark.parametrize("results", ["", ".", "/"])
def test_verify_refuses_a_dangerous_results_directory(results: str) -> None:
    assert MAKE is not None
    env = {k: v for k, v in os.environ.items() if k not in OUTER_MAKE}
    result = subprocess.run(
        [MAKE, "--no-print-directory", "-C", str(ROOT), "verify", f"RESULTS={results}",
         "PYTHON=false"],
        env=env, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert result.returncode == 2
    assert "refusing to use results directory" in result.stderr


@needs_make
def test_dry_runs_ignore_an_outer_makes_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    # What `make verify CUBRID_TEST_PORT=33599` hands the tests it runs.
    monkeypatch.setenv("MAKEFLAGS", " -- CUBRID_TEST_PORT=33599 CUBRID_VERSION=10.2")
    monkeypatch.setenv("MAKELEVEL", "1")
    monkeypatch.setenv("CUBRID_TEST_PORT", "33599")
    monkeypatch.setenv("CUBRID_VERSION", "10.2")
    line = dry_run("integration")[-1]
    assert '--cubrid-version "11.4" --port "33000"' in line


@needs_make
def test_test_stays_offline() -> None:
    assert not [line for line in dry_run("test") if "docker" in line or "run_integration" in line]


def _verify_stub(tmp_path: Path, *, fail: str = "", block: str = "") -> tuple[Path, Path]:
    """A PYTHON that logs every call and runs the real verify runner and reporter.

    The offline pytest run fails when *fail* is ``"test"``; the live runner blocks until
    SIGTERM when *block* is ``"integration"`` and logs that it was terminated. Every
    other call succeeds without doing anything.
    """
    log = tmp_path / "python.log"
    stub = tmp_path / "python"
    script = (
        f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{log}"\n'
        'case " $* " in *" scripts/run_verify.py "*|*" scripts/report_results.py "*)'
        f' exec "{sys.executable}" "$@" ;; esac\n'
    )
    if fail == "test":
        script += 'case " $* " in *" -m pytest "*"not integration"*) exit 1 ;; esac\n'
    if block == "integration":
        script += (
            'case " $* " in *" scripts/run_integration.py "*)\n'
            "  sleep 30 & pid=$!\n"
            f"  trap 'kill $pid; echo TERMINATED >> \"{log}\"; exit 143' TERM\n"
            f'  echo BLOCKING >> "{log}"\n'
            "  wait $pid; exit 0 ;;\nesac\n"
        )
    stub.write_text(script + "exit 0\n")
    stub.chmod(0o755)
    return stub, log


def _make_verify(tmp_path: Path, stub: Path, *jobs: str) -> subprocess.CompletedProcess[str]:
    assert MAKE is not None
    env = {k: v for k, v in os.environ.items() if k not in OUTER_MAKE}
    return subprocess.run(
        [MAKE, "--no-print-directory", "-C", str(ROOT), *jobs, "verify",
         f"PYTHON={stub}", f"RESULTS={tmp_path}/results"],
        env=env, capture_output=True, text=True, check=False,
    )  # fmt: skip


def _verify_summary(tmp_path: Path) -> tuple[str, dict[str, str]]:
    summary = json.loads((tmp_path / "results" / "verify" / "summary.json").read_text())
    return summary["status"], {phase["name"]: phase["status"] for phase in summary["phases"]}


@needs_make
def test_verify_runs_check_then_test_then_the_live_lane(tmp_path: Path) -> None:
    stub, log = _verify_stub(tmp_path)
    result = _make_verify(tmp_path, stub)
    calls = log.read_text().splitlines()
    static = max(i for i, call in enumerate(calls) if " ruff " in call or " mypy " in call)
    offline = next(i for i, call in enumerate(calls) if "not integration" in call)
    live = next(i for i, call in enumerate(calls) if "scripts/run_integration.py" in call)
    assert static < offline < live
    # The stub writes no lane summaries, so the run proves nothing and is never PASS.
    assert result.returncode != 0
    assert "verify: INCOMPLETE check=PASS test=INCOMPLETE integration=INCOMPLETE " in result.stdout
    status, phases = _verify_summary(tmp_path)
    assert status == "INCOMPLETE"
    assert phases == {"check": "PASS", "test": "INCOMPLETE", "integration": "INCOMPLETE"}


@needs_make
@pytest.mark.parametrize("jobs", [[], ["-j3"]], ids=["serial", "parallel"])
def test_verify_never_starts_the_live_lane_after_failing_offline_tests(
    tmp_path: Path, jobs: list[str]
) -> None:
    stub, log = _verify_stub(tmp_path, fail="test")
    result = _make_verify(tmp_path, stub, *jobs)
    assert result.returncode != 0
    calls = log.read_text().splitlines()
    assert any("-m pytest" in call for call in calls)
    assert not any("scripts/run_integration.py" in call for call in calls)
    # The summary records the failed offline phase and the live lane that never ran.
    assert _verify_summary(tmp_path) == (
        "FAIL",
        {"check": "PASS", "test": "FAIL", "integration": "NOT_RUN"},
    )
    assert "verify: FAIL check=PASS test=FAIL integration=NOT_RUN " in result.stdout


@needs_make
def test_verify_forwards_sigterm_to_the_live_lane_and_still_writes_the_summary(
    tmp_path: Path,
) -> None:
    # `timeout make verify` and `kill <make pid>` signal only make, which forwards SIGTERM
    # to the runner; the runner must stop the live lane (which then cleans up), not orphan it.
    assert MAKE is not None
    stub, log = _verify_stub(tmp_path, block="integration")
    env = {k: v for k, v in os.environ.items() if k not in OUTER_MAKE}
    process = subprocess.Popen(
        [MAKE, "--no-print-directory", "-C", str(ROOT), "verify",
         f"PYTHON={stub}", f"RESULTS={tmp_path}/results"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )  # fmt: skip
    deadline = time.monotonic() + 30
    while "BLOCKING" not in (log.read_text() if log.exists() else ""):
        assert process.poll() is None and time.monotonic() < deadline, "live lane never started"
        time.sleep(0.05)
    process.send_signal(signal.SIGTERM)
    _, stderr = process.communicate(timeout=30)
    assert process.returncode != 0
    assert "TERMINATED" in log.read_text(), stderr
    assert "Received SIGTERM; stopping make verify" in stderr
    status, phases = _verify_summary(tmp_path)
    assert status == "FAIL"
    assert phases == {"check": "PASS", "test": "INCOMPLETE", "integration": "FAIL"}


@needs_make
def test_only_format_mutates_sources() -> None:
    mutating = re.compile(r"ruff format (?!--check)|--fix|\bsed -i\b")
    for target in ("lint", "format-check", "typecheck", "check", "test", "verify"):
        assert not [line for line in dry_run(target) if mutating.search(line)], target


@needs_make
@pytest.mark.parametrize(
    ("overrides", "version", "port"),
    [
        ([], "11.4", "33000"),
        (["CUBRID_VERSION=11.2", "CUBRID_TEST_PORT=33524"], "11.2", "33524"),
        # INTEGRATION_PORT is the older name, kept for compatibility; it wins when set.
        (["INTEGRATION_PORT=33525"], "11.4", "33525"),
        (["CUBRID_TEST_PORT=33524", "INTEGRATION_PORT=33525"], "11.4", "33525"),
    ],
    ids=["defaults", "overrides", "compat-name", "compat-name-wins"],
)
def test_integration_owns_a_docker_database(overrides: list[str], version: str, port: str) -> None:
    (line,) = dry_run("integration", *overrides)
    argv = shlex.split(line)
    # `exec` makes the runner the recipe's only process, so a SIGTERM that make sends its
    # recipe reaches the runner, which then removes its Compose project (#449).
    assert argv[:3] == ["exec", "python3", "scripts/run_integration.py"]
    assert argv[argv.index("--cubrid-version") + 1] == version
    assert argv[argv.index("--port") + 1] == port
    assert argv[argv.index("--pytest") + 1] == "python3 -m pytest"
    assert argv[argv.index("--results-dir") + 1] == "test-results/integration"


@needs_make
def test_integration_local_uses_an_already_running_database() -> None:
    assert dry_run("integration-local") == ['python3 -m pytest -m "integration" -q']


@needs_make
@pytest.mark.parametrize(
    ("overrides", "version", "port"),
    [([], "11.4", "33000"), (["CUBRID_VERSION=11.2", "CUBRID_TEST_PORT=33400"], "11.2", "33400")],
    ids=["defaults", "overrides"],
)
def test_docker_up_starts_the_compose_service_and_waits(
    overrides: list[str], version: str, port: str
) -> None:
    (line,) = dry_run("docker-up", *overrides)
    assert shlex.split(line) == [
        f"CUBRID_VERSION={version}",
        f"CUBRID_TEST_PORT={port}",
        *COMPOSE,
        "up",
        "--detach",
        "--wait",
        "cubrid",
    ]


@needs_make
def test_docker_down_keeps_the_data_volume_and_docker_clean_deletes_it() -> None:
    (down,) = dry_run("docker-down")
    (clean,) = dry_run("docker-clean")
    assert shlex.split(down) == [*COMPOSE, "down"]
    assert shlex.split(clean) == [*COMPOSE, "down", "--volumes"]


@needs_make
def test_integration_runs_the_docker_up_service_as_a_run_owned_project() -> None:
    # One service definition for both lanes (#402): the runner starts the same file and
    # service as `make docker-up`, but under a unique project name of its own, so it
    # never touches the default project of the persistent lab (#378, #379).
    (up,) = dry_run("docker-up")
    runner = _load_run_integration()
    assert shlex.split(up)[2 : 2 + len(COMPOSE)] == COMPOSE
    assert ["--file", runner.COMPOSE_FILE] == COMPOSE[2:]
    assert shlex.split(up)[-1] == runner.SERVICE
    assert runner.PROJECT_PREFIX == "cubrid-mcp-it-"
    (integration,) = dry_run("integration")
    assert "compose" not in integration  # the runner owns the project lifecycle


def test_compose_service_matches_the_makefile_and_the_integration_runner() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    assert set(compose["services"]) == {"cubrid"}
    service = compose["services"]["cubrid"]
    assert "container_name" not in service  # the project name keeps instances apart
    makefile = (ROOT / "Makefile").read_text()
    version = re.search(r"^CUBRID_VERSION \?= (\S+)$", makefile, re.M)
    port = re.search(r"^CUBRID_TEST_PORT \?= (\S+)$", makefile, re.M)
    assert version is not None and port is not None
    assert service["image"] == f"cubrid/cubrid:${{CUBRID_VERSION:-{version.group(1)}}}"
    # Broker only, loopback only, with the same default port as the Makefile.
    assert service["ports"] == [f"127.0.0.1:${{CUBRID_TEST_PORT:-{port.group(1)}}}:33000"]
    database = _load_run_integration().DATABASE
    assert service["environment"] == {"CUBRID_DB": database, "CUBRID_DB_HOST": "localhost"}
    probe = service["healthcheck"]["test"]
    assert probe[0] == "CMD-SHELL"
    assert f"csql -u dba {database} " in probe[1] and "SELECT 1" in probe[1]
    # The data lives in named volumes, which `docker-down` keeps: images up to 11.3
    # use /var/lib/cubrid, the 11.4 image /home/cubrid/CUBRID/databases.
    mounts = {target: name for name, target in (v.split(":", 1) for v in service["volumes"])}
    assert set(mounts) == {"/var/lib/cubrid", "/home/cubrid/CUBRID/databases"}
    assert set(mounts.values()) <= set(compose["volumes"])


def _load_run_integration() -> Any:
    path = ROOT / "scripts" / "run_integration.py"
    spec = importlib.util.spec_from_file_location("_run_integration_for_compose", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


@needs_make
def test_install_uses_the_selected_python_and_the_dev_group() -> None:
    assert dry_run("install") == ["python3 -m pip install -e . --group dev"]
    assert dry_run("install", "PYTHON=/venv/bin/python") == [
        "/venv/bin/python -m pip install -e . --group dev"
    ]


@needs_make
def test_every_tool_is_bound_to_the_selected_python() -> None:
    selected = "/venv/bin/python"
    expected = {
        "lint": [f"{selected} -m ruff check ."],
        "format-check": [f"{selected} -m ruff format --check ."],
        "typecheck": [f"{selected} -m mypy cubrid_mcp_server"],
    }
    for target, lines in expected.items():
        assert dry_run(target, f"PYTHON={selected}") == lines
    test, *rest = dry_run("test", f"PYTHON={selected}")[1:]
    assert test.startswith(f"{selected} -m pytest -m ")
    assert (
        [line for line in rest if "report_results" in line][0]
        .strip()
        .startswith(f"{selected} scripts/report_results.py")
    )
    (integration,) = dry_run("integration", f"PYTHON={selected}")
    argv = shlex.split(integration)
    assert argv[:3] == ["exec", selected, "scripts/run_integration.py"]
    assert argv[argv.index("--pytest") + 1] == f"{selected} -m pytest"
    # Nothing in the Makefile calls a bare tool that PATH could resolve elsewhere.
    bare = re.compile(r"^\t@?(pip3?|ruff|mypy|pytest)\b", re.M)
    assert not bare.findall((ROOT / "Makefile").read_text())


@needs_make
def test_individual_tool_variables_can_be_overridden() -> None:
    assert dry_run("lint", "RUFF=ruff") == ["ruff check ."]
    assert dry_run("typecheck", "MYPY=mypy --no-incremental") == [
        "mypy --no-incremental cubrid_mcp_server"
    ]
    line = dry_run("test", "PYTEST=pytest")[1]
    assert line.startswith("pytest -m ")


def test_dev_tools_are_a_dependency_group_not_a_package_extra() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "optional-dependencies" not in pyproject["project"]
    assert set(pyproject["dependency-groups"]) == {"dev"}
    dev = " ".join(pyproject["dependency-groups"]["dev"])
    for tool in ("pytest", "ruff==", "mypy==", "build", "twine"):
        assert tool in dev, tool


def test_no_repository_install_command_uses_the_removed_dev_extra() -> None:
    removed = re.compile(r"\.\[dev\]|-e \.\[|\[dev\]\"")
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, text=True, check=True
    ).stdout.split("\0")
    offenders = []
    for name in filter(None, tracked):
        path = ROOT / name
        if path.suffix not in {".md", ".yml", ".yaml", ".py", ".toml", ""} or not path.is_file():
            continue
        # The changelog and this file's own pattern record the history.
        if name in {"CHANGELOG.md", "RELEASE_CHANGELOG.md", "tests/test_makefile.py"}:
            continue
        for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            if removed.search(line):
                offenders.append(f"{name}:{number}: {line.strip()}")
    assert not offenders, offenders


def test_ci_workflows_install_the_dev_group() -> None:
    expected = {
        "ci.yml": {
            "uv pip install --system -e . --group dev",
            "uv pip install --system --resolution lowest-direct -e . --group dev",
        },
        "integration-full.yml": {"uv pip install --system -e . --group dev"},
    }
    for workflow, installs in expected.items():
        text = (WORKFLOWS / workflow).read_text()
        for install in installs:
            assert install in text, (workflow, install)
    canary = (WORKFLOWS / "upstream-canary.yml").read_text()
    assert canary.count("python -m pip install -e . --group dev") == 2
    assert canary.count('python -m pip install --upgrade "pip>=25.1"') == 2
