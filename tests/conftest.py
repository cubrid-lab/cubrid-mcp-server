"""Fail the live lane closed (#403).

``pytest -m integration`` must prove something: it fails when no integration test
passed (none collected, all deselected or all skipped) or when a test was skipped
because the CUBRID server could not be reached or configured. Runs that do not
select the integration marker, such as ``make test``, are not affected.
"""

from __future__ import annotations

import pytest

SERVER_SKIP_MARKERS = ("CUBRID env vars not set", "unreachable")


def _selects_integration(markexpr: str) -> bool:
    return "integration" in markexpr and "not integration" not in markexpr


class _IntegrationGuard:
    def __init__(self) -> None:
        self.passed = 0
        self.server_skips: list[str] = []

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if "integration" not in report.keywords:
            return
        if report.passed and report.when == "call":
            self.passed += 1
        elif report.skipped and isinstance(report.longrepr, tuple):
            reason = str(report.longrepr[2])
            if any(marker in reason for marker in SERVER_SKIP_MARKERS):
                self.server_skips.append(f"{report.nodeid}: {reason}")

    def problems(self) -> list[str]:
        found = []
        if not self.passed:
            found.append("no integration test passed")
        if self.server_skips:
            found.append("integration tests skipped for lack of a CUBRID server:")
            found.extend(f"  {skip}" for skip in self.server_skips)
        return found

    def pytest_terminal_summary(self, terminalreporter: pytest.TerminalReporter) -> None:
        for line in self.problems():
            terminalreporter.write_line(f"INTEGRATION LANE FAILED CLOSED: {line}", red=True)

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        if self.problems() and exitstatus == pytest.ExitCode.OK:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_configure(config: pytest.Config) -> None:
    if _selects_integration(str(config.getoption("markexpr") or "")):
        config.pluginmanager.register(_IntegrationGuard(), "integration-guard")
