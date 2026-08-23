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
        """Close a cursor on a best-effort basis, logging (not raising) failures."""
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

    @contextmanager
    def trace_enabled(self) -> Iterator[Any]:
        """Run statements with CUBRID ``SET TRACE ON``, guaranteeing cleanup.

        Holds the connection lock across the whole ``SET TRACE ... SHOW TRACE``
        sequence so a concurrent query cannot interleave and clobber the session
        trace state. On exit the trace flag is turned off and any pending
        transaction is rolled back on a best-effort basis.
        """
        with self.exclusive() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("SET TRACE ON", ())
                yield cursor
            finally:
                self._safe_close_cursor(cursor)
                self._reset_trace_state(connection)

    def _reset_trace_state(self, connection: Any) -> None:
        """Best-effort cleanup of ``SET TRACE`` session state and pending transaction."""
        cleanup_errors: list[str] = []
        try:
            cursor = connection.cursor()
        except Exception as exc:
            cleanup_errors.append(f"SET TRACE OFF failed: {exc}")
        else:
            try:
                cursor.execute("SET TRACE OFF", ())
            except Exception as exc:
                cleanup_errors.append(f"SET TRACE OFF failed: {exc}")
            finally:
                # Best-effort close: a failing close() must not be misreported
                # as a "SET TRACE OFF failed" error when the execute succeeded.
                self._safe_close_cursor(cursor)
        try:
            connection.rollback()
        except Exception as exc:
            cleanup_errors.append(f"rollback failed: {exc}")
        if cleanup_errors:
            logger.debug("trace cleanup: %s", "; ".join(cleanup_errors))

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
