"""Docs must list the registered tools, prompts and resources, and the manifest must match config."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from fastmcp import Client

from cubrid_mcp_server import server

ROOT = Path(__file__).resolve().parent.parent
TOOLS_MD = (ROOT / "docs" / "TOOLS.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


async def test_tools_md_lists_every_tool_and_prompt_and_resource() -> None:
    async with Client(server.mcp) as client:
        tools = {tool.name for tool in await client.list_tools()}
        prompts = {prompt.name for prompt in await client.list_prompts()}
        resources = {str(r.uri) for r in await client.list_resources()}
        templates = {t.uriTemplate for t in await client.list_resource_templates()}

    # execute_write is registered only when write mode is on at import time; it is
    # documented regardless.
    tools.add("execute_write")
    for name in tools:
        assert f"#### `{name}(" in TOOLS_MD, f"tool {name} missing from docs/TOOLS.md"
    for name in prompts:
        assert f"| `{name}` |" in TOOLS_MD, f"prompt {name} missing from docs/TOOLS.md"
        assert f"| `{name}` |" in README, f"prompt {name} missing from README.md"
    for uri in resources | templates:
        assert f"`{uri}`" in TOOLS_MD, f"resource {uri} missing from docs/TOOLS.md"


def test_manifest_required_env_matches_config() -> None:
    manifest = json.loads((ROOT / ".mcpb" / "server.json").read_text(encoding="utf-8"))
    env = {e["name"]: e for e in manifest["packages"][0]["environmentVariables"]}
    for name in ("CUBRID_HOST", "CUBRID_USER", "CUBRID_PASSWORD", "CUBRID_DATABASE"):
        assert env[name]["isRequired"] is True
    for name in ("CUBRID_PORT", "CUBRID_MCP_READONLY", "CUBRID_MCP_WRITE", "CUBRID_MCP_AUDIT_LOG"):
        assert env[name]["isRequired"] is False
    assert re.search(r"\b11 read-only\b", manifest["description"])


def test_changelog_lint_rejects_duplicate_subsection_heading(tmp_path: Path) -> None:
    script = ROOT / "scripts" / "lint_changelog.py"
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "lint_changelog.py").write_text(script.read_text(encoding="utf-8"))
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n### CI\n- a\n\n### Fixed\n- b\n\n### CI\n- c\n\n"
        "## [1.0.0] - 2026-01-01\n\n### CI\n- d\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "lint_changelog.py")], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "Duplicate subsection heading '### CI' in [Unreleased]" in result.stderr
