"""Offline tests for scripts/run_verify.py, the ``make verify`` runner (#449).

A fake ``make`` stands in for the phases, so these tests need neither Docker nor CUBRID.
The Makefile-level behavior (order, ``make -j``, SIGTERM to make) is in test_makefile.py.
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_verify.py"


def _fake_make(tmp_path: Path, *, block: str = "") -> tuple[Path, Path]:
    """A make that logs its phase; the *block* phase waits for a signal and logs it."""
    log = tmp_path / "make.log"
    make = tmp_path / "make"
    script = f'#!/bin/sh\necho "$2" >> "{log}"\n'
    if block:
        script += (
            f'if [ "$2" = "{block}" ]; then\n'
            "  sleep 30 & pid=$!\n"
            + "".join(
                f"  trap 'kill $pid; echo GOT-{name} >> \"{log}\"; exit {128 + sig}' {name}\n"
                for name, sig in (("INT", 2), ("TERM", 15), ("HUP", 1))
            )
            + f'  echo BLOCKING >> "{log}"\n  wait $pid\nfi\n'
        )
    make.write_text(script + "exit 0\n")
    make.chmod(0o755)
    return make, log


def _args(tmp_path: Path, make: Path | str) -> list[str]:
    return [
        "--make", str(make),
        "--results-dir", str(tmp_path / "verify"),
        "--test-results", str(tmp_path / "test"),
        "--integration-results", str(tmp_path / "integration"),
    ]  # fmt: skip


def _summary(tmp_path: Path) -> dict[str, Any]:
    return dict(json.loads((tmp_path / "verify" / "summary.json").read_text()))


@pytest.mark.parametrize(
    "sig", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP], ids=["SIGINT", "SIGTERM", "SIGHUP"]
)
def test_a_signal_is_forwarded_to_the_running_phase_and_the_summary_is_written(
    tmp_path: Path, sig: signal.Signals
) -> None:
    make, log = _fake_make(tmp_path, block="test")
    process = subprocess.Popen(
        [sys.executable, str(SCRIPT), *_args(tmp_path, make)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        # A background job starts with SIGINT ignored, which the runner keeps; reset it.
        preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL),
    )  # fmt: skip
    deadline = time.monotonic() + 30
    while "BLOCKING" not in (log.read_text() if log.exists() else ""):
        assert process.poll() is None and time.monotonic() < deadline, "phase never started"
        time.sleep(0.05)
    process.send_signal(sig)
    stdout, stderr = process.communicate(timeout=30)
    assert process.returncode == 128 + sig
    assert f"Received {sig.name}; stopping make verify" in stderr
    assert log.read_text().splitlines() == ["check", "test", "BLOCKING", f"GOT-{sig.name[3:]}"]
    summary = _summary(tmp_path)
    assert summary["status"] == "FAIL"
    phases = {p["name"]: (p["status"], p["exit_code"]) for p in summary["phases"]}
    assert phases == {
        "check": ("PASS", 0),
        "test": ("FAIL", 128 + sig),
        "integration": ("NOT_RUN", None),
    }
    assert stdout.splitlines()[-1].startswith("verify: FAIL check=PASS test=FAIL ")


def test_a_make_that_cannot_start_fails_the_first_phase(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *_args(tmp_path, tmp_path / "no-such-make")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert result.returncode == 127
    summary = _summary(tmp_path)
    assert [(p["name"], p["status"]) for p in summary["phases"]] == [
        ("check", "FAIL"),
        ("test", "NOT_RUN"),
        ("integration", "NOT_RUN"),
    ]


def test_every_phase_exiting_zero_without_lane_summaries_is_not_pass(tmp_path: Path) -> None:
    make, log = _fake_make(tmp_path)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *_args(tmp_path, make)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert log.read_text().splitlines() == ["check", "test", "integration"]
    assert result.returncode == 1
    assert _summary(tmp_path)["status"] == "INCOMPLETE"
