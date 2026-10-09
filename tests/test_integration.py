"""Integration tests against a real CUBRID instance.

Run with: pytest -m integration
Requires CUBRID_HOST, CUBRID_USER, CUBRID_PASSWORD, CUBRID_DATABASE env vars.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from contextlib import contextmanager
from threading import Event
from typing import Any

import pytest

pytestmark = pytest.mark.integration


def _has_cubrid_env() -> bool:
    return all(k in os.environ for k in ("CUBRID_HOST", "CUBRID_USER", "CUBRID_DATABASE"))


skipif_no_cubrid = pytest.mark.skipif(
    not _has_cubrid_env(),
    reason="CUBRID env vars not set",
)


@skipif_no_cubrid
class TestCubridIntegration:
    def setup_method(self) -> None:
        from cubrid_mcp_server import server
        from cubrid_mcp_server.config import Config
        from cubrid_mcp_server.database import Database

        from cubrid_mcp_server.context import AppContext

        self.config = Config.from_env()
        self.db = Database(self.config)
        # Route the server tool functions at the live database.
        server._context = AppContext.single(config=self.config, database=self.db)

    def teardown_method(self) -> None:
        from cubrid_mcp_server import server

        server._context = None
        self.db.close()

    def test_connect(self) -> None:
        conn = self.db.connect()
        assert conn is not None

    def test_fetch_system_catalog(self) -> None:
        rows = self.db.fetch_all(
            "SELECT class_name FROM db_class WHERE is_system_class = 'YES' LIMIT 3"
        )
        assert len(rows) > 0

    def test_all_table_names_tool(self) -> None:
        from cubrid_mcp_server import server

        tables = server.all_table_names()
        assert isinstance(tables, list)

    def test_filter_table_names_tool(self) -> None:
        from cubrid_mcp_server import server

        tables = server.all_table_names()
        if not tables:
            pytest.skip("no user tables in database")
        needle = tables[0][:2]
        filtered = server.filter_table_names(needle)
        assert tables[0] in filtered

    def test_schema_definitions_tool(self) -> None:
        from cubrid_mcp_server import server

        tables = server.all_table_names()
        if not tables:
            pytest.skip("no user tables in database")
        cols = server.schema_definitions(tables[0])
        assert isinstance(cols, list)
        assert all("name" in c and "type" in c for c in cols)

    def test_describe_table_tool(self) -> None:
        from cubrid_mcp_server import server

        tables = server.all_table_names()
        if not tables:
            pytest.skip("no user tables in database")
        desc = server.describe_table(tables[0])
        assert desc["table"] == tables[0]
        assert "columns" in desc and "indexes" in desc

    def test_describe_table_composite_pk_declared_order(self) -> None:
        from cubrid_mcp_server import server

        table = "mcp_it_pk_order"
        self.db.execute_write(f"DROP TABLE IF EXISTS {table}")
        self.db.execute_write(
            f"CREATE TABLE {table} (a INT NOT NULL, b INT NOT NULL, c INT NOT NULL, "
            f"CONSTRAINT pk_{table} PRIMARY KEY (c, a, b))"
        )
        try:
            desc = server.describe_table(table)
            assert desc["primary_key"] == ["c", "a", "b"]
            pk_index = next(i for i in desc["indexes"] if i["primary_key"])
            assert [k["name"] for k in pk_index["columns"]] == ["c", "a", "b"]
            cols = server.schema_definitions(table)
            assert [(c["name"], c["primary_key"]) for c in cols] == [
                ("a", True),
                ("b", True),
                ("c", True),
            ]
        finally:
            self.db.execute_write(f"DROP TABLE IF EXISTS {table}")

    def test_schema_definitions_unknown_table_raises(self) -> None:
        from cubrid_mcp_server import server

        with pytest.raises(ValueError):
            server.schema_definitions("definitely_not_a_real_table_xyz")

    def test_execute_query_tool(self) -> None:
        from cubrid_mcp_server import server

        result = server.execute_query("SELECT 1 + 1")
        assert result["rows"][0][0] == 2
        assert result["row_count"] == 1
        assert result["truncated"] is False

    def test_list_indexes_tool(self) -> None:
        from cubrid_mcp_server import server

        tables = server.all_table_names()
        if not tables:
            pytest.skip("no user tables")
        result = server.list_indexes(tables[0])
        assert isinstance(result, list)

    def test_table_row_counts_tool(self) -> None:
        from cubrid_mcp_server import server

        tables = server.all_table_names()
        if not tables:
            pytest.skip("no user tables")
        counts = server.table_row_counts([tables[0]])
        assert counts[0]["table"] == tables[0]

    def test_explain_query_tool(self) -> None:
        from cubrid_mcp_server import server

        explain = server.explain_query("SELECT COUNT(*) FROM db_class")
        assert "plan" in explain

    def test_concurrent_tool_calls_serialize_shared_session(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A contending query cannot interleave with a real trace session."""
        import pycubrid

        from cubrid_mcp_server import server

        connection = self.db.connect()
        generation = getattr(connection, "_physical_generation", None)
        trace_entered, query_entered, release_trace = Event(), Event(), Event()
        cursors: list[Any] = []
        real_cursor = connection.cursor
        real_trace = self.db.trace_enabled
        real_fetch_many = self.db.fetch_many

        def record_cursor() -> Any:
            cursor = real_cursor()
            cursors.append(cursor)
            return cursor

        @contextmanager
        def hold_trace() -> Iterator[Any]:
            # Enter the real context first: SET TRACE ON has executed and the
            # shared Database RLock remains held throughout this pause.
            with real_trace() as cursor:
                trace_entered.set()
                assert release_trace.wait(15), "trace holder was not released"
                yield cursor

        def entering_fetch_many(
            sql: str, params: tuple[Any, ...] | None = None, max_rows: int | None = None
        ) -> tuple[list[tuple[Any, ...]], bool]:
            query_entered.set()
            return real_fetch_many(sql, params, max_rows)

        monkeypatch.setattr(connection, "cursor", record_cursor)
        monkeypatch.setattr(self.db, "trace_enabled", hold_trace)
        monkeypatch.setattr(self.db, "fetch_many", entering_fetch_many)
        with ThreadPoolExecutor(max_workers=2) as pool:
            try:
                tracing = pool.submit(server.explain_query, "SELECT 1")
                assert trace_entered.wait(5), "explain_query did not enter trace context"
                querying = pool.submit(server.execute_query, "SELECT 2")
                assert query_entered.wait(5), "execute_query did not reach the database"
                with pytest.raises(FutureTimeoutError):
                    querying.result(timeout=0.25)
                assert len(cursors) == 1, "query acquired a cursor during the trace context"
            finally:
                release_trace.set()
            explain = tracing.result(timeout=10)
            query = querying.result(timeout=10)

        assert explain["sql"] == "SELECT 1"
        assert isinstance(explain["plan"], str) and explain["plan"]
        assert query == {"row_count": 1, "truncated": False, "rows": [[2]]}
        assert self.db.connect() is connection
        assert getattr(connection, "_physical_generation", None) == generation
        assert len(cursors) == 3, "trace, trace cleanup and query each own one cursor"
        for cursor in cursors:
            with pytest.raises(pycubrid.InterfaceError):
                cursor.fetchone()

    def _second_session(self) -> Any:
        """Open an independent pycubrid session (not the server's shared one)."""
        import pycubrid

        return pycubrid.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            connect_timeout=10,
            read_timeout=30,
        )

    def test_read_does_not_hold_locks_against_ddl(self) -> None:
        """A finished execute_query must not keep a lock that blocks another session's DDL."""
        from cubrid_mcp_server import server

        table = "mcp_it_read_txn_ddl"
        self.db.execute_write(f"DROP TABLE IF EXISTS {table}")
        self.db.execute_write(f"CREATE TABLE {table} (id INT PRIMARY KEY, v INT)")
        other = self._second_session()
        try:
            result = server.execute_query(f"SELECT id, v FROM {table}")
            assert result["row_count"] == 0
            cursor = other.cursor()
            # Fail fast instead of waiting if the shared session still holds a lock.
            cursor.execute("SET TRANSACTION LOCK TIMEOUT 2")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN extra INT")
            other.commit()
            cursor.close()
            # The shared connection survived and sees the new column.
            result = server.execute_query(f"SELECT id, v, extra FROM {table}")
            assert result["row_count"] == 0
        finally:
            other.close()
            self.db.execute_write(f"DROP TABLE IF EXISTS {table}")

    def test_next_read_sees_rows_committed_by_another_session(self) -> None:
        """Under REPEATABLE READ each execute_query starts a fresh snapshot."""
        from cubrid_mcp_server import server

        table = "mcp_it_read_txn_visibility"
        self.db.execute_write(f"DROP TABLE IF EXISTS {table}")
        self.db.execute_write(f"CREATE TABLE {table} (id INT PRIMARY KEY)")
        self.db.execute_write(f"INSERT INTO {table} VALUES (1)")
        connection = self.db.connect()
        setup = connection.cursor()
        setup.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        setup.close()
        connection.commit()
        other = self._second_session()
        try:
            count_sql = f"SELECT COUNT(*) FROM {table}"
            assert server.execute_query(count_sql)["rows"] == [[1]]
            cursor = other.cursor()
            cursor.execute(f"INSERT INTO {table} VALUES (2)")
            other.commit()
            cursor.close()
            assert server.execute_query(count_sql)["rows"] == [[2]]
            # Same shared session throughout: no reconnect hid a stale snapshot.
            assert self.db.connect() is connection
        finally:
            other.close()
            self.db.execute_write(f"DROP TABLE IF EXISTS {table}")

    def test_sql_error_keeps_shared_session(self) -> None:
        """A server-rejected statement rolls back but reuses the same connection."""
        from cubrid_mcp_server import server
        from cubrid_mcp_server.database import DatabaseError

        connection = self.db.connect()
        with pytest.raises(DatabaseError, match="query failed: ProgrammingError"):
            server.execute_query("SELECT * FROM mcp_it_definitely_missing_table")
        assert self.db.connect() is connection
        assert server.execute_query("SELECT 1 + 1")["rows"] == [[2]]
        assert self.db.connect() is connection

    def test_list_serials_tool(self) -> None:
        from cubrid_mcp_server import server

        serials = server.list_serials()
        assert isinstance(serials, list)

    def test_list_class_hierarchy_tool(self) -> None:
        from cubrid_mcp_server import server

        hierarchy = server.list_class_hierarchy()
        assert isinstance(hierarchy, list)

    def test_safety_blocks_write(self) -> None:
        from cubrid_mcp_server.safety import UnsafeSQLError, ensure_read_only

        with pytest.raises(UnsafeSQLError):
            ensure_read_only("DROP TABLE nonexistent")
