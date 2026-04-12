"""Thin wrapper around pycubrid for the MCP server."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pycubrid

from cubrid_mcp_server.config import Config


class DatabaseError(RuntimeError):
    """Raised when a database operation fails."""


class Database:
    """Lazily opens and reuses a single pycubrid connection."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._connection: Any = None

    def connect(self) -> Any:
        if self._connection is None:
            try:
                self._connection = pycubrid.connect(
                    host=self._config.host,
                    port=self._config.port,
                    user=self._config.user,
                    password=self._config.password,
                    database=self._config.database,
                )
            except Exception as exc:  # pragma: no cover - driver-specific
                raise DatabaseError(f"failed to connect to CUBRID: {exc}") from exc
        return self._connection

    def close(self) -> None:
        if self._connection is not None:
            try:
                self._connection.close()
            finally:
                self._connection = None

    @contextmanager
    def cursor(self) -> Iterator[Any]:
        connection = self.connect()
        cursor = connection.cursor()
        try:
            yield cursor
        except Exception as exc:
            raise DatabaseError(f"query failed: {exc}") from exc
        finally:
            cursor.close()

    def fetch_all(self, sql: str, params: tuple[Any, ...] | None = None) -> list[tuple[Any, ...]]:
        with self.cursor() as cursor:
            cursor.execute(sql, params or ())
            return list(cursor.fetchall())
