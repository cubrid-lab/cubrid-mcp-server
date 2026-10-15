"""Offline checks for the agent-review evidence gate (#317).

``scripts/agent_review_gate.py`` decides from GitHub review records; these tests
feed it fixture records shaped like the REST/GraphQL responses (field names as
GitHub returns them) and check the workflow contract that runs it.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "agent-review.yml"
SCRIPT = ROOT / "scripts" / "agent_review_gate.py"

_spec = importlib.util.spec_from_file_location("agent_review_gate", SCRIPT)
assert _spec and _spec.loader
gate = importlib.util.module_from_spec(_spec)
sys.modules["agent_review_gate"] = gate
_spec.loader.exec_module(gate)

REPO = "cubrid-lab/cubrid-mcp-server"
HEAD = "h" * 40
OLD = "o" * 40
AUTHOR = "agent-operator"
MAINTAINER = "maintainer"
COPILOT = "copilot-pull-request-reviewer[bot]"

COPILOT_OVERVIEW = """<!-- ccr-overview-v2 -->

### 🟢 Approval recommended

The read-only check rejects the new statement form and the tests cover both modes.

**0 open findings**

<details>
<summary><strong>What changed in this PR</strong></summary>

Adds a check.
</details>
"""
COPILOT_FINDING = """<!-- ccr-overview-v2 -->

### 🟡 Changes recommended

The audit record can echo a literal.

<details open>
<summary><strong>1 open finding</strong></summary>

- <picture><img src="x.png" alt="High severity"></picture> [Audit echoes a literal](https://github.com/cubrid-lab/cubrid-mcp-server/pull/7#discussion_r901) · New
</details>
"""
COPILOT_SUMMARY_ONLY = """<!-- ccr-overview-v2 -->

<details>
<summary><strong>What changed in this PR</strong></summary>

Adds a check.

| File | Description |
| ---- | ----------- |
| `README.md` | Docs. |
</details>
"""
COPILOT_QUOTA = (
    "Copilot was unable to review this pull request because the requesting user "
    "has reached their quota."
)


def user(login: str, kind: str = "User") -> dict[str, Any]:
    return {"login": login, "type": kind}


def review(
    login: str,
    state: str = "COMMENTED",
    sha: str = HEAD,
    body: str = "",
    association: str = "MEMBER",
    at: str = "2026-10-15T01:00:00Z",
    review_id: int = 1,
) -> dict[str, Any]:
    kind = "Bot" if login.endswith("[bot]") else "User"
    return {
        "id": review_id,
        "user": user(login, kind),
        "state": state,
        "commit_id": sha,
        "submitted_at": at,
        "body": body,
        "author_association": "NONE" if kind == "Bot" else association,
    }


def copilot(body: str = COPILOT_OVERVIEW, sha: str = HEAD, **kw: Any) -> dict[str, Any]:
    return review(COPILOT, "COMMENTED", sha, body, **kw)


def commit(sha: str, author: str = AUTHOR, parents: int = 1, first: str = "") -> dict[str, Any]:
    shas = [first or "p0"] + [f"p{i}" for i in range(1, parents)]
    return {
        "sha": sha,
        "author": user(author),
        "committer": user("web-flow"),
        "parents": [{"sha": s} for s in shas[:parents]],
        "commit": {"verification": {"verified": True}},
    }


def change(
    patch: str = "@@ -1,2 +1,3 @@\n x\n+y", path: str = "cubrid_mcp_server/config.py"
) -> Any:
    """The fingerprint of a ``base...commit`` compare that changes one file."""
    compare = {"files": [{"filename": path, "status": "modified", "patch": patch, "changes": 1}]}
    return gate.diff_fingerprint(compare)


SAME = change()
MOVED = change("@@ -40,2 +41,3 @@\n x\n+y")  # the same lines at another place
OTHER = change("@@ -1,2 +1,3 @@\n x\n+z")


def data(
    reviews: list[dict[str, Any]] | None = None,
    files: tuple[str, ...] = ("cubrid_mcp_server/config.py",),
    author: str = AUTHOR,
    branch: str = "feature/x",
    head_repo: str | None = REPO,
    commits: list[dict[str, Any]] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    commits = commits if commits is not None else [commit(HEAD, author)]
    pr = {
        "user": user(author, "Bot" if author.endswith("[bot]") else "User"),
        "head": {
            "sha": HEAD,
            "ref": branch,
            "repo": {"full_name": head_repo} if head_repo else None,
        },
        "base": {"ref": "main", "repo": {"full_name": REPO}},
        "body": extra.pop("body", "- Development route: standalone Claude Code"),
        "commits": len(commits),
        "changed_files": len(files),
        "requested_reviewers": extra.pop("requested", []),
        "requested_teams": [],
    }
    return {
        "repo": REPO,
        "pr": pr,
        "reviews": reviews or [],
        "comments": extra.pop("comments", []),
        "commits": commits,
        "files": [{"filename": f} for f in files],
        "threads": extra.pop("threads", []),
        "diffs": extra.pop("diffs", {}),
    }


def evaluate(records: dict[str, Any], event_head: str = HEAD) -> Any:
    return gate.evaluate(records, event_head)


# ------------------------------------------------------------------ positive


def test_substantive_copilot_review_of_the_head_passes() -> None:
    verdict = evaluate(data([copilot()]))
    assert verdict.passed, verdict.errors
    assert any("AI round 1" in e for e in verdict.evidence)


def test_copilot_review_with_inline_comments_is_substantive() -> None:
    records = data(
        [copilot(COPILOT_SUMMARY_ONLY, review_id=5)],
        comments=[{"pull_request_review_id": 5}],
    )
    assert evaluate(records).passed


def test_trusted_approval_passes() -> None:
    assert evaluate(data([review(MAINTAINER, "APPROVED")])).passed


def test_trusted_substantive_commented_review_passes_ordinary_paths() -> None:
    body = "Checked the timeout handling and the new test; looks right."
    verdict = evaluate(data([review(MAINTAINER, "COMMENTED", body=body)]))
    assert verdict.passed
    assert any("COMMENTED is not approval" in e for e in verdict.evidence)


# ------------------------------------------------------------------ negative


def test_no_review_fails() -> None:
    verdict = evaluate(data())
    assert not verdict.passed
    assert any("No qualifying review" in e for e in verdict.errors)


def test_pending_review_request_is_not_evidence() -> None:
    records = data(requested=[user(COPILOT, "Bot")])
    pending = copy.deepcopy(copilot())
    pending.update(state="PENDING", submitted_at=None)
    records["reviews"] = [pending]
    verdict = evaluate(records)
    assert not verdict.passed
    assert any("Pending review request" in n for n in verdict.notes)


def test_pr_body_checkboxes_are_not_evidence() -> None:
    body = "- [x] Copilot reviewed\n- [x] Maintainer approved\n- Development route: human"
    verdict = evaluate(data(body=body))
    assert not verdict.passed
    assert any("never evidence" in n and "human" in n for n in verdict.notes)


def test_copilot_summary_without_assessment_is_rejected() -> None:
    verdict = evaluate(data([copilot(COPILOT_SUMMARY_ONLY)]))
    assert not verdict.passed
    assert any("without an assessment" in w for w in verdict.warnings)


def test_copilot_quota_notice_is_not_a_round() -> None:
    records = data([copilot(COPILOT_QUOTA, at="2026-10-15T00:00:00Z", review_id=1)])
    verdict = evaluate(records)
    assert not verdict.passed
    assert any("quota notice" in n for n in verdict.notes)
    records["reviews"].append(copilot(at="2026-10-15T02:00:00Z", review_id=2))
    verdict = evaluate(records)
    assert verdict.passed
    assert any("AI round 1" in e for e in verdict.evidence)


def test_self_review_is_rejected() -> None:
    body = "I checked everything carefully and it is fine."
    verdict = evaluate(data([review(AUTHOR, "COMMENTED", body=body)]))
    assert not verdict.passed
    assert any("self-review" in w for w in verdict.warnings)


def test_reviewer_who_committed_to_the_pr_is_rejected() -> None:
    commits = [commit(OLD), commit(HEAD, MAINTAINER)]
    verdict = evaluate(data([review(MAINTAINER, "APPROVED")], commits=commits))
    assert not verdict.passed
    assert any("authored commits" in w for w in verdict.warnings)


def test_untrusted_and_other_bot_reviews_are_rejected() -> None:
    reviews = [
        review("stranger", "APPROVED", association="NONE", review_id=1),
        review("some-bot[bot]", "APPROVED", review_id=2),
    ]
    verdict = evaluate(data(reviews))
    assert not verdict.passed
    assert any("association NONE" in w for w in verdict.warnings)
    assert any("bot other than Copilot" in w for w in verdict.warnings)


def test_thread_reply_is_not_an_assessment() -> None:
    records = data(
        [review(MAINTAINER, "COMMENTED", review_id=9)],
        comments=[{"pull_request_review_id": 9, "in_reply_to_id": 4}],
    )
    assert not evaluate(records).passed
    records["comments"].append({"pull_request_review_id": 9, "in_reply_to_id": None})
    assert evaluate(records).passed


def test_empty_commented_review_is_rejected() -> None:
    verdict = evaluate(data([review(MAINTAINER, "COMMENTED", body="LGTM")]))
    assert not verdict.passed


def test_changes_requested_blocks_until_superseded() -> None:
    reviews = [
        review(MAINTAINER, "CHANGES_REQUESTED", body="no", review_id=1),
        copilot(review_id=2, at="2026-10-15T02:00:00Z"),
    ]
    verdict = evaluate(data(reviews))
    assert not verdict.passed
    assert any("requested changes" in e for e in verdict.errors)
    reviews.append(review(MAINTAINER, "APPROVED", review_id=3, at="2026-10-15T03:00:00Z"))
    assert evaluate(data(reviews)).passed


# -------------------------------------------------------- COMMENTED vs APPROVED


@pytest.mark.parametrize(
    "path",
    [
        "cubrid_mcp_server/safety.py",
        "cubrid_mcp_server/database.py",
        "cubrid_mcp_server/audit.py",
        "cubrid_mcp_server/server.py",
        ".github/workflows/publish-pypi.yml",
        ".github/workflows/release-please.yml",
        ".github/workflows/dependabot-auto-merge.yml",
        ".github/workflows/agent-review.yml",
        "scripts/agent_review_gate.py",
    ],
)
def test_protected_paths_need_trusted_approval(path: str) -> None:
    body = "Reviewed the read-only enforcement and the new tests in detail."
    commented = [copilot(review_id=1), review(MAINTAINER, "COMMENTED", body=body, review_id=2)]
    verdict = evaluate(data(commented, files=(path,)))
    assert not verdict.passed
    assert any("Protected paths" in e for e in verdict.errors)
    approved = [*commented, review(MAINTAINER, "APPROVED", review_id=3)]
    assert evaluate(data(approved, files=(path,))).passed


def test_rename_away_from_a_protected_path_is_protected() -> None:
    records = data([copilot()], files=("cubrid_mcp_server/other.py",))
    records["files"][0]["previous_filename"] = "cubrid_mcp_server/safety.py"
    assert not evaluate(records).passed


def test_every_write_or_release_workflow_is_protected() -> None:
    folder = ROOT / ".github" / "workflows"
    for path in sorted([*folder.glob("*.yml"), *folder.glob("*.yaml")]):
        text = path.read_text()
        workflow = yaml.safe_load(text)
        scopes = [workflow.get("permissions") or {}]
        scopes += [job.get("permissions") or {} for job in workflow["jobs"].values()]
        writes = any(
            scope == "write-all" or (isinstance(scope, dict) and "write" in scope.values())
            for scope in scopes
        )
        releases = "release" in path.name or "publish" in path.name
        if writes or releases:
            assert gate.protected_paths([f".github/workflows/{path.name}"]), path.name


# ---------------------------------------------------------------- stale head


def test_review_of_an_older_commit_is_stale() -> None:
    records = data([copilot(sha=OLD)], diffs={OLD: SAME, HEAD: OTHER})
    verdict = evaluate(records)
    assert not verdict.passed
    assert any("Stale" in n for n in verdict.notes)


def test_unchanged_pr_change_carries_a_review_forward() -> None:
    # An "Update branch" merge (with the base commits it imports) or a rebase that
    # leaves the PR's own change exactly as it was.
    merge = commit(HEAD, MAINTAINER, parents=2, first=OLD)
    records = data([copilot(sha=OLD)], commits=[commit(OLD), merge], diffs={OLD: SAME, HEAD: SAME})
    verdict = evaluate(records)
    assert verdict.passed
    assert any("carried forward" in e for e in verdict.evidence)


def test_edit_relocated_to_identical_context_is_stale() -> None:
    # Reverting the reviewed edit and applying it to another block with the same
    # context leaves the same patch lines at other line numbers.
    assert not evaluate(data([copilot(sha=OLD)], diffs={OLD: SAME, HEAD: MOVED})).passed


@pytest.mark.parametrize("fingerprint", [None, []])
def test_unknown_or_empty_change_is_not_carried_forward(fingerprint: Any) -> None:
    records = data([copilot(sha=OLD)], diffs={OLD: fingerprint, HEAD: SAME})
    assert not evaluate(records).passed


def test_force_pushed_review_commit_is_stale() -> None:
    assert not evaluate(data([copilot(sha=OLD)], diffs={HEAD: SAME})).passed


def test_fingerprint_rejects_incomplete_compares() -> None:
    assert gate.diff_fingerprint(None) is None
    assert gate.diff_fingerprint({"files": [{"filename": "a.bin", "changes": 4}]}) is None
    assert gate.diff_fingerprint({"files": [{"filename": "x"}] * 300}) is None
    renamed = {"files": [{"filename": "b", "status": "renamed", "changes": 0}]}
    assert gate.diff_fingerprint(renamed) == [["b", "renamed", "", ""]]


def test_author_of_a_code_changing_merge_cannot_approve() -> None:
    merge = commit(HEAD, MAINTAINER, parents=2, first=OLD)
    records = data(
        [review(MAINTAINER, "APPROVED")],
        commits=[commit(OLD), merge],
        diffs={OLD: SAME, HEAD: OTHER},
    )
    verdict = evaluate(records)
    assert not verdict.passed
    assert any("authored commits" in w for w in verdict.warnings)
    records["diffs"] = {OLD: SAME, HEAD: SAME}
    assert evaluate(records).passed


def test_event_for_an_older_head_fails() -> None:
    verdict = evaluate(data([copilot()]), event_head=OLD)
    assert not verdict.passed
    assert any("no longer the PR head" in e for e in verdict.errors)


def test_three_copilot_reviews_of_the_same_head_need_a_person() -> None:
    reviews = [copilot(review_id=i, at=f"2026-10-15T0{i}:00:00Z") for i in (1, 2, 3)]
    verdict = evaluate(data(reviews))
    assert not verdict.passed
    assert not verdict.evidence


def test_third_copilot_round_needs_a_person() -> None:
    reviews = [
        copilot(sha=OLD, review_id=1, at="2026-10-15T01:00:00Z"),
        copilot(sha=OLD, review_id=2, at="2026-10-15T02:00:00Z"),
        copilot(sha=HEAD, review_id=3, at="2026-10-15T03:00:00Z"),
    ]
    verdict = evaluate(data(reviews))
    assert not verdict.passed
    assert any("past the 2-round" in w for w in verdict.warnings)
    reviews.append(review(MAINTAINER, "APPROVED", review_id=4, at="2026-10-15T04:00:00Z"))
    assert evaluate(data(reviews)).passed


# ------------------------------------------------------------ review threads


def thread(comment_id: int, body: str, resolved: bool = False, by: str = "") -> dict[str, Any]:
    return {
        "isResolved": resolved,
        "isOutdated": False,
        "resolvedBy": {"login": by} if by else None,
        "comments": {
            "nodes": [
                {
                    "databaseId": comment_id,
                    "body": body,
                    "url": f"https://example.invalid/{comment_id}",
                    "path": "cubrid_mcp_server/audit.py",
                    "author": {"login": "Copilot"},
                }
            ]
        },
    }


def test_unresolved_high_severity_copilot_finding_blocks() -> None:
    records = data([copilot(COPILOT_FINDING)], threads=[thread(901, "Echoes a value.")])
    verdict = evaluate(records)
    assert not verdict.passed
    assert any("Unresolved high-severity finding" in e for e in verdict.errors)


def test_unresolved_security_thread_blocks_and_ordinary_one_is_noted() -> None:
    records = data(
        [copilot()],
        threads=[thread(1, "Nit: rename this variable."), thread(2, "This is a security bypass.")],
    )
    verdict = evaluate(records)
    assert not verdict.passed
    assert len(verdict.errors) == 1
    assert any("Unresolved thread" in n for n in verdict.notes)


@pytest.mark.parametrize(
    "broken", [{"databaseId": None}, {"databaseId": 0}, {"body": None}, {"databaseId": True}]
)
def test_incomplete_thread_fails_closed(broken: dict[str, Any]) -> None:
    item = thread(5, "Nit: naming.")
    item["comments"]["nodes"][0].update(broken)
    assert run_main(data([copilot()], threads=[item])) == 1


def test_security_reply_makes_a_thread_blocking() -> None:
    reply = {"pull_request_review_id": 8, "in_reply_to_id": 3, "body": "It leaks credentials."}
    records = data([copilot()], threads=[thread(3, "Nit: naming.")], comments=[reply])
    assert not evaluate(records).passed


def test_plural_privileges_is_a_security_word() -> None:
    records = data([copilot()], threads=[thread(4, "This grants excessive privileges.")])
    assert not evaluate(records).passed


def test_security_thread_resolved_by_the_author_is_flagged() -> None:
    records = data([copilot()], threads=[thread(2, "Possible SQL injection.", True, AUTHOR)])
    verdict = evaluate(records)
    assert verdict.passed
    assert any("resolved by the PR author" in w for w in verdict.warnings)


# ------------------------------------------------- exemptions and fork PRs


def test_release_please_candidate_is_exempt() -> None:
    records = data(
        author="github-actions[bot]",
        branch="release-please--branches--main--components--cubrid-mcp-server",
        commits=[commit(HEAD, "github-actions[bot]"), commit(OLD, MAINTAINER)],
        files=("CHANGELOG.md", "cubrid_mcp_server/__init__.py"),
    )
    verdict = evaluate(records)
    assert verdict.passed and "release-please" in verdict.exempt


def test_dependabot_update_with_branch_sync_is_exempt() -> None:
    records = data(
        author="dependabot[bot]",
        branch="dependabot/github_actions/x",
        commits=[commit(OLD, "dependabot[bot]"), commit(HEAD, MAINTAINER, parents=2)],
        files=(".github/workflows/publish-pypi.yml",),
        diffs={OLD: SAME, HEAD: SAME},
    )
    records["commits"][1]["parents"][0]["sha"] = OLD
    assert evaluate(records).passed
    records["diffs"] = {OLD: SAME, HEAD: OTHER}
    assert not evaluate(records).passed


@pytest.mark.parametrize(
    "amend",
    [{"committer": {"login": MAINTAINER}}, {"commit": {"verification": {"verified": False}}}],
)
def test_amended_dependabot_commit_is_not_exempt(amend: dict[str, Any]) -> None:
    bot = commit(HEAD, "dependabot[bot]")
    bot.update(amend)
    records = data(
        author="dependabot[bot]",
        branch="dependabot/pip/x",
        commits=[bot],
        files=("cubrid_mcp_server/safety.py",),
    )
    assert not evaluate(records).passed


def test_dependabot_pr_with_a_human_commit_is_evaluated() -> None:
    records = data(
        author="dependabot[bot]",
        branch="dependabot/pip/x",
        commits=[commit(OLD, "dependabot[bot]"), commit(HEAD, MAINTAINER)],
    )
    assert not evaluate(records).passed


@pytest.mark.parametrize(
    ("author", "branch"),
    [
        ("github-actions[bot]", "release-please--branches--main"),
        ("dependabot[bot]", "dependabot/x"),
    ],
)
def test_fork_never_gets_an_exemption(author: str, branch: str) -> None:
    records = data(
        author=author, branch=branch, head_repo="someone/fork", commits=[commit(HEAD, author)]
    )
    assert not evaluate(records).passed


def test_fork_pr_is_evaluated_like_any_other() -> None:
    records = data(author="outside", head_repo=None, commits=[commit(HEAD, "outside")])
    assert not evaluate(records).passed
    records["reviews"] = [review(MAINTAINER, "APPROVED")]
    assert evaluate(records).passed


# ------------------------------------------------------- API errors (fail closed)


class FakeClient:
    def __init__(self, records: dict[str, Any], fail: str = "") -> None:
        self.records = records
        self.fail = fail

    def _check(self, path: str) -> None:
        if self.fail and self.fail in path:
            raise gate.GateError(f"HTTP 502 for {path}")

    def get(self, path: str) -> Any:
        self._check(path)
        return self.records["pr"]

    def get_optional(self, path: str) -> Any:
        self._check(path)
        assert path.startswith(f"repos/{REPO}/compare/main...")
        return None

    def paginate(self, path: str) -> list[Any]:
        self._check(path)
        key = path.rsplit("/", 1)[1]
        return list(self.records[key])

    def graphql(self, query: str, variables: dict[str, Any]) -> Any:
        self._check("graphql")
        return {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": self.records["threads"],
                    }
                }
            }
        }


def run_main(records: dict[str, Any], fail: str = "", extra: tuple[str, ...] = ()) -> int:
    def factory(token: str) -> FakeClient:
        return FakeClient(records, fail)

    argv = ["--repo", REPO, "--pr", "7", "--event-head-sha", HEAD, *extra]
    return int(gate.main(argv, factory))


def test_main_passes_and_writes_the_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert run_main(data([copilot()])) == 0
    assert "agent-review: passed" in summary.read_text()


@pytest.mark.parametrize("fail", ["pulls/7", "reviews", "comments", "commits", "files", "graphql"])
def test_api_error_fails_closed(fail: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_main(data([copilot()]), fail) == 1
    assert "Failing closed" in capsys.readouterr().out


def test_missing_field_fails_closed() -> None:
    records = data([copilot()])
    del records["reviews"][0]["state"]
    assert run_main(records) == 1


@pytest.mark.parametrize(
    "broken",
    [
        {"state": "CHANGES_REQUESTED", "submitted_at": None},
        {"state": "APPROVED", "user": {"type": "User"}},
    ],
)
def test_incomplete_review_record_fails_closed(broken: dict[str, Any]) -> None:
    records = data([copilot(review_id=1), review(MAINTAINER, review_id=2)])
    records["reviews"][1].update(broken)
    assert run_main(records) == 1


def test_truncated_listing_fails_closed() -> None:
    records = data([copilot()])
    records["pr"]["changed_files"] = 5
    assert run_main(records) == 1


def test_missing_token_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert gate.main(["--repo", REPO, "--pr", "7"]) == 1


def test_bootstrap_is_advisory() -> None:
    assert run_main(data(), extra=("--bootstrap",)) == 0


# ---------------------------------------------------------- workflow contract


def test_workflow_triggers_and_permissions_are_read_only() -> None:
    text = WORKFLOW.read_text()
    workflow = yaml.safe_load(text)
    triggers = workflow[True]  # YAML 1.1 reads the "on" key as True.
    assert set(triggers) == {"pull_request", "pull_request_review"}
    assert "pull_request_target" not in triggers
    assert workflow["permissions"] == {}
    job = workflow["jobs"]["agent-review"]
    assert job["name"] == "agent-review"
    assert job["permissions"] == {"contents": "read", "pull-requests": "read"}
    steps = job["steps"]
    assert all("uses" not in step for step in steps), "the job checks out nothing"
    run = steps[0]["run"]
    assert "${{" not in run
    assert 'ref=$BASE_REF"' in run
    assert "python3 -I" in run
    assert '[ "$HEAD_REPO" = "$GITHUB_REPOSITORY" ]' in run
