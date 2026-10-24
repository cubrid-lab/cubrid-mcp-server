"""Offline tests for scripts/report_results.py, the test-results/ reporter (#405)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "report_results.py"

_spec = importlib.util.spec_from_file_location("_report_results", SCRIPT)
assert _spec is not None and _spec.loader is not None
report = importlib.util.module_from_spec(_spec)
sys.modules["_report_results"] = report
_spec.loader.exec_module(report)

CASES = {
    "pass": "<testcase name='p'/>",
    "fail": "<testcase name='f'><failure message='x'/></testcase>",
    "error": "<testcase name='e'><error message='x'/></testcase>",
    "skip": "<testcase name='s'><skipped type='pytest.skip'/></testcase>",
    "xfail": "<testcase name='x'><skipped type='pytest.xfail'/></testcase>",
}


def junit(tmp_path: Path, *kinds: str) -> Path:
    path = tmp_path / "junit.xml"
    # A distinct name per record: repeated names are one test with several records.
    cases = "".join(CASES[k].replace("name='", f"name='{i}", 1) for i, k in enumerate(kinds))
    path.write_text(f"<testsuites><testsuite name='pytest'>{cases}</testsuite></testsuites>")
    return path


def summarize(tmp_path: Path, exit_code: int, *args: str) -> dict[str, Any]:
    assert (
        report.main(
            [
                "summarize",
                "--lane",
                "t",
                "--results-dir",
                str(tmp_path),
                "--exit-code",
                str(exit_code),
                *args,
            ]
        )
        == 0
    )
    return dict(json.loads((tmp_path / "summary.json").read_text()))


def test_pass_counts_and_console_line_match_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    junit(tmp_path, "pass", "pass", "skip", "xfail")
    (tmp_path / "coverage.xml").write_text("<coverage line-rate='0.9712'/>")
    summary = summarize(tmp_path, 0, "--coverage", str(tmp_path / "coverage.xml"))
    assert summary["schema_version"] == 1
    assert summary["status"] == "PASS"
    assert summary["counts"] == {
        "selected": 4, "passed": 2, "failed": 0, "errors": 0,
        "skipped": 1, "xfailed": 1, "xpassed": 0,
    }  # fmt: skip
    assert summary["coverage"] == {"line_percent": 97.12}
    line = capsys.readouterr().out.strip()
    assert line == report.console_line(summary) + f" -> {tmp_path / 'summary.json'}"
    assert "PASS" in line and "passed=2" in line and "coverage=97.12%" in line


@pytest.mark.parametrize("kind", ["fail", "error"])
def test_failure_or_error_is_fail_even_with_exit_zero(tmp_path: Path, kind: str) -> None:
    junit(tmp_path, "pass", kind)
    assert summarize(tmp_path, 0)["status"] == "FAIL"


def test_a_test_with_a_failing_teardown_is_counted_once(tmp_path: Path) -> None:
    # pytest writes two <testcase> records when a test fails and its teardown errors.
    path = tmp_path / "junit.xml"
    path.write_text(
        "<testsuites><testsuite name='pytest' tests='2'>"
        "<testcase classname='m' name='t'><failure message='call'/></testcase>"
        "<testcase classname='m' name='t'><error message='teardown'/></testcase>"
        "<testcase classname='m' name='ok'/>"
        "</testsuite></testsuites>"
    )
    summary = summarize(tmp_path, 1)
    assert summary["counts"]["selected"] == 2
    assert summary["counts"]["errors"] == 1 and summary["counts"]["failed"] == 0
    assert summary["counts"]["passed"] == 1
    assert summary["status"] == "FAIL"


def test_nonzero_exit_without_failed_tests_is_fail(tmp_path: Path) -> None:
    junit(tmp_path, "pass")  # e.g. the coverage floor was missed
    assert summarize(tmp_path, 1)["status"] == "FAIL"


@pytest.mark.parametrize("kinds", [("skip",), ("skip", "xfail"), ()], ids=["skip", "mixed", "none"])
@pytest.mark.parametrize("exit_code", [0, 5])
def test_nothing_passed_is_incomplete_never_pass(
    tmp_path: Path, kinds: tuple[str, ...], exit_code: int
) -> None:
    junit(tmp_path, *kinds)
    assert summarize(tmp_path, exit_code)["status"] == "INCOMPLETE"


def test_missing_junit_is_incomplete_after_success_and_fail_after_failure(tmp_path: Path) -> None:
    assert summarize(tmp_path, 0)["status"] == "INCOMPLETE"
    assert summarize(tmp_path, 2)["status"] == "FAIL"
    (tmp_path / "junit.xml").write_text("not xml")
    assert summarize(tmp_path, 0)["status"] == "INCOMPLETE"


def test_coverage_is_omitted_when_not_measured(tmp_path: Path) -> None:
    junit(tmp_path, "pass")
    assert "coverage" not in summarize(tmp_path, 0)
    assert "coverage" not in summarize(tmp_path, 0, "--coverage", str(tmp_path / "none.xml"))


def test_environment_json_never_contains_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CUBRID_PASSWORD", "s3cr3t-pass")
    monkeypatch.setenv("CUBRID_USER", "secret-user")
    code = report.main(
        ["environment", "--lane", "integration", "--results-dir", str(tmp_path),
         "--command", "python3 -m pytest -m integration -v", "--cubrid-version", "11.4"]
    )  # fmt: skip
    assert code == 0
    text = (tmp_path / "environment.json").read_text()
    assert "s3cr3t-pass" not in text and "secret-user" not in text
    data = json.loads(text)
    assert data["cubrid_version"] == "11.4"
    assert data["package"]["version"] == report.package_version() != "unknown"
    assert {"python", "platform", "command", "lane", "schema_version"} <= set(data)


def test_script_runs_standalone_and_keeps_exit_status_zero(tmp_path: Path) -> None:
    junit(tmp_path, "fail")
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "summarize", "--lane", "t", "--results-dir", str(tmp_path),
         "--exit-code", "1"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert done.returncode == 0  # the caller keeps pytest's own status
    assert done.stdout.startswith("t: FAIL selected=1 passed=0 failed=1")
