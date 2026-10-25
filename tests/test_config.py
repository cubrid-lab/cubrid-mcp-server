import pytest

from cubrid_mcp_server.config import Config, ConfigError, ConnectionRegistry, _parse_bool


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


@pytest.mark.parametrize("key", ["CUBRID_HOST", "CUBRID_USER", "CUBRID_DATABASE"])
@pytest.mark.parametrize("value", ["", "   ", "\t"])
def test_from_env_blank_required(key: str, value: str) -> None:
    with pytest.raises(ConfigError, match=key):
        Config.from_env(BASE_ENV | {key: value})


def test_from_env_non_empty_required_values_still_work() -> None:
    cfg = Config.from_env(BASE_ENV)
    assert (cfg.host, cfg.user, cfg.database) == ("localhost", "mcp", "demodb")


@pytest.mark.parametrize("value", ["0", "-1", "65536", "99999"])
def test_from_env_out_of_range_port(value: str) -> None:
    with pytest.raises(ConfigError, match="CUBRID_PORT must be between 1 and 65535"):
        Config.from_env(BASE_ENV | {"CUBRID_PORT": value})


def test_from_env_invalid_port() -> None:
    with pytest.raises(ConfigError, match="CUBRID_PORT must be an integer"):
        Config.from_env(BASE_ENV | {"CUBRID_PORT": "not-a-port"})


@pytest.mark.parametrize("value", ["1", "33000", "65535"])
def test_from_env_valid_port_boundaries(value: str) -> None:
    assert Config.from_env(BASE_ENV | {"CUBRID_PORT": value}).port == int(value)


def test_from_env_invalid_max_chars() -> None:
    with pytest.raises(ConfigError, match="CUBRID_MCP_MAX_CHARS"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_MAX_CHARS": "zero"})
    with pytest.raises(ConfigError, match="positive"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_MAX_CHARS": "0"})


def test_from_env_invalid_readonly() -> None:
    with pytest.raises(ConfigError, match="boolean"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_READONLY": "maybe"})


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", True),
        ("true", True),
        ("yes", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("no", False),
        ("off", False),
        ("TrUe", True),
        ("FaLsE", False),
        ("OFF", False),
        ("  Yes\t", True),
        (" no ", False),
    ],
)
def test_parse_bool_accepted_aliases(value: str, expected: bool) -> None:
    assert _parse_bool(value) is expected


@pytest.mark.parametrize("value", ["", " ", "maybe", "2", "y", "enabled"])
def test_parse_bool_invalid_aliases(value: str) -> None:
    with pytest.raises(ConfigError, match="boolean"):
        _parse_bool(value)


@pytest.mark.parametrize("name", ["MCP_READONLY", "MCP_WRITE", "MCP_AUDIT_LOG"])
def test_from_env_invalid_bool_names_variable(name: str) -> None:
    with pytest.raises(ConfigError, match=rf"CUBRID_{name} must be a boolean.*'maybe'"):
        Config.from_env(BASE_ENV | {f"CUBRID_{name}": "maybe"})


@pytest.mark.parametrize("name", ["MCP_READONLY", "MCP_WRITE", "MCP_AUDIT_LOG"])
def test_registry_invalid_bool_names_prefixed_variable(name: str) -> None:
    env = BASE_ENV | {"CUBRID_CONNECTIONS": "reporting"}
    env |= {"CUBRID_REPORTING_HOST": "db2", "CUBRID_REPORTING_USER": "u"}
    env |= {"CUBRID_REPORTING_PASSWORD": "p", "CUBRID_REPORTING_DATABASE": "d"}
    env[f"CUBRID_REPORTING_{name}"] = "maybe"
    with pytest.raises(ConfigError, match=rf"CUBRID_REPORTING_{name} must be a boolean"):
        ConnectionRegistry.from_env(env)


def test_parse_bool_without_key_keeps_old_message() -> None:
    with pytest.raises(ConfigError, match="expected a boolean-like value"):
        _parse_bool("maybe")


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


def test_from_env_non_numeric_query_timeout() -> None:
    with pytest.raises(ConfigError, match="CUBRID_MCP_QUERY_TIMEOUT"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_QUERY_TIMEOUT": "soon"})


@pytest.mark.parametrize("value", ["nan", "inf", "-1", "0"])
def test_from_env_non_positive_or_non_finite_query_timeout(value: str) -> None:
    with pytest.raises(ConfigError, match="positive"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_QUERY_TIMEOUT": value})


def test_from_env_connect_timeout_default_and_override() -> None:
    assert Config.from_env(BASE_ENV).connect_timeout == 10.0
    cfg = Config.from_env(BASE_ENV | {"CUBRID_MCP_CONNECT_TIMEOUT": "2.5"})
    assert cfg.connect_timeout == 2.5


def test_from_env_non_numeric_connect_timeout() -> None:
    with pytest.raises(ConfigError, match="CUBRID_MCP_CONNECT_TIMEOUT must be a number"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_CONNECT_TIMEOUT": "soon"})


@pytest.mark.parametrize("value", ["nan", "inf", "-1", "0"])
def test_from_env_non_positive_or_non_finite_connect_timeout(value: str) -> None:
    with pytest.raises(ConfigError, match="CUBRID_MCP_CONNECT_TIMEOUT must be positive"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_CONNECT_TIMEOUT": value})


def test_from_env_max_row_count_tables_default_and_override() -> None:
    assert Config.from_env(BASE_ENV).max_row_count_tables == 50
    cfg = Config.from_env(BASE_ENV | {"CUBRID_MCP_MAX_ROW_COUNT_TABLES": "200"})
    assert cfg.max_row_count_tables == 200


@pytest.mark.parametrize(
    ("value", "message"),
    [("lots", "must be an integer"), ("0", "must be positive"), ("-3", "must be positive")],
)
def test_from_env_invalid_max_row_count_tables(value: str, message: str) -> None:
    with pytest.raises(ConfigError, match=f"CUBRID_MCP_MAX_ROW_COUNT_TABLES {message}"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_MAX_ROW_COUNT_TABLES": value})


@pytest.mark.parametrize(("value", "expected"), [("1024", 1024), ("0", 0)])
def test_from_env_max_inline_binary_bytes_default_and_override(value: str, expected: int) -> None:
    assert Config.from_env(BASE_ENV).max_inline_binary_bytes == 256
    cfg = Config.from_env(BASE_ENV | {"CUBRID_MCP_MAX_INLINE_BINARY_BYTES": value})
    assert cfg.max_inline_binary_bytes == expected


@pytest.mark.parametrize(
    ("value", "message"),
    [("big", "must be an integer"), ("-1", "must not be negative")],
)
def test_from_env_invalid_max_inline_binary_bytes(value: str, message: str) -> None:
    with pytest.raises(ConfigError, match=f"CUBRID_MCP_MAX_INLINE_BINARY_BYTES {message}"):
        Config.from_env(BASE_ENV | {"CUBRID_MCP_MAX_INLINE_BINARY_BYTES": value})


def test_registry_named_connection_reads_its_own_new_limits() -> None:
    env = BASE_ENV | {
        "CUBRID_MCP_CONNECT_TIMEOUT": "3",
        "CUBRID_MCP_MAX_ROW_COUNT_TABLES": "7",
        "CUBRID_MCP_MAX_INLINE_BINARY_BYTES": "0",
        "CUBRID_CONNECTIONS": "reporting",
        "CUBRID_REPORTING_HOST": "reporting-db",
        "CUBRID_REPORTING_USER": "ru",
        "CUBRID_REPORTING_PASSWORD": "rp",
        "CUBRID_REPORTING_DATABASE": "reports",
        "CUBRID_REPORTING_MCP_CONNECT_TIMEOUT": "45",
        "CUBRID_REPORTING_MCP_MAX_ROW_COUNT_TABLES": "100",
    }
    registry = ConnectionRegistry.from_env(env)
    default = registry.config_for()
    assert (default.connect_timeout, default.max_row_count_tables) == (3.0, 7)
    assert default.max_inline_binary_bytes == 0
    reporting = registry.config_for("reporting")
    assert (reporting.connect_timeout, reporting.max_row_count_tables) == (45.0, 100)
    # Not inherited from the bare CUBRID_MCP_* variable.
    assert reporting.max_inline_binary_bytes == 256


def test_empty_password_is_accepted() -> None:
    # CUBRID's default ``dba`` user has an empty password.
    cfg = Config.from_env(BASE_ENV | {"CUBRID_USER": "dba", "CUBRID_PASSWORD": ""})
    assert cfg.user == "dba"
    assert cfg.password == ""


def test_password_not_in_repr() -> None:
    cfg = Config.from_env(BASE_ENV)
    assert "secret" not in repr(cfg)


def test_registry_default_only_when_no_connections() -> None:
    registry = ConnectionRegistry.from_env(BASE_ENV)
    assert sorted(registry.configs) == ["default"]
    assert registry.config_for().database == "demodb"
    # None/empty selector resolves to the default connection.
    assert registry.config_for(None) is registry.config_for()
    assert registry.config_for("   ") is registry.config_for()


def test_registry_empty_connections_behaves_like_unset() -> None:
    registry = ConnectionRegistry.from_env(BASE_ENV | {"CUBRID_CONNECTIONS": "  "})
    assert sorted(registry.configs) == ["default"]


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
    assert sorted(registry.configs) == ["default", "reporting"]
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
    reporting = registry.config_for("reporting")
    assert reporting.host == "reporting-db"
    assert registry.config_for("REPORTING") is reporting
    assert registry.config_for("  RePoRtInG  ") is reporting


def test_registry_named_connection_does_not_inherit_bare_settings() -> None:
    env = BASE_ENV | {
        "CUBRID_PORT": "30000",
        "CUBRID_MCP_MAX_ROWS": "250",
        "CUBRID_MCP_MAX_CHARS": "8000",
        "CUBRID_MCP_READONLY": "0",
        "CUBRID_CONNECTIONS": "reporting",
        "CUBRID_REPORTING_HOST": "reporting-db",
        "CUBRID_REPORTING_USER": "ru",
        "CUBRID_REPORTING_PASSWORD": "rp",
        "CUBRID_REPORTING_DATABASE": "reports",
    }
    registry = ConnectionRegistry.from_env(env)
    default = registry.config_for()
    assert default.port == 30000
    assert default.max_rows == 250
    assert default.max_chars == 8000
    assert default.readonly is False

    # The named connection does not inherit the bare CUBRID_* / CUBRID_MCP_* variables.
    reporting = registry.config_for("reporting")
    assert reporting.port == 33000
    assert reporting.max_rows == 1000
    assert reporting.max_chars == 4000
    assert reporting.readonly is True


def test_registry_missing_named_vars_fail_with_name() -> None:
    env = BASE_ENV | {"CUBRID_CONNECTIONS": "reporting"}
    with pytest.raises(ConfigError, match="CUBRID_REPORTING_HOST"):
        ConnectionRegistry.from_env(env)


@pytest.mark.parametrize(
    ("suffix", "value"),
    [
        ("PORT", "x"),
        ("PORT", "70000"),
        ("MCP_MAX_ROWS", "0"),
        ("MCP_MAX_CHARS", "lots"),
        ("MCP_MAX_SQL_LENGTH", "-5"),
        ("MCP_QUERY_TIMEOUT", "inf"),
        ("MCP_CONNECT_TIMEOUT", "0"),
        ("MCP_MAX_ROW_COUNT_TABLES", "many"),
        ("MCP_MAX_INLINE_BINARY_BYTES", "-1"),
    ],
)
def test_registry_invalid_named_values_name_the_prefixed_variable(suffix: str, value: str) -> None:
    env = BASE_ENV | {
        "CUBRID_CONNECTIONS": "reporting",
        "CUBRID_REPORTING_HOST": "reporting-db",
        "CUBRID_REPORTING_USER": "ru",
        "CUBRID_REPORTING_PASSWORD": "rp",
        "CUBRID_REPORTING_DATABASE": "reports",
        f"CUBRID_REPORTING_{suffix}": value,
    }
    with pytest.raises(ConfigError) as excinfo:
        ConnectionRegistry.from_env(env)
    message = str(excinfo.value)
    assert f"CUBRID_REPORTING_{suffix}" in message
    # The error must not fall back to the bare default variable name.
    assert f"CUBRID_{suffix}" not in message


def test_registry_blank_named_host_is_reported_as_missing() -> None:
    env = BASE_ENV | {
        "CUBRID_CONNECTIONS": "reporting",
        "CUBRID_REPORTING_HOST": "  ",
        "CUBRID_REPORTING_USER": "ru",
        "CUBRID_REPORTING_PASSWORD": "rp",
        "CUBRID_REPORTING_DATABASE": "reports",
    }
    with pytest.raises(
        ConfigError, match="missing required environment variable: CUBRID_REPORTING_HOST"
    ):
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
    assert sorted(registry.configs) == ["default", "reporting"]
