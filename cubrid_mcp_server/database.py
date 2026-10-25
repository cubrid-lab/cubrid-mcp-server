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


class NoResultSetError(ValueError):
    """Raised when a read statement produced no result set.

    The read path (``fetch_all``/``fetch_many``) only serves statements that
    return rows. One that does not (a write or DDL statement that slipped past
    the SQL checks) is rolled back and reported with this error; the session is
    intact, so the connection is kept.
    """


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


# pycubrid errors that report a statement the server rejected (bad SQL, unknown
# object, constraint or value error) rather than a broken session. Deliberately
# an allowlist: ``OperationalError`` (communication failures, closed handles),
# ``InterfaceError`` (closed connection), ``InternalError`` and the generic
# ``DatabaseError`` (unmapped CAS codes) are all treated as possible transport
# or session failures and still discard the connection.
_SERVER_SQL_ERRORS: tuple[type[BaseException], ...] = (
    pycubrid.ProgrammingError,
    pycubrid.IntegrityError,
    pycubrid.DataError,
)


def _is_server_sql_error(exc: BaseException) -> bool:
    """Return ``True`` if ``exc`` is a statement-level SQL error, not a session failure.

    Such an error arrives as a complete CAS error response, so the connection is
    still in protocol sync and only the transaction needs to be ended.
    """
    return isinstance(exc, _SERVER_SQL_ERRORS) and not _is_timeout_error(exc)


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

    _SERIAL_ATTRIBUTE_COLUMNS = ("att_name", "attr_name")

    def __init__(self, config: Config) -> None:
        self._config = config
        self._connection: Any = None
        self._lock = threading.RLock()
        self._serial_attribute_column: str | None = None
        self._owner_qualified_names: bool | None = None

    def owner_qualified_names(self) -> bool:
        """Whether table names are unique per owner, probed once per connection.

        From CUBRID 11.2 on, two users may each own a table with the same name,
        and the catalog views (``db_attribute``, ``db_index``, ``db_index_key``,
        ``db_direct_super_class``) gain ``owner_name`` columns to tell them apart.
        Before 11.2 table names are unique in the database and those views have
        no owner column. Probed with a zero-row SELECT and cached like
        :meth:`serial_attribute_column`.
        """
        with self._lock:
            if self._owner_qualified_names is not None:
                return self._owner_qualified_names
            probed = self.connect()
            try:
                self.fetch_all('SELECT "owner_name" FROM db_attribute WHERE 1 = 0')
            except DatabaseError as exc:
                # Only the server rejecting the column answers the question;
                # a lost connection or a timeout must not be cached as "no".
                if exc.__cause__ is None or not _is_server_sql_error(exc.__cause__):
                    raise
                found = False
            else:
                found = True
            # Cache the answer only for the connection it was probed on: if the
            # rollback after the probe failed, the connection was discarded and
            # the next one may reach another server version.
            if self._connection is probed:
                self._owner_qualified_names = found
            return found

    def serial_attribute_column(self) -> str:
        """Resolve ``db_serial``'s attribute column once per connection.

        CUBRID 11.2 names it ``att_name``; 11.4 renamed it to ``attr_name``.
        Probed with a zero-row SELECT and cached, so every later
        ``list_serials`` call uses the version-correct identifier.

        Only the server rejecting a spelling moves on to the other one: a lost
        connection or a timeout says nothing about the catalog and is raised
        as it is (#351). Every answer belongs to the connection it was probed
        on; if the probe's cleanup discarded that connection, the call fails
        instead of applying the answer to the next connection, which may reach
        another server version.
        """
        with self._lock:
            if self._serial_attribute_column is not None:
                return self._serial_attribute_column
            probed = self.connect()
            for column in self._SERIAL_ATTRIBUTE_COLUMNS:
                try:
                    self.fetch_all(f'SELECT "{column}" FROM db_serial WHERE 1 = 0')
                except DatabaseError as exc:
                    if exc.__cause__ is None or not _is_server_sql_error(exc.__cause__):
                        raise
                    found = False
                else:
                    found = True
                if self._connection is not probed:
                    raise DatabaseError(
                        "connection was reset while probing db_serial; retry the request"
                    )
                if found:
                    self._serial_attribute_column = column
                    return column
            raise DatabaseError("db_serial exposes neither att_name nor attr_name")

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
                connect_timeout=self._config.connect_timeout,
                # Bound how long a single statement may block the shared
                # connection. This is a socket read timeout (not a true
                # server-side statement timeout): if the broker sends no bytes
                # for this many seconds the read aborts and we discard the
                # now-unusable connection. See CUBRID_MCP_QUERY_TIMEOUT.
                read_timeout=self._config.query_timeout,
            )
        except Exception as exc:
            # Host, database and the driver's cause (which may embed the user or
            # password) go to the stderr log only; clients get a fixed message.
            logger.error(
                "failed to connect to CUBRID host=%s port=%s database=%s",
                self._config.host,
                self._config.port,
                self._config.database,
                exc_info=exc,
            )
            raise DatabaseError("failed to connect to CUBRID") from exc
        return self._connection

    def _discard_connection(self) -> None:
        """Drop the cached connection, closing it first on a best-effort basis.

        Also forgets the per-connection catalog probes (``db_serial`` column and
        owner-qualified names): the next connection may reach a different CUBRID
        version (e.g. after a broker failover), so they must be re-probed rather
        than reused.
        """
        connection = self._connection
        self._connection = None
        self._serial_attribute_column = None
        self._owner_qualified_names = None
        if connection is not None:
            try:
                connection.close()
            except Exception as exc:
                logger.debug("failed to close stale connection: %s", exc)

    def close(self) -> None:
        self._serial_attribute_column = None
        self._owner_qualified_names = None
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
            cursor: Any = None
            timed_out = False
            try:
                cursor = connection.cursor()
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
                if cursor is None:
                    # Cursor creation itself failed: no statement ran, and a
                    # connection that cannot open a cursor is not worth reusing.
                    self._discard_connection()
                else:
                    self._rollback_or_discard(connection)
                logger.error("write failed", exc_info=exc)
                raise DatabaseError(f"write failed: {sanitize_error(exc)}") from exc
            finally:
                if cursor is not None and not timed_out:
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
            cursor: Any = None
            timed_out = False
            try:
                # Created inside the try so a cursor-creation failure takes the
                # same sanitize + discard recovery path as a failed query.
                cursor = connection.cursor()
                yield cursor
            except NoResultSetError:
                # The statement ran to completion, so the session is in sync:
                # roll back whatever it did and keep the connection.
                self._rollback_or_discard(connection)
                raise
            except Exception as exc:
                if _is_timeout_error(exc):
                    timed_out = True
                    raise self._timeout_error(exc) from exc
                if cursor is not None and _is_server_sql_error(exc):
                    # The server rejected the statement but the session is
                    # intact: end the read transaction and keep the connection
                    # (a failing rollback still discards it).
                    self._rollback_or_discard(connection)
                else:
                    # Lazy recovery (#106): drop the possibly-dead connection so
                    # the next request reconnects instead of pre-pinging on
                    # acquisition.
                    self._discard_connection()
                # Full detail to stderr for operators; only the error category is
                # surfaced to the client to avoid leaking schema/host/SQL/config.
                logger.error("query failed", exc_info=exc)
                raise DatabaseError(f"query failed: {sanitize_error(exc)}") from exc
            finally:
                # After a timeout the connection is already discarded and the
                # socket is dead; closing the cursor would only block again.
                if cursor is not None and not timed_out:
                    self._safe_close_cursor(cursor)

    @contextmanager
    def exclusive(self, *, rollback_on_sql_error: bool = True) -> Iterator[Any]:
        """Hold the connection lock across multiple statements (e.g. SET TRACE ... SHOW TRACE).

        After a server-side SQL error the transaction is rolled back and the
        connection kept. A caller whose block already ends the transaction on
        every exit (``trace_enabled``) passes ``rollback_on_sql_error=False`` so
        exactly one rollback is sent.
        """
        with self._lock:
            connection = self.connect()
            try:
                yield connection
            except Exception as exc:
                if _is_timeout_error(exc):
                    raise self._timeout_error(exc) from exc
                if _is_server_sql_error(exc):
                    # As in ``cursor``: the server rejected a statement but the
                    # session is in sync, so end the transaction and keep the
                    # connection (a failing rollback still discards it). Skip it
                    # when cleanup inside the block already discarded it.
                    if rollback_on_sql_error and self._connection is connection:
                        self._rollback_or_discard(connection)
                else:
                    # Lazy recovery on any other failure, mirroring ``cursor``.
                    self._discard_connection()
                if isinstance(exc, DatabaseError):
                    raise
                # Raw driver errors can embed SQL, schema or host details.
                logger.error("query failed", exc_info=exc)
                raise DatabaseError(f"query failed: {sanitize_error(exc)}") from exc

    @contextmanager
    def trace_enabled(self) -> Iterator[Any]:
        """Run statements with CUBRID ``SET TRACE ON``, guaranteeing cleanup.

        Holds the connection lock across the whole ``SET TRACE ... SHOW TRACE``
        sequence so a concurrent query cannot interleave and clobber the session
        trace state. On exit the trace flag is turned off and any pending
        transaction is rolled back on a best-effort basis; if that cleanup fails
        the connection is discarded (see :meth:`_reset_trace_state`). After a
        timeout the socket is dead and ``exclusive()`` discards the connection,
        so no cleanup statement is sent.
        """
        # _reset_trace_state below rolls back (or discards) on every exit.
        with self.exclusive(rollback_on_sql_error=False) as connection:
            cursor = connection.cursor()
            timed_out = False
            try:
                cursor.execute("SET TRACE ON", ())
                yield cursor
            except Exception as exc:
                timed_out = _is_timeout_error(exc)
                raise
            finally:
                if not timed_out:
                    self._safe_close_cursor(cursor)
                    self._reset_trace_state(connection)

    def _reset_trace_state(self, connection: Any) -> None:
        """Best-effort cleanup of ``SET TRACE`` session state and pending transaction.

        Called with the connection lock held. If opening the cleanup cursor,
        ``SET TRACE OFF`` or the rollback fails, the session may still have
        tracing on or a transaction open, so the connection is discarded and the
        next call reconnects instead of reusing it. Cleanup stops at the first
        failure, so an unhealthy session gets no further statements. It never
        raises: a query error that is already propagating stays the error the
        caller sees.
        """
        step = "opening the cleanup cursor"
        try:
            cursor = connection.cursor()
            step = "SET TRACE OFF"
            try:
                cursor.execute("SET TRACE OFF", ())
            finally:
                # Best-effort close: a failing close() is logged, not treated
                # as a failed cleanup step.
                self._safe_close_cursor(cursor)
            step = "rollback"
            connection.rollback()
        except Exception as exc:
            logger.warning("trace cleanup failed at %s; discarding connection", step, exc_info=exc)
            self._discard_connection()

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
                logger.error("health check failed", exc_info=exc)
                return {"ok": False, "error": sanitize_error(exc)}
            return {"ok": True, "server_version": str(version)}

    def _end_read_transaction(self) -> None:
        """Roll back the read transaction a successful fetch left open.

        The connection runs with pycubrid's default ``autocommit=False``, so a
        SELECT opens a transaction that would otherwise stay open across tool
        calls, holding locks and pinning the snapshot. Called with the lock held,
        after the cursor is closed. Calling ``fetch_*`` inside ``exclusive()``
        ends the outer transaction.
        """
        if self._connection is not None:
            self._rollback_or_discard(self._connection)

    @staticmethod
    def _require_result_set(cursor: Any) -> None:
        """Raise :class:`NoResultSetError` if the executed statement has no result set.

        Raised inside ``cursor()``, which rolls the statement back and keeps the
        connection.
        """
        if cursor.description is None:
            raise NoResultSetError(
                "statement produced no result set; execute_query is read-only, "
                "use execute_write for INSERT/UPDATE/DELETE"
            )

    def fetch_all(self, sql: str, params: tuple[Any, ...] | None = None) -> list[tuple[Any, ...]]:
        with self._lock:
            with self.cursor() as cursor:
                cursor.execute(sql, params or ())
                self._require_result_set(cursor)
                rows = list(cursor.fetchall())
            self._end_read_transaction()
            return rows

    def fetch_many(
        self,
        sql: str,
        params: tuple[Any, ...] | None = None,
        max_rows: int | None = None,
    ) -> tuple[list[tuple[Any, ...]], bool]:
        """Stream rows, returning ``(rows, truncated)``.

        At most ``max_rows`` rows are returned; ``truncated`` is ``True`` when the
        result set contained more rows than that. When ``max_rows`` is ``None`` all
        rows are returned and ``truncated`` is always ``False``. The read
        transaction is rolled back before returning, truncated or not.
        """
        with self._lock:
            with self.cursor() as cursor:
                cursor.execute(sql, params or ())
                self._require_result_set(cursor)
                rows: list[tuple[Any, ...]] = []
                truncated = False
                while not truncated:
                    batch = cursor.fetchmany(100)
                    if not batch:
                        break
                    for row in batch:
                        if max_rows is not None and len(rows) >= max_rows:
                            truncated = True
                            break
                        rows.append(row)
            self._end_read_transaction()
            return rows, truncated
