"""Thin wrapper around pycubrid for the MCP server."""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import Any, Iterator

import pycubrid

from cubrid_mcp_server.config import Config

logger = logging.getLogger(__name__)


class DatabaseError(RuntimeError):
    """Raised when a database operation fails."""


class Database:
    """Lazily opens and reuses a single pycubrid connection.

    Concurrency model
    -----------------
    The server intentionally holds **one** pycubrid connection for the whole
    process, guarded by a single ``threading.RLock``. Every statement-executing
    path — ``cursor()`` / ``exclusive()`` / ``fetch_*`` — acquires that lock, so
    **query execution is fully serialized**: only one statement runs at a time,
    regardless of how many tool calls arrive. (The ``connect()`` / ``close()``
    lifecycle helpers are not themselves lock-guarded; they are expected to run
    outside concurrent query load, e.g. at startup and shutdown.)

    This is a deliberate fit for the MCP **stdio** transport, which serves a
    single client whose requests are already effectively sequential. A single
    serialized connection keeps CUBRID session state (e.g. ``SET TRACE`` used
    by ``explain_query``, transaction/rollback state) coherent and makes the
    lifecycle trivial to reason about and test.

    A connection **pool is intentionally not used**. It would add session-state
    isolation, cleanup, and test complexity with no benefit at this scope. Only
    introduce concurrency (e.g. per-query disposable connections) if stdio
    serialization is ever shown, by measurement, to be a real bottleneck.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._connection: Any = None
        self._lock = threading.RLock()

    def connect(self) -> Any:
        if self._connection is not None:
            try:
                self._connection.get_server_version()
                return self._connection
            except Exception:
                self._discard_connection()

        try:
            self._connection = pycubrid.connect(
                host=self._config.host,
                port=self._config.port,
                user=self._config.user,
                password=self._config.password,
                database=self._config.database,
                connect_timeout=10,
            )
        except Exception as exc:  # pragma: no cover - driver-specific
            raise DatabaseError(
                f"failed to connect to CUBRID host={self._config.host} "
                f"database={self._config.database}"
            ) from exc
        return self._connection

    def _discard_connection(self) -> None:
        """Drop the cached connection, closing it first on a best-effort basis."""
        connection = self._connection
        self._connection = None
        if connection is not None:
            try:
                connection.close()
            except Exception as exc:
                logger.debug("failed to close stale connection: %s", exc)

    def close(self) -> None:
        if self._connection is not None:
            try:
                self._connection.close()
            finally:
                self._connection = None

    @contextmanager
    def cursor(self) -> Iterator[Any]:
        with self._lock:
            connection = self.connect()
            cursor = connection.cursor()
            try:
                yield cursor
            except Exception as exc:
                raise DatabaseError(f"query failed: {exc}") from exc
            finally:
                cursor.close()

    @contextmanager
    def exclusive(self) -> Iterator[Any]:
        """Hold the connection lock across multiple statements (e.g. SET TRACE ... SHOW TRACE)."""
        with self._lock:
            yield self.connect()

    def fetch_all(self, sql: str, params: tuple[Any, ...] | None = None) -> list[tuple[Any, ...]]:
        with self.cursor() as cursor:
            cursor.execute(sql, params or ())
            return list(cursor.fetchall())

    def fetch_many(
        self,
        sql: str,
        params: tuple[Any, ...] | None = None,
        max_rows: int | None = None,
    ) -> tuple[list[tuple[Any, ...]], bool]:
        """Stream rows, returning ``(rows, truncated)``.

        At most ``max_rows`` rows are returned; ``truncated`` is ``True`` when the
        result set contained more rows than that. When ``max_rows`` is ``None`` all
        rows are returned and ``truncated`` is always ``False``.
        """
        with self.cursor() as cursor:
            cursor.execute(sql, params or ())
            rows: list[tuple[Any, ...]] = []
            truncated = False
            while True:
                batch = cursor.fetchmany(100)
                if not batch:
                    break
                for row in batch:
                    if max_rows is not None and len(rows) >= max_rows:
                        truncated = True
                        return rows, truncated
                    rows.append(row)
            return rows, truncated
