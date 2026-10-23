"""Offline checks for the App-owned agent-review publisher (#393).

``scripts/agent_review_publish.py`` reuses the gate's decision unchanged and
posts it as a check run; these tests drive it with a fake client and check the
workflow contract that keeps it on the default branch.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "agent-review-app.yml"
SCRIPT = ROOT / "scripts" / "agent_review_publish.py"

_spec = importlib.util.spec_from_file_location("agent_review_publish", SCRIPT)
assert _spec and _spec.loader
publisher = importlib.util.module_from_spec(_spec)
sys.modules["agent_review_publish"] = publisher
_spec.loader.exec_module(publisher)
gate = publisher.gate

REPO = "cubrid-lab/cubrid-mcp-server"
HEAD = "h" * 40
APP_ID = 4242


class FakeClient:
    """Answers the publisher's own calls; the gate's fetch/evaluate are stubbed."""

    def __init__(
        self, previous: list[dict[str, Any]] | None = None, fail: str = "", head: str = HEAD
    ) -> None:
        self.previous = previous or []
        self.fail = fail
        self.head = head  # what the PR endpoint reports now
        self.gets: list[str] = []
        self.posts: list[tuple[str, dict[str, Any]]] = []

    def get(self, path: str) -> Any:
        self.gets.append(path)
        if self.fail and self.fail in path:
            raise gate.GateError(f"HTTP 502 for {path}")
        if "/check-runs?" in path:
            return {"total_count": len(self.previous), "check_runs": self.previous}
        return {"number": int(path.rsplit("/", 1)[1]), "head": {"sha": self.head}}

    def paginate(self, path: str) -> list[Any]:
        self.gets.append(path)
        if self.fail and self.fail in path:
            raise gate.GateError(f"HTTP 502 for {path}")
        return [{"number": 7}, {"number": 9}]

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        self.posts.append((path, payload))
        return {"id": 1}


@pytest.fixture
def verdict(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Stub the gate decision; set ``state["verdict"]`` or ``state["error"]``."""
    state: dict[str, Any] = {"verdict": gate.Verdict(passed=True, evidence=["ok"]), "error": None}

    def fetch(client: Any, repo: str, number: int) -> dict[str, Any]:
        if state["error"]:
            raise gate.GateError(state["error"])
        return {"pr": {"number": number, "head": {"sha": HEAD}}}

    monkeypatch.setattr(gate, "fetch", fetch)
    monkeypatch.setattr(gate, "evaluate", lambda data: state["verdict"])
    return state


def summary_of(v: Any, number: int = 7) -> str:
    return str(gate.render(v, number, False))


def test_posts_a_completed_check_run_on_the_head(verdict: dict[str, Any]) -> None:
    client = FakeClient()
    assert publisher.publish(client, REPO, 7, APP_ID) == "posted"
    ((path, payload),) = client.posts
    assert path == f"repos/{REPO}/check-runs"
    assert payload["name"] == "agent-review"
    assert payload["head_sha"] == HEAD
    assert payload["status"] == "completed"
    assert payload["conclusion"] == "success"
    assert payload["output"]["title"] == "agent-review: passed"
    assert payload["output"]["summary"] == summary_of(verdict["verdict"])
    listing = next(p for p in client.gets if "/check-runs?" in p)
    assert f"commits/{HEAD}/check-runs?" in listing
    assert f"app_id={APP_ID}" in listing and "check_name=agent-review" in listing


def test_a_failed_verdict_fails_the_check(verdict: dict[str, Any]) -> None:
    verdict["verdict"] = gate.Verdict(errors=["no qualifying review"])
    client = FakeClient()
    publisher.publish(client, REPO, 7, APP_ID)
    payload = client.posts[0][1]
    assert payload["conclusion"] == "failure"
    assert payload["output"]["title"] == "agent-review: failed"


def test_an_exempt_pr_passes_and_says_so(verdict: dict[str, Any]) -> None:
    verdict["verdict"] = gate.Verdict(passed=True, exempt="release-please candidate")
    client = FakeClient()
    publisher.publish(client, REPO, 7, APP_ID)
    assert client.posts[0][1]["conclusion"] == "success"
    assert client.posts[0][1]["output"]["title"] == "agent-review: exempt"


def test_an_unchanged_verdict_is_not_posted_again(verdict: dict[str, Any]) -> None:
    previous = {"conclusion": "success", "output": {"summary": summary_of(verdict["verdict"])}}
    client = FakeClient(previous=[previous])
    assert publisher.publish(client, REPO, 7, APP_ID) == "unchanged"
    assert client.posts == []


@pytest.mark.parametrize(
    "previous",
    [
        pytest.param({"conclusion": "failure", "output": {"summary": "x"}}, id="conclusion"),
        pytest.param({"conclusion": "success", "output": {"summary": "older"}}, id="summary"),
        pytest.param({"conclusion": "success", "output": None}, id="no-output"),
    ],
)
def test_a_changed_verdict_is_posted(verdict: dict[str, Any], previous: dict[str, Any]) -> None:
    client = FakeClient(previous=[previous])
    assert publisher.publish(client, REPO, 7, APP_ID) == "posted"


def test_missing_review_data_posts_a_failing_check(verdict: dict[str, Any]) -> None:
    verdict["error"] = "HTTP 502 for repos/x/pulls/7/reviews"
    client = FakeClient()
    assert publisher.publish(client, REPO, 7, APP_ID) == "posted"
    payload = client.posts[0][1]
    assert payload["conclusion"] == "failure"
    assert "Failing closed on missing API data" in payload["output"]["summary"]


def test_a_head_that_moved_during_evaluation_is_not_posted(verdict: dict[str, Any]) -> None:
    client = FakeClient(head="n" * 40)  # a push landed after fetch read HEAD
    with pytest.raises(gate.GateError, match="head moved"):
        publisher.publish(client, REPO, 7, APP_ID)
    assert client.posts == []


def test_the_check_goes_on_the_evaluated_head(verdict: dict[str, Any]) -> None:
    client = FakeClient()
    publisher.publish(client, REPO, 7, APP_ID)
    assert client.posts[0][1]["head_sha"] == HEAD
    assert f"commits/{HEAD}/check-runs?" in next(p for p in client.gets if "check-runs" in p)


def test_a_long_summary_is_truncated(verdict: dict[str, Any]) -> None:
    verdict["verdict"] = gate.Verdict(errors=["x" * 70000])
    client = FakeClient()
    publisher.publish(client, REPO, 7, APP_ID)
    assert len(client.posts[0][1]["output"]["summary"]) == publisher.SUMMARY_LIMIT


def run_main(client: FakeClient, *args: str) -> int:
    argv = ["--repo", REPO, "--app-id", str(APP_ID), *args]
    return int(publisher.main(argv, client_factory=lambda token: client))


def test_sweep_evaluates_every_open_pr_into_the_base(verdict: dict[str, Any]) -> None:
    client = FakeClient()
    assert run_main(client, "--all-open") == 0
    assert f"repos/{REPO}/pulls?state=open&base=main" in client.gets
    assert [payload["head_sha"] for _, payload in client.posts] == [HEAD, HEAD]


def test_named_prs_are_evaluated_alone(verdict: dict[str, Any]) -> None:
    client = FakeClient()
    assert run_main(client, "--pr", "7") == 0
    assert not any(p.startswith(f"repos/{REPO}/pulls?") for p in client.gets)
    assert len(client.posts) == 1


def test_an_api_error_fails_the_run_but_not_the_other_prs(
    verdict: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(fail="/pulls/7")
    assert run_main(client, "--pr", "7", "--pr", "9") == 1
    assert len(client.posts) == 1  # PR 9 is still published
    assert "::error title=agent-review-app::PR #7: HTTP 502" in capsys.readouterr().out


def test_a_failed_sweep_listing_fails_closed(
    verdict: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(fail="pulls?state=open")
    assert run_main(client, "--all-open") == 1
    assert client.posts == []
    assert "::error title=agent-review-app::" in capsys.readouterr().out


def test_a_missing_token_fails_closed(capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["--repo", REPO, "--app-id", str(APP_ID), "--all-open"]
    assert publisher.main(argv, client_factory=publisher.Client) == 1
    assert "no API token" in capsys.readouterr().out


@pytest.mark.parametrize("args", [(), ("--pr", "7", "--all-open"), ("--pr", "x")])
def test_the_target_is_exactly_one_of_pr_or_all_open(args: tuple[str, ...]) -> None:
    with pytest.raises(SystemExit) as raised:
        run_main(FakeClient(), *args)
    assert raised.value.code == 2


def test_the_publisher_uses_the_gate_beside_it() -> None:
    assert Path(gate.__file__).resolve() == ROOT / "scripts" / "agent_review_gate.py"


# ---------------------------------------------------------- workflow contract


def test_workflow_runs_only_default_branch_code() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    triggers = workflow[True]  # YAML 1.1 reads the "on" key as True.
    assert set(triggers) == {
        "pull_request_target",
        "workflow_run",
        "schedule",
        "workflow_dispatch",
    }
    assert triggers["workflow_run"] == {"workflows": ["agent-review"], "types": ["completed"]}
    assert "pull_request" not in triggers and "pull_request_review" not in triggers
    assert workflow["permissions"] == {}
    assert workflow["concurrency"] == {"group": "agent-review-app", "cancel-in-progress": False}


def test_workflow_job_is_minimal_and_never_checks_out_the_pr() -> None:
    job = yaml.safe_load(WORKFLOW.read_text())["jobs"]["publish"]
    assert job["permissions"] == {"contents": "read"}
    assert job["environment"] == {"name": "agent-review-app"}
    assert "vars.AGENT_REVIEW_APP_ID != ''" in job["if"]
    assert "dependabot[bot]" in job["if"]
    checkout, token, run = job["steps"]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"] == {"ref": "main", "persist-credentials": False}
    assert token["uses"].startswith("actions/create-github-app-token@")
    assert token["with"]["permission-checks"] == "write"
    assert token["with"]["private-key"] == "${{ secrets.AGENT_REVIEW_APP_KEY }}"
    assert set(token["with"]) == {
        "app-id",
        "private-key",
        "permission-checks",
        "permission-contents",
        "permission-pull-requests",
    }
    assert "${{" not in run["run"]
    target = run["env"]["TARGET_PR"]
    assert "github.event.workflow_run.pull_requests[0].number" in target
    assert "github.event.pull_request.number" in target
    assert "python3 -I scripts/agent_review_publish.py" in run["run"]


def test_workflow_actions_are_pinned_to_full_shas() -> None:
    for step in yaml.safe_load(WORKFLOW.read_text())["jobs"]["publish"]["steps"]:
        if "uses" in step:
            ref = step["uses"].split("@", 1)[1]
            assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref)
