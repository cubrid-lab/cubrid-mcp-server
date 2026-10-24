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


def test_explicit_junit_path_is_used(tmp_path: Path) -> None:
    junit_path = tmp_path / "other.xml"
    junit(tmp_path, "pass").replace(junit_path)

    summary = summarize(tmp_path, 0, "--junit", str(junit_path))

    assert summary["status"] == "PASS"
    assert summary["counts"]["selected"] == 1
    assert summary["counts"]["passed"] == 1


def test_coverage_is_omitted_when_not_measured(tmp_path: Path) -> None:
    junit(tmp_path, "pass")
    assert "coverage" not in summarize(tmp_path, 0)
    assert "coverage" not in summarize(tmp_path, 0, "--coverage", str(tmp_path / "none.xml"))


@pytest.mark.parametrize(
    "content",
    ["<coverage/>", "<coverage line-rate='abc'/>", "not xml"],
    ids=["missing-rate", "non-numeric-rate", "invalid-xml"],
)
def test_unusable_coverage_is_omitted_without_changing_status(tmp_path: Path, content: str) -> None:
    junit(tmp_path, "pass")
    coverage = tmp_path / "coverage.xml"
    coverage.write_text(content)

    summary = summarize(tmp_path, 0, "--coverage", str(coverage))

    assert summary["status"] == "PASS"
    assert "coverage" not in summary


def test_coverage_is_rounded_and_printed_to_two_decimals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    junit(tmp_path, "pass")
    coverage = tmp_path / "coverage.xml"
    coverage.write_text("<coverage line-rate='0.97126'/>")

    summary = summarize(tmp_path, 0, "--coverage", str(coverage))

    assert summary["coverage"] == {"line_percent": 97.13}
    assert "coverage=97.13%" in capsys.readouterr().out


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


@pytest.mark.parametrize(
    "command",
    [
        "python3 -m pytest -m integration -v",
        "python3 -m pytest --db-url=cubrid://localhost:33000/testdb -k password_test",
        "python3 -m pytest -k 'not password' --no-token -v -k token",
        "python3 -m pytest --db-url=cubrid://dba@localhost:33000/testdb",
        "curl 'http://host:8080/path?a=b@c' PASSWORD= --password=",
    ],
)
def test_redact_command_keeps_a_command_without_credentials_byte_identical(command: str) -> None:
    assert report.redact_command(command) == command


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (
            "python -m pytest --db-url=cubrid://dba:example-secret@localhost:33000/testdb",
            "python -m pytest --db-url=cubrid://dba:***@localhost:33000/testdb",
        ),
        ("x cubrid://dba:p%40ss%2Fw0rd@h:33000/db -v", "x cubrid://dba:***@h:33000/db -v"),
        ("x cubrid://dba:p@ss@localhost/db", "x cubrid://dba:***@localhost/db"),
        ("pytest --password=example-secret -v", "pytest --password=*** -v"),
        ("pytest --password example-secret -v", "pytest --password *** -v"),
        ("PASSWORD=example-secret pytest", "PASSWORD=*** pytest"),
        ("env CUBRID_PASSWORD=example-secret pytest", "env CUBRID_PASSWORD=*** pytest"),
        ("pytest --DB-Passwd='example secret' -v", "pytest --DB-Passwd='***' -v"),
        (
            'API_KEY="example-secret" x --api-key k1 --apikey=k2 --token t3 SECRET=s4 pwd=p5',
            'API_KEY="***" x --api-key *** --apikey=*** --token *** SECRET=*** pwd=***',
        ),
        (
            "curl 'https://u:example-secret@h/x?token=t1&page=2'",
            "curl 'https://u:***@h/x?token=***&page=2'",
        ),
    ],
)
def test_redact_command_masks_url_passwords_and_credential_assignments(
    command: str, expected: str
) -> None:
    redacted = report.redact_command(command)
    assert redacted == expected
    assert report.redact_command(redacted) == redacted  # idempotent


def test_redact_command_scans_a_long_dotted_word_once() -> None:
    # A scheme match may only start at a word start, so "a.a.a..." is not rescanned
    # from every "." (that made a 100k-character command take seconds).
    noise = "a." * 50_000
    command = f"{noise} x://u:example-secret@h"

    assert report.redact_command(command) == f"{noise} x://u:***@h"


def test_environment_json_redacts_credentials_in_the_command(tmp_path: Path) -> None:
    command = (
        "python3 -m pytest --db-url=cubrid://dba:example-secret@localhost:33000/testdb"
        " --password example-token -m integration -v"
    )
    code = report.main(
        ["environment", "--lane", "integration", "--results-dir", str(tmp_path),
         "--command", command, "--cubrid-version", "11.4"]
    )  # fmt: skip
    assert code == 0
    text = (tmp_path / "environment.json").read_text()
    assert "example-secret" not in text and "example-token" not in text
    data = json.loads(text)
    assert data["command"] == (
        "python3 -m pytest --db-url=cubrid://dba:***@localhost:33000/testdb"
        " --password *** -m integration -v"
    )
    assert set(data) == {
        "schema_version", "lane", "command", "python", "package", "cubrid_version", "platform"
    }  # fmt: skip


def test_environment_without_cubrid_version_writes_null(tmp_path: Path) -> None:
    code = report.main(
        ["environment", "--lane", "t", "--results-dir", str(tmp_path), "--command", "test"]
    )

    assert code == 0
    data = json.loads((tmp_path / "environment.json").read_text())
    assert data["cubrid_version"] is None


def test_script_runs_standalone_and_keeps_exit_status_zero(tmp_path: Path) -> None:
    junit(tmp_path, "fail")
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "summarize", "--lane", "t", "--results-dir", str(tmp_path),
         "--exit-code", "1"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert done.returncode == 0  # the caller keeps pytest's own status
    assert done.stdout.startswith("t: FAIL selected=1 passed=0 failed=1")


def test_step_summary_renders_the_console_line_of_summary_json(tmp_path: Path, capsys: Any) -> None:
    junit(tmp_path, "pass", "pass")
    summary = summarize(tmp_path, 0)
    capsys.readouterr()
    assert report.main(["step-summary", "--results-dir", str(tmp_path), "--title", "Unit"]) == 0
    assert capsys.readouterr().out == f"### Unit\n\n`{report.console_line(summary)}`\n"


@pytest.mark.parametrize("content", [None, "{not json", '{"lane": "t"}'])
def test_step_summary_reports_a_missing_or_unreadable_summary(
    tmp_path: Path, capsys: Any, content: str | None
) -> None:
    if content is not None:
        (tmp_path / "summary.json").write_text(content)
    assert report.main(["step-summary", "--results-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("### Test results\n\n")
    assert "No readable" in out
