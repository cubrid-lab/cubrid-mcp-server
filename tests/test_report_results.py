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


def _lane(tmp_path: Path, name: str, status: object) -> Path:
    path = tmp_path / name / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"lane": name, "status": status}))
    return path


def _statuses(summary: dict[str, Any]) -> dict[str, str]:
    return {phase["name"]: phase["status"] for phase in summary["phases"]}


def test_aggregate_passes_only_when_every_phase_passed(tmp_path: Path) -> None:
    summary = report.build_aggregate(
        [
            ("check", 0, None),
            ("test", 0, _lane(tmp_path, "test", "PASS")),
            ("integration", 0, _lane(tmp_path, "integration", "PASS")),
        ]
    )
    assert summary["schema_version"] == report.SCHEMA_VERSION
    assert summary["lane"] == "verify"
    assert summary["status"] == "PASS"
    assert summary["problems"] == []
    assert [phase["name"] for phase in summary["phases"]] == ["check", "test", "integration"]
    assert summary["phases"][0] == {
        "name": "check",
        "status": "PASS",
        "exit_code": 0,
        "summary": None,
        "summary_status": None,
    }


@pytest.mark.parametrize(
    ("exit_code", "lane_status", "expected"),
    [
        # The lane's own verdict wins over a zero exit status: an all-skipped live lane
        # is INCOMPLETE, never PASS.
        (0, "INCOMPLETE", "INCOMPLETE"),
        (0, "FAIL", "FAIL"),
        # A non-zero exit status is a failure even next to a PASS summary.
        (1, "PASS", "FAIL"),
    ],
)
def test_aggregate_takes_the_worst_lane_verdict(
    tmp_path: Path, exit_code: int, lane_status: str, expected: str
) -> None:
    summary = report.build_aggregate(
        [("test", 0, _lane(tmp_path, "test", "PASS")),
         ("integration", exit_code, _lane(tmp_path, "integration", lane_status))]
    )  # fmt: skip
    assert summary["status"] == expected
    assert _statuses(summary)["integration"] == expected


def test_aggregate_never_passes_a_phase_that_did_not_run(tmp_path: Path) -> None:
    summary = report.build_aggregate(
        [("check", 0, None), ("test", 0, _lane(tmp_path, "test", "PASS")),
         ("integration", None, tmp_path / "integration" / "summary.json")]
    )  # fmt: skip
    assert summary["status"] == "INCOMPLETE"
    assert _statuses(summary)["integration"] == "NOT_RUN"
    assert summary["phases"][2]["exit_code"] is None
    assert "integration did not run" in summary["problems"]


def test_aggregate_without_phases_is_incomplete() -> None:
    summary = report.build_aggregate([])
    assert summary["status"] == "INCOMPLETE"
    assert summary["problems"] == ["no phase was given"]


@pytest.mark.parametrize(
    "content",
    [None, "not json", "[]", "{}", '{"status": "GREEN"}', '{"status": []}', '{"status": 1}',
     '{"status": null}'],
    ids=["missing", "not-json", "not-an-object", "no-status", "unknown", "list", "int", "null"],
)  # fmt: skip
def test_aggregate_never_passes_a_missing_unreadable_or_non_string_lane_status(
    tmp_path: Path, content: str | None
) -> None:
    path = tmp_path / "integration" / "summary.json"
    if content is not None:
        path.parent.mkdir(parents=True)
        path.write_text(content)
    summary = report.build_aggregate([("integration", 0, path)])
    assert summary["status"] == "INCOMPLETE"
    assert summary["phases"][0]["summary_status"] is None
    assert summary["problems"]


def test_aggregate_writes_the_summary_junit_and_environment_masked(
    tmp_path: Path, capsys: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CUBRID_PASSWORD", "top&secret")
    monkeypatch.setenv("CUBRID_CONNECTIONS", "reports")
    monkeypatch.setenv("CUBRID_REPORTS_PASSWORD", "r3ports pw")
    lanes = tmp_path / "lanes"
    test_summary = _lane(lanes, "test", "PASS")
    live_summary = _lane(lanes, "integration", "PASS")
    # A failing test can print a configured credential into its JUnit report, raw,
    # XML-escaped or percent-encoded.
    (lanes / "test" / "junit.xml").write_text(
        "<testsuites>top&amp;secret top%26secret r3ports%20pw r3ports pw</testsuites>"
    )
    (lanes / "integration" / "junit.xml").write_text("<testsuites/>")
    (lanes / "integration" / "environment.json").write_text('{"command": "x top&secret"}')
    output = tmp_path / "verify" / "summary.json"
    code = report.main(
        [
            "aggregate", "--output", str(output),
            "--phase", "check=0",
            "--phase", f"test=0:{test_summary}",
            "--phase", f"integration=0:{live_summary}",
            "--copy-junit", f"test={lanes / 'test' / 'junit.xml'}",
            "--copy-junit", f"integration={lanes / 'integration' / 'junit.xml'}",
            "--copy-junit", f"missing={lanes / 'missing.xml'}",
            "--environment", str(lanes / "integration" / "environment.json"),
        ]
    )  # fmt: skip
    assert code == 0
    summary = json.loads(output.read_text())
    assert summary["status"] == "PASS"
    verify = output.parent
    assert sorted(p.name for p in (verify / "junit").iterdir()) == ["integration.xml", "test.xml"]
    assert (verify / "junit" / "test.xml").read_text() == (
        "<testsuites>*** *** *** ***</testsuites>"
    )
    assert (verify / "environment.json").read_text() == '{"command": "x ***"}'
    for path in verify.rglob("*"):
        if path.is_file():
            text = path.read_text()
            assert "secret" not in text and "r3ports" not in text
    line = capsys.readouterr().out.strip()
    assert line == f"verify: PASS check=PASS test=PASS integration=PASS -> {output}"
    assert line.split(" -> ")[0] == report.console_line(summary)


def test_aggregate_exits_nonzero_unless_pass(tmp_path: Path, capsys: Any) -> None:
    output = tmp_path / "summary.json"
    assert report.main(["aggregate", "--output", str(output), "--phase", "check=2",
                        "--phase", "test=not-run", "--phase", "integration=not-run"]) == 1  # fmt: skip
    assert json.loads(output.read_text())["status"] == "FAIL"
    out = capsys.readouterr().out
    assert out.startswith("verify: FAIL check=FAIL test=NOT_RUN integration=NOT_RUN [")


@pytest.mark.parametrize("phase", ["check=ok", "check", "=0"])
def test_aggregate_rejects_a_malformed_phase(tmp_path: Path, phase: str) -> None:
    with pytest.raises(SystemExit):
        report.main(["aggregate", "--output", str(tmp_path / "s.json"), "--phase", phase])


@pytest.mark.parametrize("pair", ["test", "test=", "=x.xml"])
def test_aggregate_rejects_a_malformed_junit_copy(tmp_path: Path, pair: str) -> None:
    with pytest.raises(SystemExit):
        report.main(["aggregate", "--output", str(tmp_path / "s.json"), "--copy-junit", pair])


def test_aggregate_records_a_result_file_it_cannot_copy(tmp_path: Path) -> None:
    lane = _lane(tmp_path, "integration", "PASS")
    unreadable = tmp_path / "integration" / "junit.xml"
    unreadable.mkdir()  # exists, but reading it fails
    output = tmp_path / "verify" / "summary.json"
    code = report.main(
        ["aggregate", "--output", str(output), "--phase", f"integration=0:{lane}",
         "--copy-junit", f"integration={unreadable}"]
    )  # fmt: skip
    assert code == 1
    summary = json.loads(output.read_text())
    assert summary["status"] == "INCOMPLETE"
    assert _statuses(summary) == {"integration": "PASS"}
    assert any("could not copy" in problem for problem in summary["problems"])
    assert not (output.parent / "junit" / "integration.xml").exists()


def test_step_summary_renders_the_verify_summary(tmp_path: Path, capsys: Any) -> None:
    report.main(["aggregate", "--output", str(tmp_path / "summary.json"), "--phase", "check=0",
                 "--phase", "integration=not-run"])  # fmt: skip
    capsys.readouterr()
    assert report.main(["step-summary", "--results-dir", str(tmp_path), "--title", "Verify"]) == 0
    assert capsys.readouterr().out.startswith(
        "### Verify\n\n`verify: INCOMPLETE check=PASS integration=NOT_RUN ["
    )


def test_configured_secrets_are_the_passwords_the_server_reads() -> None:
    # Parity with ConnectionRegistry.from_env: the default and every named connection.
    from cubrid_mcp_server.config import ConnectionRegistry

    env = {"CUBRID_CONNECTIONS": " a , Reports ,"}
    for prefix, password in (("CUBRID_", "d&fault"), ("CUBRID_A_", "a%2Fb"),
                             ("CUBRID_REPORTS_", "r3ports")):  # fmt: skip
        env |= {f"{prefix}HOST": "h", f"{prefix}USER": "u", f"{prefix}DATABASE": "d",
                f"{prefix}PASSWORD": password}  # fmt: skip
    env["CUBRID_OTHER_PASSWORD"] = "not-a-connection"
    registry = ConnectionRegistry.from_env(env)
    passwords = {config.password for config in registry.configs.values()}
    secrets = report.configured_secrets(env)
    assert passwords == {"d&fault", "a%2Fb", "r3ports"}
    assert passwords <= set(secrets)
    # Each raw password, its decoded and encoded forms, and their XML escapes; nothing else.
    assert set(secrets) == {
        "d&fault", "d&amp;fault", "d%26fault",
        "a%2Fb", "a/b", "a%252Fb",
        "r3ports",
    }  # fmt: skip
    assert secrets == sorted(secrets, key=len, reverse=True)


def test_configured_secrets_ignore_empty_passwords() -> None:
    assert report.configured_secrets({"CUBRID_PASSWORD": ""}) == []
    assert report.scrub(b"<x/>", []) == b"<x/>"


def test_masking_is_consistent_with_the_environment_command_redaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # environment.json already redacts credential assignments in the command; the verify
    # copy additionally masks the configured password wherever else it appears.
    monkeypatch.setenv("CUBRID_PASSWORD", "hunter2")
    lane = tmp_path / "integration"
    report.main(["environment", "--lane", "integration", "--results-dir", str(lane),
                 "--command", "pytest CUBRID_PASSWORD=hunter2 --note hunter2"])  # fmt: skip
    written = json.loads((lane / "environment.json").read_text())["command"]
    assert written == "pytest CUBRID_PASSWORD=*** --note hunter2"
    output = tmp_path / "verify" / "summary.json"
    report.main(["aggregate", "--output", str(output), "--phase", "integration=0",
                 "--environment", str(lane / "environment.json")])  # fmt: skip
    copied = json.loads((output.parent / "environment.json").read_text())["command"]
    assert copied == "pytest CUBRID_PASSWORD=*** --note ***"
