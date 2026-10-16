"""The development-documentation notice on every site page (#355).

``docs/overrides/partials/channel.html`` labels the site as built from the
``main`` branch and names the commit when the build records one. These tests
render the partial with Jinja2 (installed with MkDocs; skipped without it) and
check that the label never depends on a version, a manifest or ``server.json``.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
PARTIAL = ROOT / "docs" / "overrides" / "partials" / "channel.html"
REPO = "https://github.com/cubrid-lab/cubrid-mcp-server"
SHA = "c0f900b76fe72523e51e5ae4e84fe197324284f8"


def _render(revision: str | None, url: str = "quickstart/") -> str:
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(PARTIAL.parent.parent)), autoescape=True
    )
    template = env.get_template("partials/channel.html")
    config = SimpleNamespace(extra={"source_revision": revision})
    return " ".join(template.render(config=config, page=SimpleNamespace(url=url)).split())


def test_names_the_commit_when_the_build_records_one() -> None:
    html = _render(SHA)
    assert "Development documentation:" in html
    assert f'href="{REPO}/commit/{SHA}"' in html
    assert f"<code>{SHA[:7]}</code>" in html
    assert "recorded no commit" not in html


@pytest.mark.parametrize("revision", ["", "  ", None])
def test_says_no_commit_was_recorded_for_a_local_build(revision: str | None) -> None:
    html = _render(revision)
    assert "(this build recorded no commit)" in html
    assert "/commit/" not in html


@pytest.mark.parametrize("url", ["ko/quickstart/", "README.ko/"])
def test_korean_pages_get_the_korean_notice(url: str) -> None:
    html = _render(SHA, url=url)
    assert "개발 문서:" in html
    assert f"<code>{SHA[:7]}</code>" in html
    assert "Development documentation" not in html


def test_points_to_the_release_list_and_never_claims_stable() -> None:
    for html in (_render(SHA), _render(""), _render(SHA, url="ko/")):
        assert f'href="{REPO}/releases"' in html
        assert not re.search(r"\b(stable|latest)\b", html, re.IGNORECASE)


def test_the_label_does_not_come_from_a_version_or_manifest() -> None:
    # Only the template logic matters, not the prose: no Jinja expression may
    # read a version, a tag, a release, the manifest or server.json.
    source = PARTIAL.read_text(encoding="utf-8")
    logic = " ".join(re.findall(r"\{[{%](.*?)[%}]\}", source, re.DOTALL)).lower()
    assert "source_revision" in logic
    for word in ("version", "tag", "release", "manifest", "server.json", "mcpb"):
        assert word not in logic


def test_mkdocs_reads_the_revision_from_github_sha() -> None:
    text = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert re.search(r'^  source_revision: !ENV \[GITHUB_SHA, ""\]$', text, re.MULTILINE)
    assert re.search(r"^  custom_dir: docs/overrides$", text, re.MULTILINE)
    assert re.search(r"^exclude_docs: \|\n  overrides/$", text, re.MULTILINE)
