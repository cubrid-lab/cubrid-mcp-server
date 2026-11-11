"""Wheel and sdist contents stay consistent with NOTICE and the license inventory."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _artifact_names(path: Path) -> list[str]:
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path) as archive:
            return archive.getnames()
    with zipfile.ZipFile(path) as archive:
        return archive.namelist()


def _relatives(names: list[str]) -> set[str]:
    """Paths relative to the sdist top-level directory, or wheel paths as-is."""
    relatives: set[str] = set()
    for name in names:
        parts = Path(name).parts
        if not parts:
            continue
        if name.endswith(".tar.gz") or name.endswith(".whl"):
            continue
        if parts[0].startswith("cubrid_mcp_server-") and not parts[0].endswith(".dist-info"):
            relatives.add("/".join(parts[1:]) if len(parts) > 1 else "")
        else:
            relatives.add(name)
    return relatives


@pytest.fixture(scope="module")
def dist_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    pytest.importorskip("build")
    out = tmp_path_factory.mktemp("dist")
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--wheel", "-o", str(out), str(ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    return out


def _one(dist_dir: Path, suffix: str) -> Path:
    matches = [p for p in dist_dir.iterdir() if p.name.endswith(suffix)]
    assert len(matches) == 1, list(dist_dir.iterdir())
    return matches[0]


def test_sdist_ships_the_license_inventory_and_omits_partial_tests(dist_dir: Path) -> None:
    names = _relatives(_artifact_names(_one(dist_dir, ".tar.gz")))
    assert "LICENSE" in names
    assert "NOTICE" in names
    assert "THIRD_PARTY_LICENSES.md" in names
    test_paths = [n for n in names if n == "tests" or n.startswith("tests/")]
    assert test_paths == []


def test_wheel_ships_the_license_inventory(dist_dir: Path) -> None:
    names = _artifact_names(_one(dist_dir, ".whl"))
    licenses = [
        n for n in names if n.startswith("cubrid_mcp_server-") and ".dist-info/licenses/" in n
    ]
    basenames = {Path(n).name for n in licenses}
    assert basenames == {"LICENSE", "NOTICE", "THIRD_PARTY_LICENSES.md"}
    assert not any("/tests/" in n or n.startswith("tests/") for n in names)
