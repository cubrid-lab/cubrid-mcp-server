"""Offline policy tests for tiered CI validation (#223).

Covers scripts/ci_scope.py (path/event classification) and static contracts of
ci.yml and integration-full.yml: the required `ci-gate` stays fail-closed, docs-only
PRs start no CUBRID container, and the release still runs the full matrix.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SCRIPT = ROOT / "scripts" / "ci_scope.py"

_spec = importlib.util.spec_from_file_location("_ci_scope", SCRIPT)
assert _spec is not None and _spec.loader is not None
ci_scope = importlib.util.module_from_spec(_spec)
sys.modules["_ci_scope"] = ci_scope
_spec.loader.exec_module(ci_scope)


def load(name: str) -> dict[str, Any]:
    data = yaml.safe_load((WORKFLOWS / name).read_text())
    data["on"] = data.pop(True, data.get("on"))
    return dict(data)


CI = load("ci.yml")
FULL = load("integration-full.yml")
# The supported Python x CUBRID cells a release and the weekly run must test (#417).
FULL_CELLS = {
    (py, db) for py in ("3.11", "3.12", "3.13", "3.14") for db in ("10.2", "11.0", "11.2", "11.4")
}


def pr(*paths: str) -> dict[str, object]:
    return dict(ci_scope.classify("pull_request", paths))


# --- classification -------------------------------------------------------------


@pytest.mark.parametrize(
    "paths",
    [
        ["README.md"],
        ["docs/TOOLS.md", "docs/ko/quickstart.md", "CHANGELOG.md"],
        ["AGENTS.md", "LICENSE", "NOTICE", "llms.txt"],
        [".github/PULL_REQUEST_TEMPLATE.md", "docs/demo.gif"],
    ],
)
def test_docs_only_pr_runs_no_unit_and_no_cubrid(paths: list[str]) -> None:
    scope = pr(*paths)
    assert scope["tier"] == "docs"
    assert scope["unit"] is False


@pytest.mark.parametrize(
    "path", ["docs/overrides/main.html", "docs/overrides/partials/channel.html", "mkdocs.yml"]
)
def test_site_notice_template_selects_the_unit_lane_only(path: str) -> None:
    # tests/test_docs_channel_notice.py renders the template and checks its
    # mkdocs.yml wiring, so these paths run the unit lane but start no CUBRID.
    scope = pr(path)
    assert scope["tier"] == "pr"
    assert scope["unit"] is True
    assert scope["live"] is False
    assert scope["lowest"] is False
    assert scope["live"] is False
    assert scope["lowest"] is False


@pytest.mark.parametrize(
    "path",
    ["cubrid_mcp_server/server.py", "cubrid_mcp_server/safety.py", "tests/test_audit.py"],
)
def test_ordinary_runtime_pr_gets_one_python_and_one_cubrid(path: str) -> None:
    scope = pr(path, "CHANGELOG.md")
    assert scope["tier"] == "pr"
    assert scope["unit"] is True
    assert scope["python"] == ["3.12"]
    assert scope["live"] is True
    assert scope["cubrid"] == ["11.4"]
    assert scope["lowest"] is False


@pytest.mark.parametrize(
    "path",
    [
        "cubrid_mcp_server/database.py",
        "cubrid_mcp_server/context.py",
        "tests/conftest.py",
        "tests/test_integration.py",
    ],
)
def test_connection_and_catalog_changes_hit_both_cubrid_endpoints(path: str) -> None:
    scope = pr(path)
    assert scope["cubrid"] == ["11.2", "11.4"]
    assert scope["python"] == ["3.12"]
    assert scope["lowest"] is False


def test_dependency_metadata_runs_lowest_direct_and_endpoints() -> None:
    scope = pr("pyproject.toml")
    assert scope["lowest"] is True
    assert scope["python"] == ["3.11", "3.12", "3.14"]
    assert scope["cubrid"] == ["11.2", "11.4"]


@pytest.mark.parametrize("path", sorted(p.name for p in WORKFLOWS.glob("*.yml")))
def test_workflow_edits_select_live_lanes_only_for_ci_yml(path: str) -> None:
    scope = pr(f".github/workflows/{path}")
    if path == "ci.yml":
        assert scope["tier"] == "full"
        assert scope["live"] is True
    else:
        # ci.yml's live job never executes another workflow (#232).
        assert scope["tier"] == "pr"
        assert scope["unit"] is True
        assert scope["live"] is False
        assert scope["lowest"] is False
        assert scope["python"] == ["3.12"]
        assert scope["cubrid"] == ["11.4"]


def test_codeql_only_edit_starts_no_live_lane() -> None:
    scope = pr(".github/workflows/codeql.yml")
    assert scope["unit"] is True
    assert scope["live"] is False


def test_ci_yml_edit_keeps_its_current_lanes() -> None:
    scope = pr(".github/workflows/ci.yml")
    assert scope["tier"] == "full"
    assert scope["unit"] is True and scope["lowest"] is True and scope["live"] is True
    assert scope["python"] == ["3.11", "3.12", "3.14"]
    assert scope["cubrid"] == ["11.2", "11.4"]


def test_release_please_edit_selects_the_unit_lane() -> None:
    scope = pr(".github/workflows/release-please.yml")
    assert scope["unit"] is True
    assert scope["live"] is False


def test_workflow_edit_with_dependency_metadata_keeps_lowest_direct() -> None:
    scope = pr(".github/workflows/codeql.yml", "pyproject.toml")
    assert scope["lowest"] is True


@pytest.mark.parametrize(
    "path",
    [
        "scripts/lint_changelog.py",
        "scripts/doctor.py",
        ".mcpb/server.json",
        ".github/dependabot.yml",
        "docs-tools/requirements.txt",
        "THIRD_PARTY_LICENSES.md",
        # The agent evaluations, Markdown included, are graded in the unit lane (#318).
        "agent-evals/README.md",
        "agent-evals/tasks/read-only-side-effect-functions/task.json",
        "agent-evals/tasks/read-only-side-effect-functions/fixtures/reference/patch.diff",
        "agent-evals/tasks/read-only-side-effect-functions/hidden/test_hidden_policy_invariants.py",
    ],
)
def test_tooling_and_metadata_run_unit_but_never_cubrid(path: str) -> None:
    scope = pr(path)
    assert scope["unit"] is True
    assert scope["live"] is False
    assert scope["python"] == ["3.12"]


@pytest.mark.parametrize("path", ["Makefile", "scripts/run_integration.py"])
def test_live_lane_implementation_selects_the_default_live_lane(path: str) -> None:
    # The live job runs `make integration`; editing it must run it (#381).
    scope = pr(path)
    assert scope["tier"] == "pr"
    assert scope["unit"] is True
    assert scope["live"] is True
    assert scope["cubrid"] == ["11.4"]
    assert scope["lowest"] is False


@pytest.mark.parametrize(
    "path", [".github/workflows/ci.yml", "scripts/ci_scope.py", "tests/test_ci_scope.py"]
)
def test_ci_policy_changes_self_test_at_the_full_tier(path: str) -> None:
    assert pr(path)["tier"] == "full"


@pytest.mark.parametrize("event", ["push", "workflow_dispatch", "merge_group", ""])
def test_non_pr_and_unknown_events_run_the_full_tier(event: str) -> None:
    scope = dict(ci_scope.classify(event, []))
    assert scope["tier"] == "full"
    assert scope["unit"] is True
    assert scope["lowest"] is True
    assert scope["live"] is True
    assert scope["python"] == ["3.11", "3.12", "3.14"]
    # #417: only a push to main narrows live CUBRID to the representative 11.4;
    # dispatch and unknown events keep both endpoints (fail closed).
    assert scope["cubrid"] == (["11.4"] if event == "push" else ["11.2", "11.4"])


def _classify_step(event: str, tmp_path: Path) -> dict[str, str]:
    """Run ci.yml's real classify step script for a non-PR event."""
    step = CI["jobs"]["classify"]["steps"][1]
    assert step["env"] == {"EVENT": "${{ github.event_name }}"}
    output = tmp_path / "output"
    env = {
        **os.environ,
        # The step's python3 is the test interpreter, as setup-python would provide.
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
        "EVENT": event,
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_OUTPUT": str(output),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
    }
    subprocess.run(["bash", "-c", step["run"]], cwd=ROOT, env=env, check=True)
    return dict(line.split("=", 1) for line in output.read_text().splitlines())


# What ci.yml starts per event (#417): unit Python lanes, lowest-direct, live CUBRID.
EVENT_LANES = {
    # Ordinary push to main: the Python endpoints and lowest-direct stay; live
    # CUBRID is the representative 11.4 only.
    "push": (["3.11", "3.12", "3.14"], "true", ["11.4"]),
    # Not ci.yml triggers today; they and any unknown event fail closed to both.
    "workflow_dispatch": (["3.11", "3.12", "3.14"], "true", ["11.2", "11.4"]),
    "schedule": (["3.11", "3.12", "3.14"], "true", ["11.2", "11.4"]),
    "merge_group": (["3.11", "3.12", "3.14"], "true", ["11.2", "11.4"]),
}


@pytest.mark.parametrize("event", sorted(EVENT_LANES))
def test_ci_yml_selects_the_documented_lanes_per_event(event: str, tmp_path: Path) -> None:
    out = _classify_step(event, tmp_path)
    jobs = CI["jobs"]
    # The matrices consume the classify outputs verbatim.
    assert jobs["lint-and-test"]["strategy"]["matrix"]["python-version"] == (
        "${{ fromJSON(needs.classify.outputs.python) }}"
    )
    assert jobs["integration"]["strategy"]["matrix"]["cubrid"] == (
        "${{ fromJSON(needs.classify.outputs.cubrid) }}"
    )
    python, lowest, cubrid = EVENT_LANES[event]
    assert out["unit"] == "true" and out["live"] == "true"
    assert json.loads(out["python"]) == python
    assert out["lowest"] == lowest
    assert json.loads(out["cubrid"]) == cubrid


def test_version_sensitive_prs_still_select_both_cubrid_endpoints() -> None:
    # #417 changes only the push event; PR classification is untouched.
    for paths in (
        *([path] for path in ci_scope.LIVE_ENDPOINTS),
        ["pyproject.toml"],
        [".github/workflows/ci.yml"],
        ["scripts/ci_scope.py"],
    ):
        assert pr(*paths)["cubrid"] == ["11.2", "11.4"], paths
    assert pr("cubrid_mcp_server/server.py")["cubrid"] == ["11.4"]
    assert pr("docs/TOOLS.md")["live"] is False


def test_fail_closed_on_unknown_paths_and_empty_diff() -> None:
    unknown = pr("some/new/thing.toml")
    assert unknown["unit"] is True and unknown["live"] is True
    assert pr()["tier"] == "full"
    assert pr("", "  ")["tier"] == "full"


def test_a_file_moved_out_of_the_runtime_tree_still_counts() -> None:
    # The workflow lists both sides of a rename (--no-renames).
    scope = pr("cubrid_mcp_server/old.py", "docs/old.md")
    assert scope["live"] is True


def test_cli_renders_github_output() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--event", "pull_request"],
        input="README.md\n",
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == [
        "tier=docs",
        "unit=false",
        'python=["3.12"]',
        "lowest=false",
        "live=false",
        'cubrid=["11.4"]',
    ]


# --- ci.yml contracts -----------------------------------------------------------


def test_required_check_names_are_stable() -> None:
    assert "ci-gate" in CI["jobs"]
    assert "name" not in CI["jobs"]["ci-gate"]


def test_gate_needs_every_job_and_always_runs() -> None:
    gate = CI["jobs"]["ci-gate"]
    others = set(CI["jobs"]) - {"ci-gate"}
    assert set(gate["needs"]) == others
    assert gate["if"] == "always()"


def test_every_lane_is_selected_by_classify() -> None:
    expected = {
        "lint-and-test": "needs.classify.outputs.unit == 'true'",
        "lowest-direct": "needs.classify.outputs.lowest == 'true'",
        "integration": "needs.classify.outputs.live == 'true'",
    }
    for job, condition in expected.items():
        assert CI["jobs"][job]["needs"] == ["classify"], job
        assert CI["jobs"][job]["if"] == condition, job
    strategy = CI["jobs"]["lint-and-test"]["strategy"]["matrix"]
    assert strategy["python-version"] == "${{ fromJSON(needs.classify.outputs.python) }}"
    assert (
        CI["jobs"]["integration"]["strategy"]["matrix"]["cubrid"]
        == "${{ fromJSON(needs.classify.outputs.cubrid) }}"
    )


def _gate_env_and_script() -> tuple[dict[str, str], str]:
    (step,) = CI["jobs"]["ci-gate"]["steps"]
    return dict(step["env"]), str(step["run"])


def test_gate_checks_every_lane_against_its_classification() -> None:
    env, run = _gate_env_and_script()
    assert env["CLASSIFY_RESULT"] == "${{ needs.classify.result }}"
    assert env["CHANGELOG_RESULT"] == "${{ needs.changelog-lint.result }}"
    for job, key, wanted in [
        ("lint-and-test", "UNIT", "unit"),
        ("lowest-direct", "LOWEST", "lowest"),
        ("integration", "LIVE", "live"),
    ]:
        assert env[f"{key}_RESULT"] == f"${{{{ needs.{job}.result }}}}"
        assert env[f"{key}_WANTED"] == f"${{{{ needs.classify.outputs.{wanted} }}}}"
        assert f'check {job} "${key}_RESULT" "${key}_WANTED"' in run
    assert 'check classify "$CLASSIFY_RESULT" required' in run
    assert 'check changelog-lint "$CHANGELOG_RESULT" required' in run
    assert "${{" not in run


def _run_gate(**results: str) -> int:
    env, run = _gate_env_and_script()
    values = {
        "TIER": "pr",
        "CLASSIFY_RESULT": "success",
        "UNIT_RESULT": "success",
        "UNIT_WANTED": "true",
        "LOWEST_RESULT": "skipped",
        "LOWEST_WANTED": "false",
        "LIVE_RESULT": "success",
        "LIVE_WANTED": "true",
        "CHANGELOG_RESULT": "success",
    }
    assert set(values) == set(env)
    values.update(results)
    proc = subprocess.run(
        ["bash", "-c", run], env={**os.environ, **values}, capture_output=True, text=True
    )
    return proc.returncode


def test_gate_passes_when_selected_lanes_succeed_and_others_are_skipped() -> None:
    assert _run_gate() == 0
    docs_only = {
        "TIER": "docs",
        "UNIT_RESULT": "skipped",
        "UNIT_WANTED": "false",
        "LIVE_RESULT": "skipped",
        "LIVE_WANTED": "false",
    }
    assert _run_gate(**docs_only) == 0


@pytest.mark.parametrize(
    "results",
    [
        {"UNIT_RESULT": "failure"},
        {"UNIT_RESULT": "cancelled"},
        {"LIVE_RESULT": "failure"},
        {"LIVE_RESULT": "cancelled"},
        {"LOWEST_RESULT": "failure", "LOWEST_WANTED": "true"},
        {"CHANGELOG_RESULT": "failure"},
        {"CHANGELOG_RESULT": "skipped"},
        # A selected lane that silently did not run.
        {"UNIT_RESULT": "skipped"},
        {"LIVE_RESULT": "skipped"},
        {"LOWEST_RESULT": "skipped", "LOWEST_WANTED": "true"},
        # Classification failed or was cancelled: outputs are empty.
        {
            "CLASSIFY_RESULT": "failure",
            "UNIT_RESULT": "skipped",
            "UNIT_WANTED": "",
            "LOWEST_WANTED": "",
            "LIVE_RESULT": "skipped",
            "LIVE_WANTED": "",
        },
        {"CLASSIFY_RESULT": "cancelled"},
        {"CLASSIFY_RESULT": "skipped"},
    ],
)
def test_gate_fails_closed(results: dict[str, str]) -> None:
    assert _run_gate(**results) != 0


# --- integration-full.yml contracts ----------------------------------------------


def test_only_the_weekly_full_matrix_is_scheduled() -> None:
    # #417: the Monday-Saturday corners cron is gone; one weekly full run remains.
    crons = [entry["cron"] for entry in FULL["on"]["schedule"]]
    assert crons == ["0 3 * * 0"]
    (plan_step,) = FULL["jobs"]["plan"]["steps"]
    # The plan no longer looks at the cron string, so no schedule can narrow it.
    assert "CRON" not in plan_step["env"]
    assert "CRON" not in plan_step["run"]


def _plan(**env: str) -> dict[str, str]:
    (plan_step,) = FULL["jobs"]["plan"]["steps"]
    values = {"RELEASE_SHA": "", "EVENT": "", "DISPATCH_SCOPE": ""}
    assert set(values) == set(plan_step["env"])
    values.update(env)
    out = subprocess.run(
        ["bash", "-c", plan_step["run"]],
        env={**os.environ, **values, "GITHUB_OUTPUT": "/dev/stdout"},
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


@pytest.mark.parametrize(
    "env",
    [
        {"RELEASE_SHA": "a" * 40, "EVENT": "push"},
        # A release must stay full even if a scope/cron would select corners.
        {"RELEASE_SHA": "a" * 40, "EVENT": "schedule", "CRON": "0 3 * * 1-6"},
        {"RELEASE_SHA": "a" * 40, "EVENT": "workflow_dispatch", "DISPATCH_SCOPE": "corners"},
        # A release call from the recovery dispatch of publish-pypi.yml.
        {"RELEASE_SHA": "a" * 40, "EVENT": "workflow_dispatch"},
        {"EVENT": "schedule", "CRON": "0 3 * * 0"},
        # #417: the removed weekday cron string no longer selects corners.
        {"EVENT": "schedule", "CRON": "0 3 * * 1-6"},
        {"EVENT": "workflow_dispatch"},
        {"EVENT": "workflow_dispatch", "DISPATCH_SCOPE": "full"},
    ],
)
def test_release_weekly_and_default_dispatch_run_the_full_matrix(env: dict[str, str]) -> None:
    out = _plan(**env)
    assert out["scope"] == "full"
    assert out["matrix"] == (
        '{"python-version":["3.11","3.12","3.13","3.14"],"cubrid":["10.2","11.0","11.2","11.4"]}'
    )
    matrix = json.loads(out["matrix"])
    cells = {(py, db) for py in matrix["python-version"] for db in matrix["cubrid"]}
    assert cells == FULL_CELLS


@pytest.mark.parametrize(
    "env",
    [
        {"EVENT": "workflow_dispatch", "DISPATCH_SCOPE": "corners"},
    ],
)
def test_corners_cover_oldest_and_newest(env: dict[str, str]) -> None:
    out = _plan(**env)
    assert out["scope"] == "corners"
    assert out["matrix"] == (
        '{"include":[{"python-version":"3.11","cubrid":"10.2"},'
        '{"python-version":"3.14","cubrid":"11.4"}]}'
    )


def test_full_matrix_result_fails_closed() -> None:
    result = FULL["jobs"]["full-matrix-result"]
    assert result["if"] == "always()"
    assert set(result["needs"]) == {"plan", "integration-full"}
    run = result["steps"][0]["run"]
    assert '[ "$PLAN_RESULT" != "success" ]' in run
    assert '[ -n "$RELEASE_SHA" ] && [ "$SCOPE" != "full" ]' in run
    assert '[ "$MATRIX_RESULT" != "success" ]' in run
    assert FULL["jobs"]["integration-full"]["needs"] == ["plan"]


def test_release_still_gates_on_the_full_matrix() -> None:
    release = load("publish-pypi.yml")
    assert release["jobs"]["matrix"]["uses"] == "./.github/workflows/integration-full.yml"
    assert "matrix" in release["jobs"]["build"]["needs"]


def test_classify_lists_unquoted_paths_on_both_sides_of_a_rename() -> None:
    run = CI["jobs"]["classify"]["steps"][1]["run"]
    assert "git -c core.quotePath=false diff --no-renames --name-only HEAD^1 HEAD" in run
    assert pr("docs/한국어.md")["tier"] == "docs"
    assert pr("cubrid_mcp_server/한국어.py")["live"] is True


def test_cli_works_without_docstrings() -> None:
    result = subprocess.run(
        [sys.executable, "-OO", str(SCRIPT), "--event", "push"],
        input="",
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines()[0] == "tier=full"


def _if(expression: str, event: str, sha: str = "") -> bool:
    """Evaluate a GitHub ``if`` expression of only ``!``, ``&&``, ``||`` and ``==``."""
    body = expression.strip().removeprefix("${{").removesuffix("}}")
    python = body.replace("&&", " and ").replace("||", " or ")
    python = re.sub(r"!(?!=)", " not ", python)
    python = python.replace("github.event_name", "event").replace("inputs.sha", "sha")
    assert not re.findall(r"[a-z]+\.[a-z_.]+", python), python
    return bool(eval(python, {"__builtins__": {}}, {"event": event, "sha": sha}))  # noqa: S307


def test_matrix_cells_record_the_image_they_ran() -> None:
    steps = FULL["jobs"]["integration-full"]["steps"]
    names = [step.get("name", "") for step in steps]
    record = steps[names.index("Record CUBRID image")]
    assert names.index("Record CUBRID image") > names.index("Pytest (integration)")
    assert record["if"] == "always()"
    assert record["run"] == (
        'python3 scripts/latest_server.py record --tag "${{ matrix.cubrid }}"'
        ' --summary "$GITHUB_STEP_SUMMARY"'
    )


@pytest.mark.parametrize(
    ("event", "sha", "runs"),
    [
        ("schedule", "", True),
        ("workflow_dispatch", "", True),
        # Under workflow_call github.event_name is the caller's event; publish-pypi.yml
        # always passes the release SHA, so no release run starts the advisory job.
        ("push", "a" * 40, False),
        ("workflow_dispatch", "a" * 40, False),
        ("schedule", "a" * 40, False),
        ("pull_request", "", False),
    ],
)
def test_newest_image_check_runs_weekly_and_manually_but_never_in_a_release(
    event: str, sha: str, runs: bool
) -> None:
    job = FULL["jobs"]["latest-server"]
    assert _if(job["if"], event, sha) is runs


def test_newest_image_check_cannot_gate_the_matrix_or_a_release() -> None:
    jobs = FULL["jobs"]
    job = jobs["latest-server"]
    assert job["continue-on-error"] is True
    assert "needs" not in job
    assert "latest-server" not in jobs["full-matrix-result"]["needs"]
    assert "latest-server" not in jobs["integration-full"].get("needs", [])
    canary = next(step for step in job["steps"] if step.get("id") == "canary")
    assert canary["if"] == "steps.resolve.outputs.canary == 'true'"
    # The canary runs the resolved immutable digest, never a moving tag.
    assert canary["env"] == {"CANARY_IMAGE": "${{ steps.resolve.outputs.image }}"}
    assert 'docker tag "$CANARY_IMAGE" cubrid/cubrid:newest-canary' in canary["run"]
    assert "make integration CUBRID_VERSION=newest-canary" in canary["run"]
