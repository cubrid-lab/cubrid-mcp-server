"""THIRD_PARTY_LICENSES.md stays consistent with pyproject.toml (#218).

The inventory is a generated snapshot; this check makes drift visible instead of
silent: the documented direct-dependency ranges must equal pyproject.toml, every
declared dependency must appear (within its declared range, unless it is an exact
``==`` pin, which pyproject.toml already records), every row's category must be
what the generator assigns to its license, and every MPL or "Needs review" row
must be explained in the prose.
"""

from __future__ import annotations

import importlib.util
import re
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "THIRD_PARTY_LICENSES.md").read_text(encoding="utf-8")
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

_spec = importlib.util.spec_from_file_location(
    "_generate_third_party_licenses", ROOT / "scripts" / "generate_third_party_licenses.py"
)
assert _spec is not None and _spec.loader is not None
generator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generator)

SECTIONS = {
    "runtime": "## Runtime dependencies",
    "dev": "## Development / test dependencies: `.[dev]` additions",
}


def section(heading: str) -> str:
    start = DOC.index(heading)
    end = DOC.find("\n## ", start + 1)
    return DOC[start : len(DOC) if end == -1 else end]


def table(scope: str) -> dict[str, dict[str, str]]:
    rows = {}
    for line in section(SECTIONS[scope]).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 6 or cells[0] == "Name" or set(cells[0]) <= {"-"}:
            continue
        rows[canonicalize_name(cells[0])] = {
            "version": cells[1],
            "license": cells[2],
            "category": cells[3],
            "required_by": cells[5],
        }
    return rows


def requirements(scope: str) -> list[Requirement]:
    declared = (
        PROJECT["dependencies"] if scope == "runtime" else PROJECT["optional-dependencies"][scope]
    )
    return [Requirement(req) for req in declared]


def is_exact_pin(req: Requirement) -> bool:
    return any(s.operator in {"==", "==="} and "*" not in s.version for s in req.specifier)


def test_direct_dependency_table_matches_pyproject() -> None:
    documented = {}
    for line in section("## Direct runtime dependencies").splitlines():
        match = re.match(r"\| `([^`]+)` \| `([^`]+)` \| ([^|]+) \| ([^|]+) \|$", line.strip())
        if match:
            documented[canonicalize_name(match.group(1))] = match.groups()
    declared = {canonicalize_name(r.name): r for r in requirements("runtime")}
    assert set(documented) == set(declared)
    runtime = table("runtime")
    for name, (_, allowed, license_text, observed) in documented.items():
        assert SpecifierSet(allowed) == declared[name].specifier, (
            f"{name}: documented {allowed}, pyproject.toml {declared[name].specifier}"
        )
        assert observed.strip() == runtime[name]["version"], name
        assert license_text.strip() == runtime[name]["license"], name


@pytest.mark.parametrize("scope", sorted(SECTIONS))
def test_every_declared_dependency_is_inventoried_within_its_range(scope: str) -> None:
    # The dev table lists only additions to the runtime tree.
    rows = {**table("runtime"), **table(scope)}
    for req in requirements(scope):
        name = canonicalize_name(req.name)
        assert name in rows, f"{name} from {scope} is missing from THIRD_PARTY_LICENSES.md"
        if is_exact_pin(req):
            continue  # Exact pins are authoritative in pyproject.toml; bumps need no regen.
        version = rows[name]["version"]
        assert req.specifier.contains(version, prereleases=True), (
            f"{name} {version} is outside {req.specifier} declared for {scope}"
        )


def test_direct_runtime_dependencies_are_attributed_to_the_project() -> None:
    runtime = table("runtime")
    for req in requirements("runtime"):
        assert "cubrid-mcp-server" in runtime[canonicalize_name(req.name)]["required_by"]
    unattributed = [name for name, row in runtime.items() if row["required_by"] == "-"]
    assert not unattributed, unattributed


@pytest.mark.parametrize("scope", sorted(SECTIONS))
def test_every_category_matches_the_generator(scope: str) -> None:
    for name, row in table(scope).items():
        assert generator.category(row["license"]) == row["category"], (name, row)


def test_every_runtime_dependency_is_permissive() -> None:
    # The prose states it; keep it true or make the prose change with the table.
    assert {row["category"] for row in table("runtime").values()} == {"Permissive"}


def test_every_review_and_mpl_row_is_explained() -> None:
    categories = section("## License categories")
    reviewed = categories[categories.index("### Reviewed entries") :]
    for scope in SECTIONS:
        for name, row in table(scope).items():
            if row["category"] == "Needs review":
                assert re.search(rf"\*\*{re.escape(name)}\*\*", reviewed, re.I), name
            elif row["category"].startswith("Weak copyleft"):
                assert f"`{name}`" in categories, f"MPL package {name} not named in the prose"
            else:
                assert row["category"] == "Permissive", (name, row)
    assert table("dev")["docutils"]["category"] == "Needs review"


def test_no_blanket_permissive_claim() -> None:
    for stale in ("No dependency is copyleft", "All listed dependencies are distributed under"):
        assert stale not in DOC


def test_generation_inputs_are_recorded() -> None:
    record = section("## How the inventories were generated")
    assert re.search(r"commit `[0-9a-f]{40}`", record)
    assert re.search(r"CPython 3\.\d+\.\d+ on Linux", record)
    assert "scripts/generate_third_party_licenses.py" in record
    assert "--exclude cubrid-mcp-server --required-by" in record
    assert '".[dev]"' in record
