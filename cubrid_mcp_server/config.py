"""Environment-variable configuration for the CUBRID MCP server."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

#: Default name of the connection built from the bare ``CUBRID_*`` variables.
DEFAULT_CONNECTION = "default"

#: Connection names must be simple identifiers so they map cleanly onto env vars.
_NAME_PATTERN = re.compile(r"[A-Za-z0-9_]+")


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    user: str
    password: str = field(repr=False)
    database: str
    readonly: bool
    max_chars: int
    max_rows: int
    max_sql_length: int = 65536
    query_timeout: float = 30.0

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        """Build the default connection config from the bare ``CUBRID_*`` variables."""
        source = env if env is not None else os.environ
        return _parse_config(source, "CUBRID_")


def _parse_config(source: Mapping[str, str], prefix: str) -> Config:
    """Parse a single connection's :class:`Config` from ``source`` using ``prefix``.

    ``prefix`` is the environment-variable prefix for this connection: ``"CUBRID_"``
    for the default connection and ``"CUBRID_<NAME>_"`` for a named one. Connection
    fields live at ``{prefix}HOST`` etc.; MCP tuning knobs live at ``{prefix}MCP_*``.
    """
    mcp_prefix = f"{prefix}MCP_"
    try:
        host = source[f"{prefix}HOST"]
        user = source[f"{prefix}USER"]
        password = source[f"{prefix}PASSWORD"]
        database = source[f"{prefix}DATABASE"]
    except KeyError as missing:
        raise ConfigError(f"missing required environment variable: {missing.args[0]}") from None

    port_raw = source.get(f"{prefix}PORT", "33000")
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise ConfigError(f"{prefix}PORT must be an integer, got {port_raw!r}") from exc

    readonly = _parse_bool(source.get(f"{mcp_prefix}READONLY", "1"))

    max_chars = _parse_positive_int(source, f"{mcp_prefix}MAX_CHARS", "4000")
    max_rows = _parse_positive_int(source, f"{mcp_prefix}MAX_ROWS", "1000")
    max_sql_length = _parse_positive_int(source, f"{mcp_prefix}MAX_SQL_LENGTH", "65536")

    query_timeout_raw = source.get(f"{mcp_prefix}QUERY_TIMEOUT", "30")
    try:
        query_timeout = float(query_timeout_raw)
    except ValueError as exc:
        raise ConfigError(
            f"{mcp_prefix}QUERY_TIMEOUT must be a number, got {query_timeout_raw!r}"
        ) from exc
    if query_timeout <= 0:
        raise ConfigError(f"{mcp_prefix}QUERY_TIMEOUT must be positive")

    return Config(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        readonly=readonly,
        max_chars=max_chars,
        max_rows=max_rows,
        max_sql_length=max_sql_length,
        query_timeout=query_timeout,
    )


def _parse_positive_int(source: Mapping[str, str], key: str, default: str) -> int:
    raw = source.get(key, default)
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise ConfigError(f"{key} must be positive")
    return value


@dataclass(frozen=True)
class ConnectionRegistry:
    """A named set of connection :class:`Config` objects with a default.

    The default connection always comes from the bare ``CUBRID_*`` variables, so a
    deployment that sets no ``CUBRID_CONNECTIONS`` behaves exactly as it did before
    multi-connection support existed. Additional named connections are read from
    ``CUBRID_<NAME>_*`` variables. Connection names are matched case-insensitively.
    """

    configs: Mapping[str, Config]
    default_name: str = DEFAULT_CONNECTION

    def config_for(self, connection: str | None = None) -> Config:
        """Return the config for ``connection`` (the default when ``None``/empty).

        Raises :class:`ConfigError` naming the available connections when the
        requested name is unknown, so the message is safe to surface to clients.
        """
        name = (
            connection.strip().lower() if connection and connection.strip() else self.default_name
        )
        try:
            return self.configs[name]
        except KeyError:
            available = ", ".join(sorted(self.configs))
            raise ConfigError(
                f"unknown connection {name!r}. Available connections: {available}"
            ) from None

    @property
    def names(self) -> list[str]:
        return sorted(self.configs)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "ConnectionRegistry":
        source = env if env is not None else os.environ
        configs: dict[str, Config] = {DEFAULT_CONNECTION: _parse_config(source, "CUBRID_")}

        raw = source.get("CUBRID_CONNECTIONS", "").strip()
        if raw:
            for original in (part.strip() for part in raw.split(",")):
                if not original:
                    continue
                if not _NAME_PATTERN.fullmatch(original):
                    raise ConfigError(
                        f"invalid connection name {original!r}: names must match [A-Za-z0-9_]+"
                    )
                name = original.lower()
                if name == DEFAULT_CONNECTION:
                    raise ConfigError("connection name 'default' is reserved")
                if name in configs:
                    raise ConfigError(f"duplicate connection name {original!r}")
                configs[name] = _parse_config(source, f"CUBRID_{original.upper()}_")

        return cls(configs=configs)


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"expected a boolean-like value, got {value!r}")
