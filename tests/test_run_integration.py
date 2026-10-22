"""Offline tests for scripts/run_integration.py, the ``make integration`` lifecycle (#379).

A fake ``docker`` on ``PATH`` records every call, so these tests need neither Docker
nor CUBRID. They pin that the run-owned container is always removed, on success,
failure, a readiness timeout and SIGINT/SIGTERM, and that exit statuses propagate.
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

FAKE_DOCKER = """\
#!{python}
import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps(["docker", *sys.argv[1:]]) + "\\n")
command = sys.argv[1]
if command == "rm":
    status = int(os.environ.get("FAKE_RM_STATUS", "0"))
    if status:
        sys.stderr.write(os.environ.get("FAKE_RM_STDERR", "rm failed") + "\\n")
    sys.exit(status)
if command == "logs":
    print("fake cubrid log")
sys.exit(int(os.environ.get("FAKE_" + command.upper() + "_STATUS", "0")))
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
    # A stray export must not redirect the run to another server.
    monkeypatch.setenv("CUBRID_HOST", "db.example.invalid")
    monkeypatch.setenv("CUBRID_PORT", "1")
    monkeypatch.setattr(run_integration, "READY_INTERVAL", 0.0)
    return {
        "log": log,
        "args": ["--cubrid-version", "11.2", "--port", "33524", "--pytest"]
        + [f"{sys.executable} {fake_pytest}"],
    }


def calls(fake: dict[str, Any]) -> list[list[Any]]:
    return [json.loads(line) for line in fake["log"].read_text().splitlines()]


def docker_commands(fake: dict[str, Any]) -> list[str]:
    return [c[1] for c in calls(fake) if c[0] == "docker"]


def container_name(fake: dict[str, Any]) -> str:
    (run,) = [c for c in calls(fake) if c[:2] == ["docker", "run"]]
    return str(run[run.index("--name") + 1])


def assert_removed(fake: dict[str, Any]) -> None:
    name = container_name(fake)
    assert name.startswith("cubrid-mcp-it-")
    assert ["docker", "rm", "-f", "-v", name] in calls(fake)
    assert calls(fake)[-1][:2] == ["docker", "rm"]


def test_success_runs_the_lane_and_removes_the_container(fake: dict[str, Any]) -> None:
    assert run_integration.main(fake["args"]) == 0
    (run,) = [c for c in calls(fake) if c[:2] == ["docker", "run"]]
    assert run[-1] == "cubrid/cubrid:11.2"
    assert run[run.index("-p") + 1] == "33524:33000"
    assert "CUBRID_DB=demodb" in run
    (pytest_call,) = [c for c in calls(fake) if c[0] == "pytest"]
    assert pytest_call[1:-1] == ["-m", "integration", "-v"]
    assert pytest_call[-1] == {
        "CUBRID_HOST": "127.0.0.1",
        "CUBRID_PORT": "33524",
        "CUBRID_USER": "dba",
        "CUBRID_PASSWORD": "",
        "CUBRID_DATABASE": "demodb",
    }
    assert "logs" not in docker_commands(fake)
    assert_removed(fake)


def test_test_failure_propagates_dumps_logs_and_cleans_up(
    fake: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FAKE_PYTEST_STATUS", "3")
    assert run_integration.main(fake["args"]) == 3
    assert "logs" in docker_commands(fake)
    assert_removed(fake)


def test_start_failure_propagates_and_absent_container_is_not_a_cleanup_error(
    fake: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_RUN_STATUS", "125")
    monkeypatch.setenv("FAKE_RM_STATUS", "1")
    monkeypatch.setenv("FAKE_RM_STDERR", "Error response from daemon: No such container: x")
    assert run_integration.main(fake["args"]) == 125
    assert "exec" not in docker_commands(fake)
    assert not [c for c in calls(fake) if c[0] == "pytest"]
    assert_removed(fake)


def test_readiness_timeout_fails_without_running_tests(
    fake: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run_integration, "READY_ATTEMPTS", 3)
    monkeypatch.setenv("FAKE_EXEC_STATUS", "1")
    assert run_integration.main(fake["args"]) == 1
    assert docker_commands(fake).count("exec") == 3
    assert not [c for c in calls(fake) if c[0] == "pytest"]
    assert_removed(fake)


def test_cleanup_failure_fails_a_successful_run(
    fake: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_RM_STATUS", "7")
    assert run_integration.main(fake["args"]) == 7


def test_cleanup_failure_never_hides_an_earlier_failure(
    fake: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_PYTEST_STATUS", "2")
    monkeypatch.setenv("FAKE_RM_STATUS", "7")
    assert run_integration.main(fake["args"]) == 2


def test_missing_docker_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    status = run_integration.main(["--cubrid-version", "11.4", "--port", "1", "--pytest", "true"])
    assert status == 127


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM], ids=["SIGINT", "SIGTERM"])
def test_signal_stops_the_tests_and_still_cleans_up(
    fake: dict[str, Any], monkeypatch: pytest.MonkeyPatch, sig: signal.Signals
) -> None:
    monkeypatch.setenv("FAKE_PYTEST_SLEEP", "60")
    proc = subprocess.Popen([sys.executable, str(SCRIPT), *fake["args"]])
    deadline = time.monotonic() + 30
    while not [c for c in calls(fake) if c[0] == "pytest"]:
        assert time.monotonic() < deadline, "fake pytest never started"
        assert proc.poll() is None
        time.sleep(0.05)
    proc.send_signal(sig)
    assert proc.wait(timeout=30) == 128 + sig
    assert "logs" not in docker_commands(fake)
    assert_removed(fake)
