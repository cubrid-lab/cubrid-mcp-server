"""Docs must list the registered tools, prompts and resources, and the manifest must match config."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
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


def test_troubleshooting_names_claude_desktop_log_files() -> None:
    """Chat-client users can find the server's stderr, the only place the cause is (#483)."""
    entries = {
        "docs/TROUBLESHOOTING.md": "## No logs anywhere",
        "docs/ko/TROUBLESHOOTING.md": "## 로그가 안 보임",
    }
    for page, heading in entries.items():
        text = _read(*page.split("/"))
        assert f'<a id="no-logs-anywhere"></a>\n\n{heading}' in text, page
        entry = _section(text, heading)
        for expected in (
            "`mcp-server-cubrid.log`",
            "`~/Library/Logs/Claude`",
            "`%APPDATA%\\Claude\\logs`",
            "`2>server.log`",
            "SQL",
        ):
            assert expected in entry, (page, expected)
    failure_sections = {
        "docs/quickstart.md": "## If something fails",
        "docs/ko/quickstart.md": "## 문제가 생기면",
    }
    for page, heading in failure_sections.items():
        section = _section(_read(*page.split("/")), heading)
        assert "](TROUBLESHOOTING.md#no-logs-anywhere)" in section, page


WINDOWS_CLAUDE_CONFIG = "`%APPDATA%\\Claude\\claude_desktop_config.json`"
MACOS_CLAUDE_CONFIG = "`~/Library/Application Support/Claude/claude_desktop_config.json`"


def test_client_setup_docs_cover_windows_and_macos() -> None:
    """Windows users get the config location, venv layout and path lookup too (#480)."""
    claude_sections = {
        "README.md": ("README.md", "### Claude Desktop"),
        "docs/README.ko.md": ("docs/README.ko.md", "### Claude Desktop"),
        "docs/quickstart.md": (
            "docs/quickstart.md",
            "## Optional: use the same server from a chat client",
        ),
        "docs/ko/quickstart.md": (
            "docs/ko/quickstart.md",
            "## 선택: 채팅 클라이언트에서 같은 서버 사용",
        ),
    }
    for name, (page, heading) in claude_sections.items():
        section = _section(_read(*page.split("/")), heading)
        assert MACOS_CLAUDE_CONFIG in section, name
        assert WINDOWS_CLAUDE_CONFIG in section, name
    for page in ("docs/TROUBLESHOOTING.md", "docs/ko/TROUBLESHOOTING.md"):
        text = _read(*page.split("/"))
        line = next(row for row in text.splitlines() if "claude_desktop_config.json" in row)
        assert MACOS_CLAUDE_CONFIG in line and WINDOWS_CLAUDE_CONFIG in line, page
    install_sections = {
        "docs/quickstart.md": "## Step 2: Install the server in a virtual environment",
        "docs/ko/quickstart.md": "## 2단계: 가상 환경에 서버 설치",
    }
    for page, heading in install_sections.items():
        section = _section(_read(*page.split("/")), heading)
        for expected in (
            "which cubrid-mcp-server",
            "`.venv\\Scripts\\activate`",
            "`.\\.venv\\Scripts\\Activate.ps1`",
            "`where cubrid-mcp-server`",
            "`(Get-Command cubrid-mcp-server).Source`",
        ):
            assert expected in section, (page, expected)
    for page in ("README.md", "docs/README.ko.md"):
        assert "`.venv\\Scripts\\activate`" in _read(*page.split("/")), page


def test_quickstart_windows_command_example_is_valid_json() -> None:
    """The escaped Windows path example parses to a real .venv\\Scripts executable path (#480)."""
    for page, heading in (
        ("docs/quickstart.md", "## Optional: use the same server from a chat client"),
        ("docs/ko/quickstart.md", "## 선택: 채팅 클라이언트에서 같은 서버 사용"),
    ):
        section = _section(_read(*page.split("/")), heading)
        match = re.search(r'`("command": "[^`]*Scripts[^`]*")`', section)
        assert match is not None, page
        command = json.loads("{" + match.group(1) + "}")["command"]
        assert (
            command == "C:\\Users\\you\\cubrid-quickstart\\.venv\\Scripts\\cubrid-mcp-server.exe"
        ), page

def _extract_json_fences(text: str) -> list[str]:
    """Extract raw contents of top-level fenced json blocks, tracking enclosing fence boundaries."""
    blocks: list[str] = []
    current: list[str] = []
    fence_char = ""
    fence_len = 0
    in_json = False

    for line in text.splitlines():
        stripped = line.lstrip(" \t")
        if fence_len == 0:
            match = re.match(r"^(`{3,}|~{3,})(.*)$", stripped)
            if match:
                marker, info = match.groups()
                fence_char = marker[0]
                fence_len = len(marker)
                lang = info.strip().split()[0].lower() if info.strip() else ""
                in_json = lang == "json"
                current = []
        else:
            close_match = re.match(rf"^{re.escape(fence_char)}{{{fence_len},}}[ \t]*$", stripped)
            if close_match:
                if in_json:
                    blocks.append("\n".join(current))
                fence_char = ""
                fence_len = 0
                in_json = False
                current = []
            elif in_json:
                current.append(line)

    return blocks


def _validate_readme_mcp_client_section(page: str, heading: str, section: str) -> None:
    """Validate that fenced json blocks in one README client section define mcpServers.cubrid."""
    blocks = _extract_json_fences(section)
    assert blocks, f"{page} {heading} has no fenced json config block"
    for index, block in enumerate(blocks, start=1):
        try:
            payload = json.loads(block)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"{page} {heading} json block #{index} is invalid JSON: {exc}"
            ) from exc
        assert isinstance(payload, dict), f"{page} {heading} block #{index} must be a JSON object"
        servers = payload.get("mcpServers")
        assert isinstance(servers, dict), f"{page} {heading} block #{index} missing mcpServers object"
        cubrid = servers.get("cubrid")
        assert isinstance(cubrid, dict), (
            f"{page} {heading} block #{index} missing mcpServers.cubrid object"
        )
        command = cubrid.get("command")
        assert isinstance(command, str) and command.strip(), (
            f"{page} {heading} block #{index} missing non-empty command"
        )
        env = cubrid.get("env")
        assert isinstance(env, dict), f"{page} {heading} block #{index} missing env object"


def test_readme_mcp_client_json_snippets_are_valid() -> None:
    """Every MCP client setup snippet in English and Korean READMEs must parse offline (#580)."""
    client_headings = ("### Claude Desktop", "### Claude Code", "### Cursor")
    for page in ("README.md", "docs/README.ko.md"):
        text = _read(*page.split("/"))
        for heading in client_headings:
            section = _section(text, heading)
            _validate_readme_mcp_client_section(page, heading, section)

    unrelated_doc = (
        "## Other Section\n\n"
        '```json\n{"unrelated":}\n```\n\n'
        "### Claude Desktop\n\n"
        '```json\n{"mcpServers": {"cubrid": {"command": "uvx", "env": {"CUBRID_HOST": "localhost"}}}}\n```\n'
    )
    _validate_readme_mcp_client_section(
        "README.md", "### Claude Desktop", _section(unrelated_doc, "### Claude Desktop")
    )

    bad_syntax = '```json\n{"mcpServers": {"cubrid": {"command": "uvx",}}}\n```\n'
    try:
        _validate_readme_mcp_client_section("README.md", "### Claude Desktop", bad_syntax)
    except AssertionError:
        pass
    else:
        raise AssertionError("Expected malformed JSON client snippet to fail validation")

    missing_env = '```json\n{"mcpServers": {"cubrid": {"command": "uvx"}}}\n```\n'
    try:
        _validate_readme_mcp_client_section("README.md", "### Claude Desktop", missing_env)
    except AssertionError:
        pass
    else:
        raise AssertionError("Expected client snippet missing env to fail validation")


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
        "CUBRID_MCP_CONNECT_TIMEOUT": cfg.connect_timeout,
        "CUBRID_MCP_MAX_ROW_COUNT_TABLES": cfg.max_row_count_tables,
        "CUBRID_MCP_MAX_INLINE_BINARY_BYTES": cfg.max_inline_binary_bytes,
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


README_TABLE_MARKERS = {
    "README.md": "Optional settings:",
    "docs/README.ko.md": "선택 설정:",
}


def _table_section(page: str, marker: str) -> str:
    """Slice one README settings table from ``marker`` to the next heading."""
    text = _read(page)
    start = text.index(marker)
    rest = text[start + len(marker) :]
    stop = re.search(r"^#{1,6} ", rest, re.MULTILINE)
    return rest[: stop.start()] if stop else rest


def _table_rows(page: str, marker: str) -> list[tuple[str, str]]:
    """Every ``| `CUBRID_MCP_...` | `default` |`` row of one README settings table."""
    return re.findall(
        r"^\|\s*`(CUBRID_MCP_[A-Z0-9_]+)`\s*\|\s*`([^`]*)`\s*\|",
        _table_section(page, marker),
        re.MULTILINE,
    )


def _config_defaults() -> dict[str, object]:
    """Config defaults from a bare environment, the values the README tables restate."""
    cfg = ConnectionRegistry.from_env(
        {
            "CUBRID_HOST": "h",
            "CUBRID_USER": "u",
            "CUBRID_PASSWORD": "p",
            "CUBRID_DATABASE": "d",
        }
    ).config_for(None)
    return {
        "CUBRID_MCP_READONLY": cfg.readonly,
        "CUBRID_MCP_WRITE": cfg.write_enabled,
        "CUBRID_MCP_AUDIT_LOG": cfg.audit_log,
        "CUBRID_MCP_MAX_ROWS": cfg.max_rows,
        "CUBRID_MCP_MAX_CHARS": cfg.max_chars,
        "CUBRID_MCP_MAX_SQL_LENGTH": cfg.max_sql_length,
        "CUBRID_MCP_QUERY_TIMEOUT": cfg.query_timeout,
        "CUBRID_MCP_CONNECT_TIMEOUT": cfg.connect_timeout,
        "CUBRID_MCP_MAX_ROW_COUNT_TABLES": cfg.max_row_count_tables,
        "CUBRID_MCP_MAX_INLINE_BINARY_BYTES": cfg.max_inline_binary_bytes,
    }


def test_readme_optional_settings_match_config_defaults() -> None:
    expected = _config_defaults()
    for page, marker in README_TABLE_MARKERS.items():
        rows = _table_rows(page, marker)
        counts = Counter(name for name, _ in rows)
        defaults = dict(rows)
        for name, value in expected.items():
            assert counts[name] == 1, (
                f"{page}: {name} must appear exactly once in the optional-settings table, "
                f"found {counts[name]}"
            )
            raw = defaults[name]
            parsed = _parse_bool(raw) if isinstance(value, bool) else type(value)(raw)
            assert parsed == value, (
                f"{page}: {name} default {raw!r} does not match the config default {value!r}"
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


def test_readme_quick_start_requirements_match_package_and_server() -> None:
    """The Quick Start requirements state the supported Python and CUBRID versions (#485)."""
    python_min = re.search(
        r'^requires-python = ">=(\d+\.\d+)"', _read("pyproject.toml"), re.MULTILINE
    )
    assert python_min is not None
    cubrid_range = re.search(
        r"targets CUBRID SQL \((\d+\.\d+)–(\d+\.\d+)\)", server.mcp.instructions or ""
    )
    assert cubrid_range is not None
    low, high = cubrid_range.groups()
    sections = {
        "README.md": (
            _section(_read("README.md"), "### Requirements"),
            "or later",
            "docs/quickstart.md",
        ),
        "docs/README.ko.md": (
            _section(_read("docs", "README.ko.md"), "### 요구 사항"),
            "이상",
            "ko/quickstart.md",
        ),
    }
    for page, (section, at_least, quickstart) in sections.items():
        assert f"Python {python_min.group(1)} {at_least}" in section, page
        assert f"CUBRID {low}–{high}" in section, page
        assert "33000" in section, page
        assert "`uvx`" in section and "`pipx run`" in section, page
        assert f"]({quickstart}#step-1-start-a-disposable-cubrid-lab)" in section, page
    english_step1 = _read("docs", "quickstart.md")
    assert re.search(r"^## Step 1: Start a disposable CUBRID lab$", english_step1, re.MULTILINE)
    assert '<a id="step-1-start-a-disposable-cubrid-lab"></a>' in _read(
        "docs", "ko", "quickstart.md"
    )
