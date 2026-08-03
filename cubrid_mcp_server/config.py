"""Environment-variable configuration for the CUBRID MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


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

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        source = env if env is not None else os.environ
        try:
            host = source["CUBRID_HOST"]
            user = source["CUBRID_USER"]
            password = source["CUBRID_PASSWORD"]
            database = source["CUBRID_DATABASE"]
        except KeyError as missing:
            raise ConfigError(f"missing required environment variable: {missing.args[0]}") from None

        port_raw = source.get("CUBRID_PORT", "33000")
        try:
            port = int(port_raw)
        except ValueError as exc:
            raise ConfigError(f"CUBRID_PORT must be an integer, got {port_raw!r}") from exc

        readonly = _parse_bool(source.get("CUBRID_MCP_READONLY", "1"))

        max_chars_raw = source.get("CUBRID_MCP_MAX_CHARS", "4000")
        try:
            max_chars = int(max_chars_raw)
        except ValueError as exc:
            raise ConfigError(
                f"CUBRID_MCP_MAX_CHARS must be an integer, got {max_chars_raw!r}"
            ) from exc
        if max_chars <= 0:
            raise ConfigError("CUBRID_MCP_MAX_CHARS must be positive")

        max_rows_raw = source.get("CUBRID_MCP_MAX_ROWS", "1000")
        try:
            max_rows = int(max_rows_raw)
        except ValueError as exc:
            raise ConfigError(
                f"CUBRID_MCP_MAX_ROWS must be an integer, got {max_rows_raw!r}"
            ) from exc
        if max_rows <= 0:
            raise ConfigError("CUBRID_MCP_MAX_ROWS must be positive")

        return cls(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            readonly=readonly,
            max_chars=max_chars,
            max_rows=max_rows,
        )


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"expected a boolean-like value, got {value!r}")
