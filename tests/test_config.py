import pytest

from cubrid_mcp_server.config import Config, ConfigError


BASE_ENV = {
    "CUBRID_HOST": "localhost",
    "CUBRID_USER": "mcp",
    "CUBRID_PASSWORD": "secret",
    "CUBRID_DATABASE": "demodb",
}


def test_from_env_defaults() -> None:
    cfg = Config.from_env(BASE_ENV)
    assert cfg.host == "localhost"
    assert cfg.port == 33000
    assert cfg.user == "mcp"
    assert cfg.database == "demodb"
    assert cfg.readonly is True
    assert cfg.max_chars == 4000


def test_from_env_overrides() -> None:
    cfg = Config.from_env(
        BASE_ENV
        | {
            "CUBRID_PORT": "30000",
            "CUBRID_MCP_READONLY": "0",
            "CUBRID_MCP_MAX_CHARS": "8000",
        }
    )
    assert cfg.port == 30000
    assert cfg.readonly is False
    assert cfg.max_chars == 8000


@pytest.mark.parametrize("missing_key", list(BASE_ENV.keys()))
def test_from_env_missing_required(missing_key: str) -> None:
    env = {k: v for k, v in BASE_ENV.items() if k != missing_key}
    with pytest.raises(ConfigError, match=missing_key):
        Config.from_env(env)


def test_from_env_invalid_port() -> None:
    with pytest.raises(ConfigError, match="CUBRID_PORT"):
        Config.from_env(BASE_ENV | {"CUBRID_PORT": "not-a-port"})


def test_from_env_invalid_max_chars() -> None:
    with pytest.raises(ConfigError, match="CUBRID_MCP_MAX_CHARS"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_MAX_CHARS": "zero"})
    with pytest.raises(ConfigError, match="positive"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_MAX_CHARS": "0"})


def test_from_env_invalid_readonly() -> None:
    with pytest.raises(ConfigError, match="boolean"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_READONLY": "maybe"})
