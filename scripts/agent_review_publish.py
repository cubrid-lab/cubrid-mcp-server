#!/usr/bin/env python3
"""Publish the agent-review verdict as a check run owned by a GitHub App (#393).

``.github/workflows/agent-review.yml`` posts its verdict as a GitHub Actions
check, which any PR can imitate with a job of the same name (#345). This script
posts the same verdict through a GitHub App installation token instead, so a
ruleset can require ``agent-review`` pinned to the App's ``integration_id``, an
identity no PR workflow can publish as.

The decision is ``scripts/agent_review_gate.py`` unchanged: this file only loads
it from beside itself, runs ``fetch`` and ``evaluate`` for each PR and posts a
completed ``agent-review`` check run on the PR head. It never checks out or runs
PR code. ``.github/workflows/agent-review-app.yml`` runs it from the default
branch on ``pull_request_target``, on a schedule (reviews by bots and thread
resolutions send no usable event) and on manual dispatch.

A check run is not posted again while the App's latest ``agent-review`` run on
the head already has the same conclusion and summary. Missing API data for a PR
posts a failing check when its head is known; any other API error fails the run.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

CHECK_NAME = "agent-review"
SUMMARY_LIMIT = 60000  # GitHub accepts at most 65535 characters.


def _load_gate() -> ModuleType:
    path = Path(__file__).resolve().with_name("agent_review_gate.py")
    loaded = sys.modules.get("agent_review_gate")
    if loaded is not None and getattr(loaded, "__file__", None) == str(path):
        return loaded
    spec = importlib.util.spec_from_file_location("agent_review_gate", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["agent_review_gate"] = module  # dataclasses resolve their module
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


class Client(gate.Client):  # type: ignore[name-defined,misc]
    """The gate's read-only client plus the one write this script needs."""

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request(f"{gate.API}/{path}", json.dumps(payload).encode())[0]


def open_prs(client: Any, repo: str, base: str) -> list[int]:
    query = urllib.parse.urlencode({"state": "open", "base": base})
    return [
        int(gate._require(pr, "number")) for pr in client.paginate(f"repos/{repo}/pulls?{query}")
    ]


def latest_run(client: Any, repo: str, head: str, app_id: int) -> dict[str, Any] | None:
    query = urllib.parse.urlencode({"check_name": CHECK_NAME, "app_id": app_id, "filter": "latest"})
    runs = client.get(f"repos/{repo}/commits/{head}/check-runs?{query}")
    items = runs.get("check_runs") if isinstance(runs, dict) else None
    if not isinstance(items, list):
        raise gate.GateError("unexpected check-run listing")
    return items[0] if items else None


def publish(client: Any, repo: str, number: int, app_id: int) -> str:
    """Post the verdict for one PR; return "posted" or "unchanged".

    The verdict is posted on the head that ``fetch`` evaluated, and only while
    that is still the PR head: a push during the evaluation fails this PR, and
    the run for the new head decides.
    """
    try:
        data = gate.fetch(client, repo, number)
        head = gate._require(data["pr"], "head", "sha")
        verdict = gate.evaluate(data)
    except gate.GateError as exc:
        head = gate._require(client.get(f"repos/{repo}/pulls/{number}"), "head", "sha")
        verdict = gate.Verdict(errors=[f"Failing closed on missing API data: {exc}"])
    status = "exempt" if verdict.exempt else ("passed" if verdict.passed else "failed")
    conclusion = "success" if verdict.passed else "failure"
    summary = gate.render(verdict, number, False)[:SUMMARY_LIMIT]

    previous = latest_run(client, repo, head, app_id)
    if (
        previous is not None
        and previous.get("conclusion") == conclusion
        and (previous.get("output") or {}).get("summary") == summary
    ):
        return "unchanged"
    current = gate._require(client.get(f"repos/{repo}/pulls/{number}"), "head", "sha")
    if current != head:
        raise gate.GateError(f"the head moved from {head[:12]} to {current[:12]} during evaluation")
    client.post(
        f"repos/{repo}/check-runs",
        {
            "name": CHECK_NAME,
            "head_sha": head,
            "status": "completed",
            "conclusion": conclusion,
            "output": {"title": f"agent-review: {status}", "summary": summary},
        },
    )
    return "posted"


def main(
    argv: list[str] | None = None,
    client_factory: Callable[[str], Any] = Client,
) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--app-id", required=True, type=int, help="the App's ID")
    parser.add_argument("--base", default="main", help="base branch of the swept PRs")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--pr", type=int, action="append", help="PR number (repeatable)")
    target.add_argument("--all-open", action="store_true", help="every open PR into --base")
    args = parser.parse_args(argv)

    try:
        client = client_factory(os.environ.get("GH_TOKEN", ""))
        numbers = args.pr or open_prs(client, args.repo, args.base)
    except gate.GateError as exc:
        print(f"::error title=agent-review-app::{gate.command_data(str(exc))}")
        return 1
    failed = False
    for number in numbers:
        try:
            print(f"PR #{number}: {publish(client, args.repo, number, args.app_id)}")
        except gate.GateError as exc:
            failed = True
            message = gate.command_data(f"PR #{number}: {exc}")
            print(f"::error title=agent-review-app::{message}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
