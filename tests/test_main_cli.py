"""CLI --help / --version before configuration (#487)."""

from __future__ import annotations

import pytest

from cubrid_mcp_server import __version__, server


def test_help_flag_prints_usage_on_stderr_and_skips_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    called: list[str] = []

    def _boom(cls: type, env: object = None) -> object:
        called.append("from_env")
        raise AssertionError("config must not load for --help")

    monkeypatch.setattr(server.AppContext, "from_env", classmethod(_boom))
    monkeypatch.setattr(server.mcp, "run", lambda: called.append("run"))

    with pytest.raises(SystemExit) as excinfo:
        server.main(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "usage: cubrid-mcp-server" in captured.err
    assert "CUBRID_HOST" in captured.err
    assert "CUBRID_DATABASE" in captured.err
    assert called == []


def test_help_short_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        server.main(["-h"])
    assert excinfo.value.code == 0
    assert "usage: cubrid-mcp-server" in capsys.readouterr().err


def test_version_flag_prints_package_version_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    called: list[str] = []
    monkeypatch.setattr(
        server.AppContext,
        "from_env",
        classmethod(lambda cls, env=None: called.append("from_env")),
    )
    monkeypatch.setattr(server.mcp, "run", lambda: called.append("run"))
    with pytest.raises(SystemExit) as excinfo:
        server.main(["--version"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == f"cubrid-mcp-server {__version__}"
    assert called == []


def test_handle_cli_flags_returns_false_without_flags() -> None:
    assert server.handle_cli_flags([]) is False


def test_unknown_argument_fails_clearly(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        server.main(["--bogus"])
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "unrecognized arguments" in err or "unrecognized" in err.lower()


def test_no_args_still_reports_config_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        server.AppContext,
        "from_env",
        classmethod(
            lambda cls, env=None: (_ for _ in ()).throw(server.ConfigError("missing CUBRID_HOST"))
        ),
    )
    with pytest.raises(SystemExit) as excinfo:
        server.main([])
    assert excinfo.value.code == 1
    assert "configuration error: missing CUBRID_HOST" in capsys.readouterr().err
