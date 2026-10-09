"""Docs must list the registered tools, prompts and resources, and the manifest must match config."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from fastmcp import Client

from cubrid_mcp_server import server
from cubrid_mcp_server.config import ConnectionRegistry, _parse_bool

ROOT = Path(__file__).resolve().parent.parent
CONFIG_SRC = (ROOT / "cubrid_mcp_server" / "config.py").read_text(encoding="utf-8")


def _read(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """Slice ``text`` from ``heading`` to the next heading of the same or higher level."""
    match = re.search(rf"^({re.escape(heading)})\s*$", text, re.MULTILINE)
    if match is None:
        match = re.search(rf"^({re.escape(heading)})\b.*$", text, re.MULTILINE)
    assert match is not None, f"heading {heading!r} not found"
    level = len(heading) - len(heading.lstrip("#"))
    rest = text[match.end() :]
    nxt = re.search(rf"^#{{1,{level}}} ", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


TOOLS_MD = _read("docs", "TOOLS.md")
TOOLS_KO = _read("docs", "ko", "TOOLS.md")
PROMPT_SECTIONS = {
    "README.md": _section(_read("README.md"), "## Prompts"),
    "docs/TOOLS.md": _section(TOOLS_MD, "## Prompts"),
    "docs/README.ko.md": _section(_read("docs", "README.ko.md"), "### 프롬프트"),
    "docs/ko/TOOLS.md": _section(TOOLS_KO, "## 프롬프트"),
}
RESOURCE_PAGES = {"docs/TOOLS.md": TOOLS_MD, "docs/ko/TOOLS.md": TOOLS_KO}


async def test_tools_md_lists_every_tool_and_prompt_and_resource() -> None:
    async with Client(server.mcp) as client:
        tools = {tool.name for tool in await client.list_tools()}
        prompts = {prompt.name for prompt in await client.list_prompts()}
        resources = {str(r.uri): r.mimeType for r in await client.list_resources()}
        templates = {t.uriTemplate: t.mimeType for t in await client.list_resource_templates()}

    # execute_write is registered only when write mode is on at import time; it is
    # documented regardless.
    tools.add("execute_write")
    for name in tools:
        assert f"#### `{name}(" in TOOLS_MD, f"tool {name} missing from docs/TOOLS.md"
    for page, section in PROMPT_SECTIONS.items():
        for name in prompts:
            assert f"| `{name}` |" in section, f"prompt {name} missing from {page} Prompts section"
    for uri, mime in {**resources, **templates}.items():
        assert mime, f"resource {uri} has no MIME type"
        for page, text in RESOURCE_PAGES.items():
            rows = [line for line in text.splitlines() if f"| `{uri}` |" in line]
            assert rows, f"resource {uri} missing from {page}"
            assert f"`{mime}`" in rows[0], f"resource {uri} in {page} must be {mime}"


async def test_manifest_matches_config() -> None:
    manifest = json.loads((ROOT / ".mcpb" / "server.json").read_text(encoding="utf-8"))
    env = {e["name"]: e for e in manifest["packages"][0]["environmentVariables"]}
    required = {"CUBRID_HOST", "CUBRID_USER", "CUBRID_PASSWORD", "CUBRID_DATABASE"}
    for name, entry in env.items():
        # config.py builds keys as f"{prefix}<SUFFIX>" (prefix CUBRID_ or CUBRID_MCP_).
        suffix = name.removeprefix("CUBRID_MCP_").removeprefix("CUBRID_")
        assert f'}}{suffix}"' in CONFIG_SRC or f'"{name}"' in CONFIG_SRC, (
            f"manifest env {name} is not read by config.py"
        )
        assert entry["isRequired"] is (name in required)

    cfg = ConnectionRegistry.from_env(
        {
            "CUBRID_HOST": "h",
            "CUBRID_USER": "u",
            "CUBRID_PASSWORD": "p",
            "CUBRID_DATABASE": "d",
        }
    ).config_for(None)
    expected = {
        "CUBRID_PORT": cfg.port,
        "CUBRID_MCP_READONLY": cfg.readonly,
        "CUBRID_MCP_WRITE": cfg.write_enabled,
        "CUBRID_MCP_AUDIT_LOG": cfg.audit_log,
        "CUBRID_MCP_MAX_ROWS": cfg.max_rows,
        "CUBRID_MCP_MAX_CHARS": cfg.max_chars,
        "CUBRID_MCP_MAX_SQL_LENGTH": cfg.max_sql_length,
        "CUBRID_MCP_QUERY_TIMEOUT": cfg.query_timeout,
    }
    for name, value in expected.items():
        assert name in env, f"{name} missing from manifest"
        default = env[name]["default"]
        parsed = _parse_bool(default) if isinstance(value, bool) else type(value)(default)
        assert parsed == value, f"{name} default {default!r} != config default {value!r}"
    assert "CUBRID_CONNECTIONS" in env

    async with Client(server.mcp) as client:
        tools = {tool.name for tool in await client.list_tools()}
    read_only = len(tools - {"execute_write"})
    assert re.search(rf"\b{read_only} read-only\b", manifest["description"]), (
        f"manifest description must state {read_only} read-only tools"
    )


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
