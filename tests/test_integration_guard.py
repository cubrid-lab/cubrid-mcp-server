"""Offline tests for the fail-closed integration guard in tests/conftest.py (#403)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CONFTEST = Path(__file__).with_name("conftest.py")

PASSING = "import pytest\n\n@pytest.mark.integration\ndef test_live():\n    pass\n"
SKIPPING = (
    "import pytest\n\n@pytest.mark.integration\n"
    "@pytest.mark.skipif(True, reason='CUBRID env vars not set')\n"
    "def test_live():\n    pass\n"
)
PASS_AND_UNREACHABLE_SKIP = (
    PASSING
    + "\n@pytest.mark.integration\ndef test_other():\n    pytest.skip('server unreachable')\n"
)
PASS_AND_OTHER_SKIP = (
    PASSING + "\n@pytest.mark.integration\ndef test_other():\n    pytest.skip('old version')\n"
)
UNMARKED = "def test_plain():\n    pass\n"


def _run(tmp_path: Path, source: str, *args: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / "conftest.py").write_text(CONFTEST.read_text())
    (tmp_path / "test_sample.py").write_text(source)
    (tmp_path / "pytest.ini").write_text("[pytest]\nmarkers =\n    integration: live\n")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("source", "args", "status", "message"),
    [
        (PASSING, ("-m", "integration"), 0, ""),
        (SKIPPING, ("-m", "integration"), 1, "no integration test passed"),
        (UNMARKED, ("-m", "integration"), 5, ""),
        (PASSING, ("-m", "integration and not integration"), 5, ""),
        (PASS_AND_UNREACHABLE_SKIP, ("-m", "integration"), 1, "lack of a CUBRID server"),
        (PASS_AND_OTHER_SKIP, ("-m", "integration"), 0, ""),
        (SKIPPING, ("-m", "not integration"), 5, ""),
        (SKIPPING, (), 0, ""),
    ],
)
def test_integration_guard(
    tmp_path: Path, source: str, args: tuple[str, ...], status: int, message: str
) -> None:
    result = _run(tmp_path, source, *args)
    assert result.returncode == status, result.stdout + result.stderr
    assert message in result.stdout
    if status == 1:
        assert "INTEGRATION LANE FAILED CLOSED" in result.stdout
