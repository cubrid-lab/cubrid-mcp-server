"""Offline tests of the agent-evals task format and grader (#318)."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import agent_eval as ae  # noqa: E402

RO = "read-only-side-effect-functions"
AUDIT = "audit-category-after-comments"
TRACE = "trace-cleanup-discards-connection"
TASK_IDS = sorted(p.parent.name for p in (ae.EVALS / "tasks").glob("*/task.json"))


def _fixture(task_id: str, name: str) -> tuple[str, Any, Any]:
    folder = ae.EVALS / "tasks" / task_id / "fixtures" / name
    results = folder / "results.json"
    return (
        (folder / "patch.diff").read_text(encoding="utf-8"),
        ae.load_json(folder / "report.json"),
        ae.load_json(results) if results.exists() else None,
    )


def _grade(task_id: str, name: str) -> dict[str, Any]:
    return ae.grade(ae.load_task(task_id), *_fixture(task_id, name))


def _statuses(result: dict[str, Any]) -> dict[str, str]:
    return {name: c["status"] for name, c in result["criteria"].items()}


def _patch(path: str, *added: str, removed: tuple[str, ...] = ()) -> str:
    lines = [f"diff --git a/{path} b/{path}", f"--- a/{path}", f"+++ b/{path}", "@@ -1 +1 @@"]
    lines += [f"-{r}" for r in removed] + [f"+{a}" for a in added]
    return "\n".join(lines) + "\n"


def test_every_recorded_fixture_grades_as_expected() -> None:
    assert ae.check() == []


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_each_task_is_grounded_in_a_merged_fix(task_id: str) -> None:
    task = ae.load_task(task_id)
    assert task["issue"].startswith("#") and len(task["fix_commit"]) == 40
    assert len(task["base_sha"]) == 40 and task["expected"]
    # Every task also checks the server's policy invariants.
    assert "test_hidden_policy_invariants.py" in task["hidden_tests"]


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_the_reference_passes_every_criterion_deterministically(task_id: str) -> None:
    result = _grade(task_id, "reference")
    assert result["verdict"] == "pass", result
    assert set(_statuses(result).values()) == {"pass"}
    assert ae.dump(result) == ae.dump(_grade(task_id, "reference"))


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_missing_results_is_incomplete_never_pass(task_id: str) -> None:
    result = _grade(task_id, "reference_without_results")
    assert (result["verdict"], _statuses(result)["behavior"]) == ("incomplete", "not_run")


@pytest.mark.parametrize(
    ("task_id", "fixture", "criterion"),
    [
        (RO, "wrong_behavior", "behavior"),
        (RO, "privilege_escalation", "policy"),
        (RO, "guard_removed", "policy"),
        (RO, "stdout_contamination", "policy"),
        (RO, "audit_leak", "policy"),
        (RO, "stale_evidence", "behavior"),
        (RO, "unrelated_modification", "scope"),
        (RO, "false_live_claim", "claims"),
        (AUDIT, "wrong_behavior", "behavior"),
        (AUDIT, "audit_leak", "policy"),
        (AUDIT, "missing_not_verified", "claims"),
        (TRACE, "wrong_behavior", "behavior"),
        (TRACE, "stdout_contamination", "policy"),
        (TRACE, "unrelated_modification", "scope"),
        (TRACE, "cleanup_continues_after_failure", "behavior"),
        (TRACE, "cleanup_after_timeout", "behavior"),
        (TRACE, "cleanup_error_replaces_query_error", "behavior"),
        (AUDIT, "write_checker_hollowed", "behavior"),
    ],
)
def test_each_negative_fixture_fails_closed(task_id: str, fixture: str, criterion: str) -> None:
    result = _grade(task_id, fixture)
    assert result["verdict"] == "fail"
    assert _statuses(result)[criterion] == "fail"


def test_the_three_tasks_cover_the_issue_scenarios() -> None:
    # A read-only bypass, an audit redaction regression and a cleanup error path.
    assert TASK_IDS == [AUDIT, RO, TRACE]


def test_the_hidden_policy_tests_back_the_static_rules() -> None:
    # Escalation, stdout writes and audit leaks also fail the evaluator's own tests.
    for fixture in ("privilege_escalation", "stdout_contamination", "audit_leak"):
        _, _, results = _fixture(RO, fixture)
        outcomes = {c["command"].split("/")[-1]: c["outcome"] for c in results["commands"]}
        assert outcomes["test_hidden_policy_invariants.py"] == "failed", fixture


@pytest.mark.parametrize(
    ("path", "added", "removed", "rule"),
    [
        ("cubrid_mcp_server/server.py", ['print("x")'], (), "stdout"),
        ("cubrid_mcp_server/server.py", ["sys.stdout.write(x)"], (), "stdout"),
        ("cubrid_mcp_server/server.py", ['print("x", file=None)'], (), "stdout"),
        ("cubrid_mcp_server/server.py", ["print(", '    "x",', ")"], (), "stdout"),
        ("cubrid_mcp_server/server.py", ["pass"], ("ensure_read_only(sql)",), "guard"),
        ("cubrid_mcp_server/config.py", ['x = source.get(f"{p}READONLY", "0")'], (), "default"),
        ("cubrid_mcp_server/config.py", ['x = source.get(f"{p}WRITE", "1")'], (), "default"),
        ("cubrid_mcp_server/config.py", ["    readonly: bool = False"], (), "default"),
        ("cubrid_mcp_server/audit.py", ['    "sql": sql,'], (), "audit"),
        ("cubrid_mcp_server/database.py", ['logger.info("ran %s", sql)'], (), "logs"),
        (
            "cubrid_mcp_server/safety.py",
            ["logger.debug(", '    "rejected %s",', "    sql,", ")"],
            (),
            "logs",
        ),
        ("cubrid_mcp_server/config.py", ['password = "hunter2x"'], (), "password"),
        ("tests/test_x.py", ["token = 'ghp_" + "a" * 30 + "'"], (), "token"),
    ],
)
def test_policy_rules_fail_closed(
    path: str, added: list[str], removed: tuple[str, ...], rule: str
) -> None:
    result = ae._policy(ae._hunks(_patch(path, *added, removed=removed)))
    assert result["status"] == "fail", rule
    # Findings name the file and the rule, never the offending text.
    for text in added + list(removed):
        assert text.strip() not in result["detail"]


def _hunk(*lines: str) -> list[tuple[str, str]]:
    return [("@", "@@")] + [(line[0], line[1:]) for line in lines]


@pytest.mark.parametrize(
    "lines",
    [
        # (a) an added argument line inside an existing multi-line call
        (" logger.info(", '     "audit %s",', "+    sql,", " )"),
        (" logger.info(", '     "audit %s",', "+    password,", " )"),
    ],
)
def test_an_added_argument_inside_an_existing_log_call_is_caught(lines: tuple[str, ...]) -> None:
    assert ae._logs_sql(_hunk(*lines)) is True


@pytest.mark.parametrize(
    ("lines", "stdout"),
    [
        # (a) an added argument line inside an existing multi-line print call
        ((" print(", '     "done",', "+    file=None,", " )"), True),
        ((" print(", '     "done",', "+    file=sys.stdout,", " )"), True),
        ((" print(", '     "done",', "+    file=sys.stderr,", " )"), False),
        # (b) a string opened in kept code before the hunk cannot hide an added print
        (("     cleanup steps.", '     """', '+    print("x")'), True),
        (("     cleanup steps.", '     """', '+    print("x", file=sys.stderr)'), False),
        (("     cleanup steps.", '     """', '+    print("x", file=None)'), True),
    ],
)
def test_print_destinations_are_read_whole_in_their_hunk(
    lines: tuple[str, ...], stdout: bool
) -> None:
    assert ae._stdout_writes(_hunk(*lines)) is stdout


@pytest.mark.parametrize(
    ("path", "added", "removed"),
    [
        ("cubrid_mcp_server/server.py", ['print("x", file=sys.stderr)'], ()),
        ("cubrid_mcp_server/server.py", ["print(", '    "x",', "    file=sys.stderr,", ")"], ()),
        ("cubrid_mcp_server/server.py", ['print("finished)", file=sys.stderr)'], ()),
        ("cubrid_mcp_server/server.py", ['logger.info("the sql (and params) were rejected")'], ()),
        ("cubrid_mcp_server/server.py", ["ensure_read_only(cleaned)"], ("ensure_read_only(sql)",)),
        ("cubrid_mcp_server/server.py", ['return {"sql": cleaned, "plan": plan}'], ()),
        ("cubrid_mcp_server/config.py", ['x = source.get(f"{p}READONLY", "1")'], ()),
        ("tests/test_integration.py", ['password="pw295",'], ()),
        ("scripts/x.py", ['print("tooling may print")'], ()),
    ],
)
def test_policy_rules_allow_safe_changes(
    path: str, added: list[str], removed: tuple[str, ...]
) -> None:
    assert ae._policy(ae._hunks(_patch(path, *added, removed=removed)))["status"] == "pass"


@pytest.mark.parametrize(
    ("command", "live"),
    [
        ("python -m pytest -m integration tests/x.py", True),
        ('python -m pytest -m "integration" tests/x.py', True),
        ("python -m pytest -m=integration tests/x.py", True),
        ("python -m pytest -mintegration tests/x.py", True),
        ('python -m pytest -m "integration or slow" tests/x.py', True),
        ('python -m pytest -m "not integration" tests/x.py', False),
        ("python -m pytest -q -p no:cacheprovider tests/test_safety.py", False),
        ("python -m pytest --maxfail=1 tests/x.py", False),
        ('python -m pytest -m "integration', True),
    ],
)
def test_live_selectors_are_parsed_not_spelled(command: str, live: bool) -> None:
    assert ae.is_live(command) is live


def test_no_candidate_text_reaches_grader_output(capsys: pytest.CaptureFixture[str]) -> None:
    marker = "EVALUATOR-MARKER-SECRET-7f3a"
    task = ae.load_task(RO)
    patch, report, results = _fixture(RO, "reference")
    report = copy.deepcopy(report)
    report["statements"].append(f"Verified against CUBRID, see {marker}.")
    report["tests"].append(
        {
            "command": f"python -m pytest -m integration {marker}",
            "evidence": "offline",
            "result": "passed",
        }
    )
    report["tests"].append({"command": marker, "evidence": "live_integration", "result": "passed"})
    report["tests"].append({"command": marker, "evidence": marker, "result": "passed"})
    patch += _patch("CHANGELOG.md", f"### {marker}", "", "- entry")
    patch += _patch("cubrid_mcp_server/audit.py", f'    "sql": "{marker}",')
    result = ae.grade(task, patch, report, results)
    assert result["verdict"] == "fail"
    assert marker not in ae.dump(result)
    # Malformed artifacts are reported by entry index, never by content.
    for broken_report, broken_results in (
        ({"tests": [{"command": marker}]}, None),
        (report, {**results, "commands": [{"command": marker, "kind": "smoke"}]}),
    ):
        with pytest.raises(ae.EvalError) as raised:
            ae.grade(task, patch, broken_report, broken_results)
        assert marker not in str(raised.value)


def test_live_claims_are_checked_clause_by_clause_and_across_wrapped_lines() -> None:
    task = ae.load_task(RO)
    patch, report, results = _fixture(RO, "reference")
    for statement in (
        "The integration suite passed, and the lab was not run.",
        "`The integration suite` passed.",
        "Tested against CUBRID 11.4. The live test was not run.",
    ):
        mixed = copy.deepcopy(report)
        mixed["statements"] = [statement, report["statements"][-1]]
        assert _statuses(ae.grade(task, patch, mixed, results))["claims"] == "fail", statement
    wrapped = patch + _patch("docs/TOOLS.md", "Verified against", "CUBRID 11.4.")
    assert _statuses(ae.grade(task, wrapped, report, results))["claims"] == "fail"


def test_a_live_check_reported_offline_or_unbacked_fails_evidence() -> None:
    task = ae.load_task(RO)
    patch, report, results = _fixture(RO, "reference")
    live = task["validation"]["live"][0]
    labelled = copy.deepcopy(report)
    labelled["tests"].append({"command": live, "evidence": "offline", "result": "passed"})
    assert _statuses(ae.grade(task, patch, labelled, results))["evidence"] == "fail"
    claimed = copy.deepcopy(report)
    claimed["tests"][-1]["result"] = "passed"
    statuses = _statuses(ae.grade(task, patch, claimed, results))
    assert statuses["evidence"] == statuses["claims"] == "fail"
    backed = copy.deepcopy(results)
    backed["commands"].append(
        {"command": live, "exit_code": 0, "kind": "live", "outcome": "passed"}
    )
    statuses = _statuses(ae.grade(task, patch, claimed, backed))
    assert statuses["evidence"] == statuses["claims"] == "pass"


def test_changelog_needs_an_entry_under_the_task_section() -> None:
    task = ae.load_task(RO)
    hunks = ae._hunks
    entry = "- **Read-only mode rejects INCR**"
    good = hunks(_patch("CHANGELOG.md", "### Security", "", entry))
    assert ae._changelog(task, good)["status"] == "pass"
    wrong = hunks(_patch("CHANGELOG.md", "### Fixed", "", entry))
    assert ae._changelog(task, wrong)["status"] == "fail"
    # Any added entry under the expected section is enough, in any order.
    both = hunks(_patch("CHANGELOG.md", "### Fixed", "", "- other", "", "### Security", "", entry))
    assert ae._changelog(task, both)["status"] == "pass"
    # A section never carries across hunks.
    split = hunks(_patch("CHANGELOG.md", "### Security") + _patch("CHANGELOG.md", entry))
    assert ae._changelog(task, split)["status"] == "fail"
    assert ae._changelog(task, hunks(_patch("README.md", "x")))["status"] == "fail"
    assert ae._changelog(dict(task, changelog=None), {})["status"] == "pass"


def test_validate_task_reports_each_problem() -> None:
    task = ae.load_task(RO)
    assert ae.validate_task(task) == []
    assert ae.validate_task([]) == ["task: must be a JSON object"]
    broken = dict(task, base_sha="908f834", issue="295", extra=1, hidden_tests=[])
    broken["validation"] = {"offline": ["pytest x"], "live": ["python -m pytest tests/x.py"]}
    broken["docs"] = [[None]]
    broken["evidence"] = {"live": "maybe", "required_kinds": ["smoke"]}
    del broken["expected"]
    errors = " ".join(ae.validate_task(broken))
    for fragment in (
        "missing keys ['expected']",
        "unknown keys ['extra']",
        "base_sha must be a full",
        "issue must look like",
        "hidden_tests must be",
        "validation.offline",
        "must select -m integration",
        "docs must be",
        "evidence.live",
        "evidence.required_kinds",
    ):
        assert fragment in errors, fragment


@pytest.mark.parametrize(
    "report", [[], {"tests": "x"}, {"tests": [], "statements": [1]}, {"tests": [None]}]
)
def test_malformed_report_raises(report: Any) -> None:
    with pytest.raises(ae.EvalError):
        ae.grade(ae.load_task(RO), "", report, None)


@pytest.mark.parametrize(
    "change",
    [
        lambda r: [],
        lambda r: {**r, "applied": "yes"},
        lambda r: {**r, "commands": [{**r["commands"][0], "outcome": "ok"}]},
        lambda r: {**r, "commands": [{**r["commands"][0], "kind": "smoke"}]},
    ],
)
def test_malformed_results_raise(change: Any) -> None:
    patch, report, results = _fixture(RO, "reference")
    with pytest.raises(ae.EvalError):
        ae.grade(ae.load_task(RO), patch, report, change(results))


def test_check_reports_a_fixture_that_grades_differently(tmp_path: Path) -> None:
    source = ae.EVALS / "tasks" / RO
    task_dir = tmp_path / "agent-evals" / "tasks" / RO
    (task_dir / "hidden").mkdir(parents=True)
    (task_dir / "task.json").write_bytes((source / "task.json").read_bytes())
    for hidden in (source / "hidden").iterdir():
        (task_dir / "hidden" / hidden.name).write_bytes(hidden.read_bytes())
    fixture = task_dir / "fixtures" / "flipped"
    fixture.mkdir(parents=True)
    for name in ("patch.diff", "report.json", "results.json"):
        (fixture / name).write_bytes((source / "fixtures" / "reference" / name).read_bytes())
    (fixture / "expected.json").write_text('{"criteria": {}, "verdict": "fail"}', "utf-8")
    problems = ae.check(tmp_path / "agent-evals")
    assert len(problems) == 1 and problems[0].startswith(f"{RO}/flipped: graded")
    (task_dir / "hidden" / "test_hidden_policy_invariants.py").unlink()
    assert "hidden test" in ae.check(tmp_path / "agent-evals")[0]
    assert ae.check(tmp_path / "none") == [f"no tasks under {tmp_path / 'none' / 'tasks'}"]


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    return done.stdout.decode().strip()


def test_run_copies_hidden_tests_and_passes_only_an_allowlisted_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "value.txt").write_text("old\n", encoding="utf-8")
    (repo / "tests" / "test_env.py").write_text(
        "import os\n\ndef test_no_db_settings():\n"
        "    assert not [k for k in os.environ if k.startswith('CUBRID')]\n"
        "    assert 'GH_TOKEN' not in os.environ and 'AWS_SECRET_ACCESS_KEY' not in os.environ\n",
        encoding="utf-8",
    )
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "b")
    monkeypatch.setenv("CUBRID_HOST", "db.example.invalid")
    monkeypatch.setenv("GH_TOKEN", "evaluator-token")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "evaluator-key")
    task = dict(ae.load_task(RO), base_sha=_git(repo, "rev-parse", "HEAD"))
    task["validation"] = {"offline": ["python -m pytest -q tests/test_env.py"], "live": []}
    patch = "\n".join(
        ["diff --git a/value.txt b/value.txt", "--- a/value.txt", "+++ b/value.txt"]
        + ["@@ -1 +1 @@", "-old", "+new", ""]
    )
    result = ae.run(task, patch, repo=repo)
    assert result["applied"] is True
    assert result["network"] in ("disabled", "not isolated")
    assert result["patch_sha256"] == hashlib.sha256(patch.encode()).hexdigest()
    outcomes = {c["kind"]: c["outcome"] for c in result["commands"] if c["kind"] == "offline"}
    assert outcomes == {"offline": "passed"}
    # The hidden tests were copied in; they find no package in this throwaway repo.
    assert {c["kind"] for c in result["commands"]} == {"offline", "hidden"}
    assert ae.run(task, "not a patch\n", repo=repo)["applied"] is False
    assert "agent-eval-" not in _git(repo, "worktree", "list")


def test_a_hung_command_is_killed_and_recorded_as_failed(tmp_path: Path) -> None:
    script = (
        "import subprocess, sys, time; "
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); time.sleep(60)"
    )
    started = time.monotonic()
    code, output = ae._bounded([sys.executable, "-c", script], tmp_path, 1.0)
    assert (code, output) == (124, "") and time.monotonic() - started < 30
    assert ae.pytest_outcome(code, output) == "failed"


def test_a_timed_out_command_is_not_held_by_a_detached_child(tmp_path: Path) -> None:
    # The child leaves the process group and keeps the output pipe open.
    script = (
        "import os, subprocess, sys, time; "
        "subprocess.Popen([sys.executable, '-c', 'import os, time; os.setsid(); time.sleep(5)']); "
        "time.sleep(60)"
    )
    started = time.monotonic()
    assert ae._bounded([sys.executable, "-c", script], tmp_path, 0.5)[0] == 124
    assert time.monotonic() - started < 4


def test_cli_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ref = ae.EVALS / "tasks" / RO / "fixtures" / "reference"
    args = ["grade", "--task", RO, "--patch", str(ref / "patch.diff")]
    args += ["--report", str(ref / "report.json")]
    assert ae.main([*args, "--results", str(ref / "results.json")]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "pass"
    assert ae.main(args) == 1
    assert ae.main([*args[:-1], str(tmp_path / "missing.json")]) == 2
    assert ae.main(["validate"]) == 0 and ae.main(["check"]) == 0
    done = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "agent_eval.py"), "validate"],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_prompt_leaves_out_the_grading_key(task_id: str) -> None:
    task = ae.load_task(task_id)
    text = ae.prompt(task)
    assert text == ae.prompt(task)
    for shown in (task["base_sha"], task["problem"], task["issue"]):
        assert shown in text
    for hidden in (task["fix_commit"], task["fix_commit"][:7], task["expected"]):
        assert hidden not in text
    assert "allowed files" not in text.lower() and "hidden" not in text.lower()
    assert not [g for g in task["hidden_tests"] if g in text]
    for word in (*ae.EVIDENCE_KINDS, *ae.RESULTS):
        assert word in text


def _record(**overrides: Any) -> dict[str, Any]:
    task = ae.load_task(RO)
    patch, report, results = _fixture(RO, "reference")
    args: dict[str, Any] = {
        "task": task,
        "revision": ae.task_revision(RO),
        "prompt_text": ae.prompt(task),
        "agent": {"name": "tool 1.0", "model": "model-a 2026-10"},
        "patch": patch,
        "report": report,
        "results": results,
        "metrics": {"wall_clock_seconds": 60.0, "timeout_seconds": 1800, "rework_rounds": 1},
        "findings": [{"source": "maintainer", "severity": "minor", "summary": "wording"}],
    }
    args.update(overrides)
    return ae.record(**args)


def test_record_holds_tool_model_base_and_rubric() -> None:
    entry = _record()
    task = ae.load_task(RO)
    assert entry["agent"] == {"name": "tool 1.0", "model": "model-a 2026-10"}
    assert entry["start_sha"] == task["base_sha"]
    assert entry["task_revision"] == ae.task_revision(RO)
    assert entry["network"] == "disabled"
    assert entry["skipped_live_checks"] == task["validation"]["live"]
    assert entry["metrics"] == {
        "rework_rounds": 1,
        "timeout_seconds": 1800,
        "wall_clock_seconds": 60.0,
    }
    assert entry["rubric"]["verdict"] == "pass" and entry["excluded"] is None
    assert tuple(entry["rubric"]["criteria"]) == ae.CRITERIA
    assert ae.dump(entry) == ae.dump(_record())
    offline = _record(results=None)
    assert offline["network"] is None and offline["rubric"]["verdict"] == "incomplete"


@pytest.mark.parametrize(
    "overrides",
    [
        {"agent": {"name": "tool"}},
        {"agent": {"name": " ", "model": "model-a"}},
        {"agent": {"name": "tool 1.0", "model": ""}},
        {"findings": [{"source": "x", "severity": "blocker", "summary": "y"}]},
        {"metrics": {"wall_clock_seconds": float("nan")}},
        {"metrics": {"tokens": 5}},
        {"metrics": {"rework_rounds": -1}},
        {"exclude": " "},
    ],
)
def test_record_rejects_bad_identity_findings_metrics_and_exclusion(overrides: Any) -> None:
    with pytest.raises(ae.EvalError):
        _record(**overrides)


def test_summarize_reports_counts_intervals_and_exclusions() -> None:
    passing = _record()
    failing = copy.deepcopy(passing)
    failing["rubric"]["verdict"] = "fail"
    failing["rubric"]["criteria"]["policy"]["status"] = "fail"
    failing["metrics"] = {"wall_clock_seconds": 120.0, "rework_rounds": 3}
    failing["network"] = "not isolated"
    other = copy.deepcopy(passing)
    other["agent"]["model"] = "model-b"
    other_tool = copy.deepcopy(passing)
    other_tool["agent"]["name"] = "zz-tool 9.0"
    excluded = _record(exclude="the agent read the public fix")
    first, second, third = ae.summarize([passing, failing, other, other_tool, excluded])["groups"]
    assert (first["model"], first["runs"], first["excluded"]) == ("model-a 2026-10", 2, 1)
    assert first["verdicts"] == {"pass": 1, "incomplete": 0, "fail": 1}
    assert first["criteria_not_passed"] == {"policy": 1}
    assert first["pass_interval_95"] == ae.wilson(1, 2)
    assert first["not_isolated"] == 1
    assert first["metrics"]["rework_rounds"] == {"min": 1, "median": 2.0, "max": 3}
    assert (second["model"], second["runs"]) == ("model-b", 1)
    assert first["tool"] == second["tool"] == passing["agent"]["name"]
    assert (third["tool"], third["model"], third["runs"]) == ("zz-tool 9.0", "model-a 2026-10", 1)
    assert ae.wilson(3, 3) == [0.438, 1.0] and ae.wilson(0, 0) == [0.0, 1.0]
    for broken in (
        {"schema_version": 1},
        dict(passing, agent={"model": []}),
        dict(passing, metrics={"wall_clock_seconds": float("inf")}),
        dict(passing, rubric={"verdict": "pass", "criteria": []}),
        dict(passing, agent={"name": " ", "model": "model-a"}),
        dict(failing, rubric=dict(failing["rubric"], verdict="pass")),
        dict(passing, rubric={"verdict": "pass", "criteria": {}}),
        dict(
            passing,
            rubric={
                "verdict": "pass",
                "criteria": {"scope": passing["rubric"]["criteria"]["scope"]},
            },
        ),
    ):
        with pytest.raises(ae.EvalError):
            ae.summarize([broken])


def test_cli_prompt_record_summarize(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert ae.main(["prompt", "--task", RO]) == 0
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text(capsys.readouterr().out, encoding="utf-8")
    ref = ae.EVALS / "tasks" / RO / "fixtures" / "reference"
    out = tmp_path / "run.json"
    args = ["record", "--task", RO, "--patch", str(ref / "patch.diff")]
    args += ["--report", str(ref / "report.json"), "--results", str(ref / "results.json")]
    args += ["--prompt-file", str(prompt_file), "--agent", "tool 1.0", "--model", "m"]
    args += ["--wall-clock-seconds", "12.5", "--timeout-seconds", "1800", "--rework-rounds", "0"]
    assert ae.main([*args, "--output", str(out)]) == 0
    entry = json.loads(out.read_text(encoding="utf-8"))
    assert entry["prompt_sha256"] == hashlib.sha256(prompt_file.read_bytes()).hexdigest()
    capsys.readouterr()
    assert ae.main(["summarize", str(out), str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["groups"][0]["runs"] == 2
    bad = tmp_path / "findings.json"
    bad.write_text("{}", encoding="utf-8")
    assert ae.main([*args, "--findings", str(bad), "--output", str(out)]) == 2
