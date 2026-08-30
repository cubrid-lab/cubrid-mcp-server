import pytest

from cubrid_mcp_server.config import Config, ConfigError, ConnectionRegistry


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


def test_registry_default_only_when_no_connections() -> None:
    registry = ConnectionRegistry.from_env(BASE_ENV)
    assert registry.names == ["default"]
    assert registry.config_for().database == "demodb"
    # None/empty selector resolves to the default connection.
    assert registry.config_for(None) is registry.config_for()
    assert registry.config_for("   ") is registry.config_for()


def test_registry_empty_connections_behaves_like_unset() -> None:
    registry = ConnectionRegistry.from_env(BASE_ENV | {"CUBRID_CONNECTIONS": "  "})
    assert registry.names == ["default"]


def test_registry_missing_default_vars_still_fails() -> None:
    env = {k: v for k, v in BASE_ENV.items() if k != "CUBRID_HOST"}
    with pytest.raises(ConfigError, match="CUBRID_HOST"):
        ConnectionRegistry.from_env(env)


def test_registry_parses_named_connection() -> None:
    env = BASE_ENV | {
        "CUBRID_CONNECTIONS": "reporting",
        "CUBRID_REPORTING_HOST": "reporting-db",
        "CUBRID_REPORTING_USER": "ru",
        "CUBRID_REPORTING_PASSWORD": "rp",
        "CUBRID_REPORTING_DATABASE": "reports",
        "CUBRID_REPORTING_MCP_MAX_ROWS": "500",
    }
    registry = ConnectionRegistry.from_env(env)
    assert registry.names == ["default", "reporting"]
    reporting = registry.config_for("reporting")
    assert reporting.host == "reporting-db"
    assert reporting.database == "reports"
    assert reporting.max_rows == 500
    # The default connection is unaffected by named-connection vars.
    assert registry.config_for().host == "localhost"


def test_registry_named_selection_is_case_insensitive() -> None:
    env = BASE_ENV | {
        "CUBRID_CONNECTIONS": "Reporting",
        "CUBRID_REPORTING_HOST": "reporting-db",
        "CUBRID_REPORTING_USER": "ru",
        "CUBRID_REPORTING_PASSWORD": "rp",
        "CUBRID_REPORTING_DATABASE": "reports",
    }
    registry = ConnectionRegistry.from_env(env)
    assert registry.config_for("reporting").host == "reporting-db"
    assert registry.config_for("REPORTING").host == "reporting-db"


def test_registry_missing_named_vars_fail_with_name() -> None:
    env = BASE_ENV | {"CUBRID_CONNECTIONS": "reporting"}
    with pytest.raises(ConfigError, match="CUBRID_REPORTING_HOST"):
        ConnectionRegistry.from_env(env)


def test_registry_reserved_default_name() -> None:
    with pytest.raises(ConfigError, match="reserved"):
        ConnectionRegistry.from_env(BASE_ENV | {"CUBRID_CONNECTIONS": "default"})


def test_registry_invalid_name() -> None:
    with pytest.raises(ConfigError, match="invalid connection name"):
        ConnectionRegistry.from_env(BASE_ENV | {"CUBRID_CONNECTIONS": "bad-name"})


def test_registry_duplicate_name_after_normalization() -> None:
    env = BASE_ENV | {
        "CUBRID_CONNECTIONS": "reporting,REPORTING",
        "CUBRID_REPORTING_HOST": "reporting-db",
        "CUBRID_REPORTING_USER": "ru",
        "CUBRID_REPORTING_PASSWORD": "rp",
        "CUBRID_REPORTING_DATABASE": "reports",
    }
    with pytest.raises(ConfigError, match="duplicate connection name"):
        ConnectionRegistry.from_env(env)


def test_registry_unknown_selector_lists_available() -> None:
    registry = ConnectionRegistry.from_env(BASE_ENV)
    with pytest.raises(ConfigError) as excinfo:
        registry.config_for("nope")
    message = str(excinfo.value)
    assert "unknown connection" in message
    assert "default" in message


def test_registry_blank_names_in_list_are_skipped() -> None:
    env = BASE_ENV | {
        "CUBRID_CONNECTIONS": "reporting, ,",
        "CUBRID_REPORTING_HOST": "reporting-db",
        "CUBRID_REPORTING_USER": "ru",
        "CUBRID_REPORTING_PASSWORD": "rp",
        "CUBRID_REPORTING_DATABASE": "reports",
    }
    registry = ConnectionRegistry.from_env(env)
    assert registry.names == ["default", "reporting"]
