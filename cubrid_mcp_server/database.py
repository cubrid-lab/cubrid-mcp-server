"""Thin wrapper around pycubrid for the MCP server."""

from __future__ import annotations

import logging
import socket
import threading
from contextlib import contextmanager
from typing import Any, Iterator


import pycubrid

from cubrid_mcp_server.config import Config

logger = logging.getLogger(__name__)


class DatabaseError(RuntimeError):
    """Raised when a database operation fails."""


class QueryTimeoutError(DatabaseError):
    """Raised when a statement exceeds the configured read timeout."""


def _is_timeout_error(exc: BaseException | None) -> bool:
    """Return ``True`` if ``exc`` (or any error in its chain) is a socket timeout.

    ``read_timeout`` is enforced as a socket ``settimeout``; a slow statement
    surfaces as :class:`socket.timeout`/:class:`TimeoutError`, which pycubrid
    re-wraps as an ``OperationalError`` with the timeout preserved as its
    ``__cause__``. Walking the chain catches both the raw and wrapped forms.
    """
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, (socket.timeout, TimeoutError)):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


class Database:
    """Lazily opens and reuses a single pycubrid connection."""

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
                # Bound how long a single statement may block the shared
                # connection. This is a socket read timeout (not a true
                # server-side statement timeout): if the broker sends no bytes
                # for this many seconds the read aborts and we discard the
                # now-unusable connection. See CUBRID_MCP_QUERY_TIMEOUT.
                read_timeout=self._config.query_timeout,
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

    @staticmethod
    def _safe_close_cursor(cursor: Any) -> None:
        try:
            cursor.close()
        except Exception as exc:
            logger.debug("failed to close cursor: %s", exc)

    def _timeout_error(self, exc: BaseException) -> QueryTimeoutError:
        """Discard the corrupt connection and build a clear timeout error."""
        # The socket timed out mid-statement, so the connection buffer is now
        # in an unknown state; drop it so the next call reconnects instead of
        # reusing a corrupt session.
        self._discard_connection()
        return QueryTimeoutError(
            f"query exceeded timeout of {self._config.query_timeout:g}s (CUBRID_MCP_QUERY_TIMEOUT)"
        )

    @contextmanager
    def cursor(self) -> Iterator[Any]:
        with self._lock:
            connection = self.connect()
            cursor = connection.cursor()
            timed_out = False
            try:
                yield cursor
            except Exception as exc:
                if _is_timeout_error(exc):
                    timed_out = True
                    raise self._timeout_error(exc) from exc
                raise DatabaseError(f"query failed: {exc}") from exc
            finally:
                # After a timeout the connection is already discarded and the
                # socket is dead; closing the cursor would only block again.
                if not timed_out:
                    self._safe_close_cursor(cursor)

    @contextmanager
    def exclusive(self) -> Iterator[Any]:
        """Hold the connection lock across multiple statements (e.g. SET TRACE ... SHOW TRACE)."""
        with self._lock:
            connection = self.connect()
            try:
                yield connection
            except Exception as exc:
                if _is_timeout_error(exc):
                    raise self._timeout_error(exc) from exc
                raise

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
