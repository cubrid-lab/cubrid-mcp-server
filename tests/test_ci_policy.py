"""CI hygiene policy: concurrency, grouped Dependabot updates, pinned docs tools.

Covers #243 (ci.yml concurrency, Dependabot groups), #244 (pinned docs build
tools) and #245 (CodeQL concurrency).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

CANCEL_ONLY_PR = "${{ github.event_name == 'pull_request' }}"
# Non-PR runs get a unique group so a queued main/schedule run is never replaced.
EXPECTED_GROUP = (
    "${{ github.workflow }}-"
    "${{ github.event_name == 'pull_request' && github.ref || github.run_id }}"
)
RUNTIME_DEPS = {"fastmcp", "pycubrid", "sqlparse"}
DEV_TOOLS = {"pytest*", "pre-commit", "tox", "build", "twine"}
ISOLATED_TOOLS = {"ruff", "mypy"}


def _load(path: Path) -> dict[str, Any]:
    return dict(yaml.safe_load(path.read_text()))


def _updates() -> dict[tuple[str, str], dict[str, Any]]:
    data = _load(ROOT / ".github" / "dependabot.yml")
    return {(u["package-ecosystem"], u["directory"]): u for u in data["updates"]}


@pytest.mark.parametrize("name", ["ci.yml", "codeql.yml"])
def test_only_pull_request_runs_are_cancelled(name: str) -> None:
    block = _load(WORKFLOWS / name)["concurrency"]
    assert block["cancel-in-progress"] == CANCEL_ONLY_PR
    assert block["group"] == EXPECTED_GROUP


@pytest.mark.parametrize("name", ["ci.yml", "codeql.yml"])
def test_no_security_workflow_lacks_concurrency(name: str) -> None:
    assert "concurrency" in _load(WORKFLOWS / name)


def test_dev_tools_and_actions_are_grouped_by_minor_and_patch() -> None:
    updates = _updates()
    pip = updates[("pip", "/")]["groups"]
    assert set(pip["dev-tools"]["patterns"]) == DEV_TOOLS
    # Exact-pinned, non-semver-safe tools: one group each, never in dev-tools.
    for tool in ISOLATED_TOOLS:
        assert pip[tool]["patterns"] == [tool]
    actions = updates[("github-actions", "/")]["groups"]
    assert actions["github-actions"]["patterns"] == ["*"]
    for group in (*pip.values(), *actions.values()):
        # Majors are excluded from groups, so they open separate PRs.
        assert set(group["update-types"]) == {"minor", "patch"}


def test_runtime_dependencies_stay_ungrouped() -> None:
    # The root pip entry is the only one that sees runtime dependencies; its
    # groups must name dev tools explicitly and never use a wildcard.
    patterns = {p for g in _updates()[("pip", "/")]["groups"].values() for p in g["patterns"]}
    assert not RUNTIME_DEPS & patterns
    assert "*" not in patterns


def test_docs_tools_are_pinned_exactly() -> None:
    lines = [
        line.strip()
        for line in (ROOT / "docs-tools" / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    names = {line.split("==")[0] for line in lines}
    assert {"mkdocs", "mkdocs-material", "pymdown-extensions"} <= names
    for line in lines:
        assert re.fullmatch(r"[A-Za-z0-9._-]+==\d+(\.\d+)*", line), line


def test_every_docs_build_installs_from_the_pinned_file() -> None:
    builders = 0
    for path in WORKFLOWS.glob("*.yml"):
        text = path.read_text()
        if "mkdocs build" not in text:
            continue
        builders += 1
        assert "pip install -r docs-tools/requirements.txt" in text, path.name
        for line in text.splitlines():
            if "pip install" in line:
                assert "-r docs-tools/requirements.txt" in line, (path.name, line)
    assert builders >= 1


def test_dependabot_updates_the_docs_pins() -> None:
    entry = _updates()[("pip", "/docs-tools")]
    assert entry["schedule"]["interval"] == "weekly"


def test_docs_pull_request_builds_but_never_deploys() -> None:
    wf = _load(WORKFLOWS / "docs.yml")
    # PyYAML parses the bare `on` key as boolean True.
    triggers = wf.get("on", wf.get(True))
    assert triggers["pull_request"]["paths"] == ["docs-tools/**", "mkdocs.yml", "docs/**"]
    # Workflow-level permissions stay read-only so PR runs cannot write pages.
    assert wf["permissions"] == {"contents": "read"}
    jobs = wf["jobs"]
    assert jobs["deploy"]["if"] == "github.event_name != 'pull_request'"
    assert jobs["deploy"]["permissions"]["pages"] == "write"
    assert jobs["deploy"]["permissions"]["id-token"] == "write"
    assert "permissions" not in jobs["build"]
    for step in jobs["build"]["steps"]:
        if "upload-pages-artifact" in step.get("uses", ""):
            assert step["if"] == "github.event_name != 'pull_request'"
