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
    assert cfg.max_rows == 1000


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


def test_from_env_max_rows_override() -> None:
    cfg = Config.from_env(BASE_ENV | {"CUBRID_MCP_MAX_ROWS": "250"})
    assert cfg.max_rows == 250


def test_from_env_invalid_max_rows() -> None:
    with pytest.raises(ConfigError, match="CUBRID_MCP_MAX_ROWS"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_MAX_ROWS": "lots"})
    with pytest.raises(ConfigError, match="positive"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_MAX_ROWS": "0"})


def test_from_env_max_sql_length_default_and_override() -> None:
    assert Config.from_env(BASE_ENV).max_sql_length == 65536
    cfg = Config.from_env(BASE_ENV | {"CUBRID_MCP_MAX_SQL_LENGTH": "1024"})
    assert cfg.max_sql_length == 1024


def test_from_env_invalid_max_sql_length() -> None:
    with pytest.raises(ConfigError, match="CUBRID_MCP_MAX_SQL_LENGTH"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_MAX_SQL_LENGTH": "big"})
    with pytest.raises(ConfigError, match="positive"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_MAX_SQL_LENGTH": "0"})


def test_from_env_query_timeout_default_and_override() -> None:
    assert Config.from_env(BASE_ENV).query_timeout == 30.0
    cfg = Config.from_env(BASE_ENV | {"CUBRID_MCP_QUERY_TIMEOUT": "2.5"})
    assert cfg.query_timeout == 2.5


def test_from_env_invalid_query_timeout() -> None:
    with pytest.raises(ConfigError, match="CUBRID_MCP_QUERY_TIMEOUT"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_QUERY_TIMEOUT": "soon"})
    with pytest.raises(ConfigError, match="positive"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_QUERY_TIMEOUT": "0"})


def test_password_not_in_repr() -> None:
    cfg = Config.from_env(BASE_ENV)
    assert "secret" not in repr(cfg)
