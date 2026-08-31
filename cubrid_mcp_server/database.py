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


def sanitize_error(exc: BaseException) -> str:
    """Return a concise, non-sensitive description of an exception for clients.

    Only the exception's class name is surfaced — never the raw message, which may
    embed schema details, hostnames, SQL fragments, or configuration values. Full
    detail is logged to stderr (see callers) for operator diagnostics.
    """
    return type(exc).__name__


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
        # Return the cached connection without a liveness ping: pinging on every
        # cursor acquisition adds an avoidable server round-trip to each operation.
        # Staleness is handled lazily instead — a failed query discards the
        # connection so the next request transparently reconnects (see ``cursor``).
        if self._connection is not None:
            return self._connection

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

    def _rollback_or_discard(self, connection: Any) -> None:
        """Roll back a failed write; discard the connection if rollback itself fails.

        A rollback failure means the shared connection may retain unknown
        transaction state, so it is dropped (closed best-effort) to force a
        clean reconnect on the next call rather than reusing a poisoned session.
        """
        try:
            connection.rollback()
        except Exception as exc:
            logger.debug("rollback failed; discarding connection: %s", exc)
            self._discard_connection()

    def execute_write(self, sql: str, params: tuple[Any, ...] | None = None) -> int:
        """Execute a single DML statement in an atomic transaction.

        Commits on success and returns the affected-row count. On any failure the
        transaction is rolled back (and the connection discarded if the rollback
        itself fails), the full error is logged to stderr, and a sanitized
        :class:`DatabaseError` is raised. Only reachable via the opt-in write
        path; callers must have already passed :func:`safety.ensure_write_allowed`.
        """
        with self._lock:
            connection = self.connect()
            cursor = connection.cursor()
            timed_out = False
            try:
                cursor.execute(sql, params or ())
                affected = int(cursor.rowcount)
                connection.commit()
                return affected
            except Exception as exc:
                if _is_timeout_error(exc):
                    # The socket is dead mid-statement; a rollback would only
                    # block again. _timeout_error discards the connection.
                    timed_out = True
                    raise self._timeout_error(exc) from exc
                self._rollback_or_discard(connection)
                logger.error("write failed", exc_info=exc)
                raise DatabaseError(f"write failed: {sanitize_error(exc)}") from exc
            finally:
                if not timed_out:
                    self._safe_close_cursor(cursor)

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
                # Lazy recovery (#106): drop the possibly-dead connection so the
                # next request reconnects instead of pre-pinging on acquisition.
                self._discard_connection()
                # Full detail to stderr for operators; only the error category is
                # surfaced to the client to avoid leaking schema/host/SQL/config.
                logger.error("query failed", exc_info=exc)
                raise DatabaseError(f"query failed: {sanitize_error(exc)}") from exc
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
                # Lazy recovery on non-timeout failure, mirroring ``cursor``.
                self._discard_connection()
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

    def health_check(self) -> dict[str, Any]:
        """Verify connectivity on demand, reconnecting lazily on failure.

        Returns ``{"ok": True, "server_version": ...}`` when the connection
        answers a liveness ping, or ``{"ok": False, "error": ...}`` otherwise.
        This is the explicit counterpart to the per-call ping that ``connect``
        no longer performs.
        """
        with self._lock:
            try:
                connection = self.connect()
                version = connection.get_server_version()
            except Exception as exc:
                self._discard_connection()
                return {"ok": False, "error": str(exc)}
            return {"ok": True, "server_version": str(version)}

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
