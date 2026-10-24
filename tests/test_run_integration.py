"""Offline tests for scripts/run_integration.py, the ``make integration`` lifecycle (#379).

A fake ``docker`` on ``PATH`` records every ``docker compose`` call and the variables
it would interpolate, so these tests need neither Docker nor CUBRID. They pin that the
run-owned Compose project (#402) is always taken down with its volumes, on success,
failure, a readiness failure and SIGINT/SIGTERM, and that exit statuses propagate.
"""

from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_integration.py"

_spec = importlib.util.spec_from_file_location("_run_integration", SCRIPT)
assert _spec is not None and _spec.loader is not None
run_integration = importlib.util.module_from_spec(_spec)
sys.modules["_run_integration"] = run_integration
_spec.loader.exec_module(run_integration)

# Only `docker compose --file F --project-name P <command> ...` is a valid call.
FAKE_DOCKER = """\
#!{python}
import json, os, sys, time
args = sys.argv[1:]
keys = ("CUBRID_VERSION", "CUBRID_TEST_PORT")
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps(["docker", *args, {{k: os.environ.get(k) for k in keys}}]) + "\\n")
if args[:2] != ["compose", "--file"] or args[3] != "--project-name":
    sys.exit("fake docker: unexpected call")
command = args[5]
if command == "logs":
    print("fake cubrid log")
if command == "up" and os.environ.get("FAKE_UP_SLEEP"):
    time.sleep(float(os.environ["FAKE_UP_SLEEP"]))
status = int(os.environ.get("FAKE_" + command.upper() + "_STATUS", "0"))
if status:
    sys.stderr.write(command + " failed\\n")
sys.exit(status)
"""

FAKE_PYTEST = """\
import json, os, sys, time
keys = ("CUBRID_HOST", "CUBRID_PORT", "CUBRID_USER", "CUBRID_PASSWORD", "CUBRID_DATABASE")
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps(["pytest", *sys.argv[1:], {k: os.environ.get(k) for k in keys}]) + "\\n")
if os.environ.get("FAKE_PYTEST_SLEEP"):
    time.sleep(float(os.environ["FAKE_PYTEST_SLEEP"]))
sys.exit(int(os.environ.get("FAKE_PYTEST_STATUS", "0")))
"""


@pytest.fixture
def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(FAKE_DOCKER.format(python=sys.executable))
    docker.chmod(0o755)
    fake_pytest = tmp_path / "fake_pytest.py"
    fake_pytest.write_text(FAKE_PYTEST)
    log = tmp_path / "calls.jsonl"
    log.touch()
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_LOG", str(log))
    # A stray export must not redirect the run to another server or project.
    monkeypatch.setenv("CUBRID_HOST", "db.example.invalid")
    monkeypatch.setenv("CUBRID_PORT", "1")
    monkeypatch.setenv("CUBRID_TEST_PORT", "2")
    monkeypatch.setenv("CUBRID_VERSION", "9.9")
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "someone-elses-lab")
    return {
        "log": log,
        "args": ["--cubrid-version", "11.2", "--port", "33524", "--pytest"]
        + [f"{sys.executable} {fake_pytest}"],
    }


def calls(fake: dict[str, Any]) -> list[list[Any]]:
    return [json.loads(line) for line in fake["log"].read_text().splitlines()]


def compose_calls(fake: dict[str, Any]) -> list[list[Any]]:
    return [c for c in calls(fake) if c[0] == "docker"]


def compose_commands(fake: dict[str, Any]) -> list[str]:
    return [str(c[6]) for c in compose_calls(fake)]


def project_name(fake: dict[str, Any]) -> str:
    (project,) = {str(c[5]) for c in compose_calls(fake)}
    return project


def assert_taken_down(fake: dict[str, Any]) -> None:
    project = project_name(fake)
    assert project.startswith("cubrid-mcp-it-") and len(project) == len("cubrid-mcp-it-") + 12
    down = ["docker", "compose", "--file", "docker-compose.yml", "--project-name", project]
    assert compose_calls(fake)[-1] == [
        *down,
        "down",
        "--volumes",
        {"CUBRID_VERSION": "11.2", "CUBRID_TEST_PORT": "33524"},
    ]
    assert compose_commands(fake).count("down") == 1


def test_success_runs_the_lane_and_takes_the_project_down(fake: dict[str, Any]) -> None:
    assert run_integration.main(fake["args"]) == 0
    up = compose_calls(fake)[0]
    assert up[:4] == ["docker", "compose", "--file", "docker-compose.yml"]
    assert up[6:] == [
        "up",
        "--detach",
        "--wait",
        "cubrid",
        {"CUBRID_VERSION": "11.2", "CUBRID_TEST_PORT": "33524"},
    ]
    (pytest_call,) = [c for c in calls(fake) if c[0] == "pytest"]
    assert pytest_call[1:-1] == ["-m", "integration", "-v"]
    assert pytest_call[-1] == {
        "CUBRID_HOST": "127.0.0.1",
        "CUBRID_PORT": "33524",
        "CUBRID_USER": "dba",
        "CUBRID_PASSWORD": "",
        "CUBRID_DATABASE": "demodb",
    }
    assert compose_commands(fake) == ["up", "down"]
    assert_taken_down(fake)


def test_each_run_owns_a_fresh_project(fake: dict[str, Any]) -> None:
    assert run_integration.main(fake["args"]) == 0
    first = project_name(fake)
    fake["log"].write_text("")
    assert run_integration.main(fake["args"]) == 0
    assert project_name(fake) != first


def test_test_failure_propagates_dumps_logs_and_cleans_up(
    fake: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FAKE_PYTEST_STATUS", "3")
    assert run_integration.main(fake["args"]) == 3
    assert compose_commands(fake) == ["up", "logs", "down"]
    (logs,) = [c for c in compose_calls(fake) if c[6] == "logs"]
    assert logs[7:-1] == ["--no-color", "cubrid"]
    assert_taken_down(fake)


def test_start_or_readiness_failure_fails_without_running_tests(
    fake: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    # `up --wait` fails when the service cannot start or its health check turns
    # unhealthy (the readiness timeout); either way the project is still taken down.
    monkeypatch.setenv("FAKE_UP_STATUS", "125")
    assert run_integration.main(fake["args"]) == 125
    assert not [c for c in calls(fake) if c[0] == "pytest"]
    assert compose_commands(fake) == ["up", "logs", "down"]
    assert_taken_down(fake)


def test_cleanup_failure_fails_a_successful_run(
    fake: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FAKE_DOWN_STATUS", "7")
    assert run_integration.main(fake["args"]) == 7
    assert "down failed" in capsys.readouterr().err


def test_cleanup_failure_never_hides_an_earlier_failure(
    fake: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_PYTEST_STATUS", "2")
    monkeypatch.setenv("FAKE_DOWN_STATUS", "7")
    assert run_integration.main(fake["args"]) == 2


def test_missing_docker_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    status = run_integration.main(["--cubrid-version", "11.4", "--port", "1", "--pytest", "true"])
    assert status == 127


def test_runner_uses_the_docker_up_service() -> None:
    assert (ROOT / run_integration.COMPOSE_FILE).is_file()
    assert run_integration.SERVICE == "cubrid"


@pytest.mark.parametrize("step", ["up", "pytest"], ids=["during-up", "during-tests"])
@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM], ids=["SIGINT", "SIGTERM"])
def test_signal_stops_the_running_step_and_still_cleans_up(
    fake: dict[str, Any], monkeypatch: pytest.MonkeyPatch, sig: signal.Signals, step: str
) -> None:
    monkeypatch.setenv("FAKE_UP_SLEEP" if step == "up" else "FAKE_PYTEST_SLEEP", "60")
    proc = subprocess.Popen([sys.executable, str(SCRIPT), *fake["args"]])

    def started() -> bool:
        if step == "pytest":
            return any(c[0] == "pytest" for c in calls(fake))
        return "up" in compose_commands(fake)

    deadline = time.monotonic() + 30
    while not started():
        assert time.monotonic() < deadline, f"fake {step} never started"
        assert proc.poll() is None
        time.sleep(0.05)
    proc.send_signal(sig)
    assert proc.wait(timeout=30) == 128 + sig
    if step == "up":
        assert not [c for c in calls(fake) if c[0] == "pytest"]
    assert "logs" not in compose_commands(fake)
    assert_taken_down(fake)


def reporting_args(fake: dict[str, Any], results: Path) -> list[str]:
    return [*fake["args"], "--results-dir", str(results)]


def test_results_dir_gets_junit_environment_and_summary(
    fake: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("CUBRID_PASSWORD", "s3cr3t-pass")
    results = tmp_path / "results"
    results.mkdir()
    (results / "summary.json").write_text("stale")
    assert run_integration.main(reporting_args(fake, results)) == 0
    (pytest_call,) = [c for c in calls(fake) if c[0] == "pytest"]
    assert pytest_call[1:-1] == [
        "-m",
        "integration",
        "-v",
        "--junitxml",
        str(results / "junit.xml"),
    ]
    environment = (results / "environment.json").read_text()
    assert "s3cr3t-pass" not in environment
    assert json.loads(environment)["cubrid_version"] == "11.2"
    # The fake pytest writes no JUnit file, so nothing proves the lane ran.
    summary = json.loads((results / "summary.json").read_text())
    assert summary["status"] == "INCOMPLETE"
    assert not (results / "logs").exists()
    assert capfd.readouterr().out.strip().splitlines()[-1].startswith("integration: INCOMPLETE")


def test_results_dir_failure_writes_the_service_log_and_fails(
    fake: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("FAKE_PYTEST_STATUS", "3")
    results = tmp_path / "results"
    assert run_integration.main(reporting_args(fake, results)) == 3
    assert (results / "logs" / "cubrid.log").read_text() == "fake cubrid log\n"
    summary = json.loads((results / "summary.json").read_text())
    assert summary["status"] == "FAIL" and summary["exit_code"] == 3
    out = capfd.readouterr().out
    assert "fake cubrid log" in out
    assert out.strip().splitlines()[-1].startswith("integration: FAIL")
    assert_taken_down(fake)


def test_an_unwritable_service_log_never_skips_cleanup(
    fake: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    # The failure log is best-effort: an I/O error saving it must still take the
    # project down and keep the lane's own exit status.
    monkeypatch.setenv("FAKE_PYTEST_STATUS", "3")
    real_open = Path.open

    def failing_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self.name == "cubrid.log":
            raise PermissionError(13, "Permission denied", str(self))
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", failing_open)
    results = tmp_path / "results"
    assert run_integration.main(reporting_args(fake, results)) == 3
    assert_taken_down(fake)
    summary = json.loads((results / "summary.json").read_text())
    assert summary["status"] == "FAIL" and summary["exit_code"] == 3
    assert "could not save the service log" in capfd.readouterr().err
