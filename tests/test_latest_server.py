"""Weekly newest-stable CUBRID image check and per-cell image evidence (#417).

Covers scripts/latest_server.py offline: Docker is replaced by a fake, so the
equal-digest, newer-GA and unavailable/invalid upstream cases need no registry.
The workflow wiring is checked in tests/test_ci_scope.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "latest_server.py"

_spec = importlib.util.spec_from_file_location("_latest_server", SCRIPT)
assert _spec is not None and _spec.loader is not None
latest_server = importlib.util.module_from_spec(_spec)
sys.modules["_latest_server"] = latest_server
_spec.loader.exec_module(latest_server)

REF_A = "cubrid/cubrid@sha256:" + "a" * 64
REF_B = "cubrid/cubrid@sha256:" + "b" * 64
REL_1146 = (
    "CUBRID 11.4.6 (11.4.6.1963-0e7d3c1) (64bit release build for Linux) (Sep  7 2026 17:45:11)"
)
REL_1147 = "CUBRID 11.4.7 (11.4.7.2001-1a2b3c4) (64bit release build for Linux)"
REL_1150 = "CUBRID 11.5.0 (11.5.0.0100-abcdef0) (64bit release build for Linux)"
REL_1145 = "CUBRID 11.4.5 (11.4.5.1900-0123456) (64bit release build for Linux)"
REL_102 = (
    "CUBRID 10.2 (10.2.18.9024-01b54fa) (64bit release build for Linux) (May  9 2026 01:02:18)"
)


def fake_docker(
    monkeypatch: pytest.MonkeyPatch, images: dict[str, tuple[str, str]], pulls: set[str]
) -> list[tuple[str, ...]]:
    """Answer docker pull/inspect/run from ``images`` ({tag ref: (digest ref, rel)})."""
    calls: list[tuple[str, ...]] = []
    by_digest = {ref: rel for ref, rel in images.values()}

    def docker(*args: str) -> str:
        calls.append(args)
        if args[0] == "pull":
            return args[-1] if args[-1] in pulls else ""
        if args[:2] == ("image", "inspect"):
            return images.get(args[-1], ("", ""))[0]
        if args[0] == "run":
            return by_digest.get(args[4], "")
        raise AssertionError(args)

    monkeypatch.setattr(latest_server, "_docker", docker)
    return calls


# --- decision ---------------------------------------------------------------------


def test_equal_digest_starts_no_duplicate_database() -> None:
    decision = latest_server.decide(REF_A, REL_1146, REF_A, REL_1146)
    assert decision == {"status": "same-image", "canary": "false", "image": ""}


@pytest.mark.parametrize("rel", [REL_1150, REL_1147])
def test_newer_ga_runs_the_canary_on_the_immutable_ref(rel: str) -> None:
    decision = latest_server.decide(REF_B, rel, REF_A, REL_1146)
    assert decision == {"status": "newer", "canary": "true", "image": REF_B}


@pytest.mark.parametrize("rel", [REL_1145, REL_1146])
def test_other_digest_that_is_not_newer_runs_nothing(rel: str) -> None:
    decision = latest_server.decide(REF_B, rel, REF_A, REL_1146)
    assert decision == {"status": "not-newer", "canary": "false", "image": ""}


@pytest.mark.parametrize(
    "case",
    [
        ("", "", REF_A, REL_1146),  # latest pull failed
        (REF_A, REL_1146, "", ""),  # series pull failed
        ("cubrid/cubrid:latest", REL_1146, REF_A, REL_1146),  # a tag, not a digest
        ("other/image@sha256:" + "a" * 64, REL_1146, REF_A, REL_1146),
        (REF_A + "\nimage=x", REL_1146, REF_A, REL_1146),
        (REF_B, "bash: cubrid_rel: command not found", REF_A, REL_1146),
        (REF_B, REL_1150, REF_A, ""),
    ],
)
def test_unavailable_or_invalid_upstream_is_unverified(case: tuple[str, str, str, str]) -> None:
    decision = latest_server.decide(*case)
    assert decision == {"status": "unverified", "canary": "false", "image": ""}


def test_engine_versions_parse_for_every_supported_series() -> None:
    assert latest_server.version(REL_1146) == "11.4.6.1963"
    assert latest_server.version(REL_102) == "10.2.18.9024"
    assert latest_server.version("") == "unknown"


# --- report -----------------------------------------------------------------------


def test_a_passed_canary_is_the_only_passed_claim() -> None:
    code, line, annotation = latest_server.report("newer", REF_B, "success")
    assert (code, annotation) == (0, "")
    assert "passed" in line


@pytest.mark.parametrize("outcome", ["failure", "skipped", "cancelled", ""])
def test_report_never_claims_an_unrun_or_failed_canary(outcome: str) -> None:
    code, line, annotation = latest_server.report("newer", REF_B, outcome)
    assert code == 1
    assert "passed" not in line
    assert "NOT verified" in line
    assert annotation.startswith("::error::")


@pytest.mark.parametrize("status", ["unverified", ""])
def test_unverified_or_missing_status_is_never_success(status: str) -> None:
    # An empty status means the resolve step itself never produced outputs.
    code, line, annotation = latest_server.report(status, "", "")
    assert code == 0
    assert "UNVERIFIED" in line and "passed" not in line
    assert annotation.startswith("::warning::")


@pytest.mark.parametrize("status", ["same-image", "not-newer"])
def test_no_canary_needed(status: str) -> None:
    assert latest_server.report(status, "", "") == (0, "No advisory canary needed.", "")


# --- commands ---------------------------------------------------------------------


def test_resolve_same_digest_records_provenance_without_claiming_a_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    images = {"cubrid/cubrid:latest": (REF_A, REL_1146), "cubrid/cubrid:11.4": (REF_A, REL_1146)}
    calls = fake_docker(monkeypatch, images, set(images))
    output = tmp_path / "out"
    args = ["resolve", "--date", "2026-10-25T03:00Z", "--output", str(output)]
    assert latest_server.main(args) == 0
    assert output.read_text() == "status=same-image\ncanary=false\nimage=\n"
    # Each tag is pulled exactly once per run.
    assert [c for c in calls if c[0] == "pull"] == [
        ("pull", "-q", "cubrid/cubrid:latest"),
        ("pull", "-q", "cubrid/cubrid:11.4"),
    ]
    text = capsys.readouterr().out
    for evidence in (REF_A, "11.4.6.1963", "2026-10-25T03:00Z", "No extra database started"):
        assert evidence in text
    assert f"the newest-stable image is `{REF_A}`" in text
    assert "only if they show this same digest" in text
    assert "passed" not in text


def test_resolve_newer_ga_selects_the_canary_digest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    images = {"cubrid/cubrid:latest": (REF_B, REL_1150), "cubrid/cubrid:11.4": (REF_A, REL_1146)}
    fake_docker(monkeypatch, images, set(images))
    output = tmp_path / "out"
    assert latest_server.main(["resolve", "--output", str(output)]) == 0
    assert output.read_text() == f"status=newer\ncanary=true\nimage={REF_B}\n"
    text = capsys.readouterr().out
    assert "11.5.0.100" in text
    assert "never promoted automatically" in text


def test_resolve_failed_pull_is_unverified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    images = {"cubrid/cubrid:latest": (REF_B, REL_1150), "cubrid/cubrid:11.4": (REF_A, REL_1146)}
    fake_docker(monkeypatch, images, {"cubrid/cubrid:11.4"})  # latest cannot be pulled
    output = tmp_path / "out"
    assert latest_server.main(["resolve", "--output", str(output)]) == 0
    assert output.read_text() == "status=unverified\ncanary=false\nimage=\n"
    text = capsys.readouterr().out
    assert "UNVERIFIED" in text and "not resolved" in text


def test_missing_docker_is_unverified(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "")
    assert latest_server._docker("version") == ""
    assert latest_server.pull("latest") == ("", "")


def test_record_writes_the_cell_image_and_always_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_docker(monkeypatch, {"cubrid/cubrid:11.4": (REF_A, REL_1146)}, set())
    summary = tmp_path / "summary"
    assert latest_server.main(["record", "--tag", "11.4", "--summary", str(summary)]) == 0
    assert summary.read_text() == (
        f"CUBRID image: `cubrid/cubrid:11.4` -> `{REF_A}` (engine 11.4.6.1963)\n"
    )
    # An image that cannot be inspected is recorded as unresolved, never failing the cell.
    assert latest_server.main(["record", "--tag", "11.0", "--summary", str(summary)]) == 0
    assert summary.read_text().splitlines()[-1] == (
        "CUBRID image: `cubrid/cubrid:11.0` -> `unresolved` (engine unknown)"
    )


def test_report_appends_to_the_summary_and_fails_a_failed_canary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    summary = tmp_path / "summary"
    args = ["report", "--status", "newer", "--image", REF_B, "--outcome", "failure"]
    assert latest_server.main([*args, "--summary", str(summary)]) == 1
    assert "NOT verified" in summary.read_text()
    assert "::error::" not in summary.read_text()
    assert capsys.readouterr().out.startswith("::error::")
