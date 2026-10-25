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


FIXTURE_TABLE = "mcp_it_fixture"


@pytest.fixture(scope="module")
def fixture_table() -> Iterator[str]:
    """A disposable user table, so the table-dependent tests always run (#403)."""
    if not _has_cubrid_env():
        yield FIXTURE_TABLE
        return
    from cubrid_mcp_server.config import Config
    from cubrid_mcp_server.database import Database

    config = Config.from_env()
    db = Database(config)
    try:
        db.execute_write(f"DROP TABLE IF EXISTS {FIXTURE_TABLE}")
        db.execute_write(f"CREATE TABLE {FIXTURE_TABLE} (id INT PRIMARY KEY, label VARCHAR(20))")
        db.execute_write(f"INSERT INTO {FIXTURE_TABLE} VALUES (?, ?)", (1, "first"))
        # The name the tools list: owner-qualified from CUBRID 11.2 on.
        qualified = db.owner_qualified_names()
        yield f"{config.user.lower()}.{FIXTURE_TABLE}" if qualified else FIXTURE_TABLE
    finally:
        try:
            db.execute_write(f"DROP TABLE IF EXISTS {FIXTURE_TABLE}")
        finally:
            db.close()


@skipif_no_cubrid
class TestCubridIntegration:
    def setup_method(self) -> None:
        from cubrid_mcp_server import server
        from cubrid_mcp_server.config import Config
        from cubrid_mcp_server.database import Database

        from tests.helpers import single_context

        self.config = Config.from_env()
        self.db = Database(self.config)
        # Route the server tool functions at the live database.
        server._context = single_context(config=self.config, database=self.db)

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

    def test_filter_table_names_tool(self, fixture_table: str) -> None:
        from cubrid_mcp_server import server

        tables = server.all_table_names()
        assert fixture_table in tables
        needle = fixture_table[:2]
        filtered = server.filter_table_names(needle)
        assert fixture_table in filtered

    def test_schema_definitions_tool(self, fixture_table: str) -> None:
        from cubrid_mcp_server import server

        tables = server.all_table_names()
        assert fixture_table in tables
        cols = server.schema_definitions(fixture_table)
        assert isinstance(cols, list)
        assert all("name" in c and "type" in c for c in cols)

    def test_describe_table_tool(self, fixture_table: str) -> None:
        from cubrid_mcp_server import server

        tables = server.all_table_names()
        assert fixture_table in tables
        desc = server.describe_table(fixture_table)
        assert desc["table"] == fixture_table
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

    def test_list_indexes_tool(self, fixture_table: str) -> None:
        from cubrid_mcp_server import server

        tables = server.all_table_names()
        assert fixture_table in tables
        result = server.list_indexes(fixture_table)
        assert isinstance(result, list)

    def test_table_row_counts_tool(self, fixture_table: str) -> None:
        from cubrid_mcp_server import server

        tables = server.all_table_names()
        assert fixture_table in tables
        counts = server.table_row_counts([fixture_table])
        assert counts["tables"][0]["table"] == fixture_table
        assert counts["truncated"] is False

    def test_table_row_counts_default_caps_beyond_limit(self) -> None:
        """With no table_names on a >limit-table database, count the first limit (#239).

        The limit is ``CUBRID_MCP_MAX_ROW_COUNT_TABLES`` (default 50), so the test also
        holds when the live lane runs with a non-default value (#430).
        """
        from cubrid_mcp_server import server

        limit = server._cfg().max_row_count_tables
        created = [f"mcp_it_rc_{i:03d}" for i in range(limit + 1)]
        try:
            for table in created:
                self.db.execute_write(f"DROP TABLE IF EXISTS {table}")
                self.db.execute_write(f"CREATE TABLE {table} (id INT)")
            every = server.all_table_names()
            result = server.table_row_counts()
            assert result["truncated"] is True
            assert result["total_tables"] == len(every)
            assert [r["table"] for r in result["tables"]] == sorted(every)[:limit]
            assert all(r.get("error") is None for r in result["tables"])
            with pytest.raises(ValueError, match="too many tables requested"):
                server.table_row_counts(created)
        finally:
            for table in created:
                self.db.execute_write(f"DROP TABLE IF EXISTS {table}")

    def test_configured_connect_timeout_and_output_limits(self, fixture_table: str) -> None:
        """The #430 settings parsed from the environment reach a live session."""
        from cubrid_mcp_server import server
        from cubrid_mcp_server.config import Config
        from cubrid_mcp_server.database import Database

        from tests.helpers import single_context

        config = Config.from_env(
            dict(os.environ)
            | {
                "CUBRID_MCP_CONNECT_TIMEOUT": "5",
                "CUBRID_MCP_MAX_ROW_COUNT_TABLES": "1",
                "CUBRID_MCP_MAX_INLINE_BINARY_BYTES": "2",
            }
        )
        db = Database(config)
        server._context = single_context(config=config, database=db)
        try:
            assert server.health_check()["ok"] is True
            result = server.table_row_counts()
            assert len(result["tables"]) == 1
            assert result["truncated"] is (result["total_tables"] > 1)
            with pytest.raises(ValueError, match="limit is 1 per call"):
                server.table_row_counts([fixture_table, fixture_table])
            rows = server.execute_query("SELECT X'0102', X'010203'")["rows"]
            assert rows == [["AQI=", "<binary 3 bytes>"]]
        finally:
            db.close()

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

    def test_execute_query_rejects_insert_with_whitelist_off(self) -> None:
        """With CUBRID_MCP_READONLY=0, execute_query still refuses writes (#235)."""
        from dataclasses import replace

        from cubrid_mcp_server import server
        from tests.helpers import single_context
        from cubrid_mcp_server.safety import UnsafeSQLError

        table = "mcp_it_query_readonly"
        self.db.execute_write(f"DROP TABLE IF EXISTS {table}")
        self.db.execute_write(f"CREATE TABLE {table} (id INT PRIMARY KEY)")
        self.db.execute_write(f"INSERT INTO {table} VALUES (1)")
        server._context = single_context(
            config=replace(self.config, readonly=False), database=self.db
        )
        other = self._second_session()
        try:
            connection = self.db.connect()
            with pytest.raises(UnsafeSQLError, match="execute_write"):
                server.execute_query(f"INSERT INTO {table} VALUES (2)")
            cursor = other.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            assert cursor.fetchall() == [(1,)]
            cursor.close()
            other.rollback()
            # Result-set reads still work, on the same shared session.
            count_sql = f"SELECT COUNT(*) FROM {table}"
            assert server.execute_query(count_sql)["rows"] == [[1]]
            assert self.db.connect() is connection
        finally:
            other.close()
            self.db.execute_write(f"DROP TABLE IF EXISTS {table}")

    def test_session_user_cannot_change_through_any_tool(self) -> None:
        """CALL login, EVALUATE and KILL are rejected with the whitelist off (#297).

        The control call below shows that ``CALL login(...) ON CLASS db_user``
        switches a session to the given user; through the tools it never runs,
        so the shared session keeps its user for every later call.
        """
        from dataclasses import replace

        import pycubrid

        from cubrid_mcp_server import server
        from tests.helpers import single_context
        from cubrid_mcp_server.database import Database
        from cubrid_mcp_server.safety import UnsafeSQLError

        user = "mcp_it_login_user"
        owner, owner_password = self.config.user, self.config.password or ""
        login = f"CALL login('{owner}', '{owner_password}') ON CLASS db_user"
        admin = self._second_session()
        try:
            cursor = admin.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM db_user WHERE name = '{user.upper()}'")
            if cursor.fetchall()[0][0]:
                cursor.execute(f"DROP USER {user}")
            cursor.execute(f"CREATE USER {user} PASSWORD 'pw297'")
            admin.commit()

            # Control: sent directly, CALL login changes the session user.
            limited = pycubrid.connect(
                host=self.config.host,
                port=self.config.port,
                user=user,
                password="pw297",
                database=self.config.database,
                connect_timeout=10,
                read_timeout=30,
            )
            try:
                limited_cursor = limited.cursor()
                limited_cursor.execute(login)
                limited_cursor.fetchall()
                limited_cursor.execute("SELECT CURRENT_USER")
                assert limited_cursor.fetchall() == [(owner.upper(),)]
            finally:
                limited.close()

            config = replace(
                self.config, user=user, password="pw297", readonly=False, write_enabled=True
            )
            database = Database(config)
            server._context = single_context(config=config, database=database)
            try:
                for sql in (
                    login,
                    f"call LOGIN('{owner}', '{owner_password}') on class [db_user]",
                    f"EVALUATE login('{owner}', '{owner_password}') ON CLASS db_user",
                    "EVALUATE 1 + 1",
                    "KILL 999999",
                ):
                    with pytest.raises(UnsafeSQLError, match="not permitted in execute_query"):
                        server.execute_query(sql)
                    # sqlparse finds no keyword in KILL or EVALUATE statements.
                    with pytest.raises(UnsafeSQLError, match="write mode|leading SQL keyword"):
                        server.execute_write(sql)
                    with pytest.raises(ValueError, match="only accepts SELECT or WITH"):
                        server.explain_query(sql)
                assert server.execute_query("SELECT CURRENT_USER")["rows"] == [[user.upper()]]
            finally:
                database.close()
        finally:
            cursor = admin.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM db_user WHERE name = '{user.upper()}'")
            if cursor.fetchall()[0][0]:
                cursor.execute(f"DROP USER {user}")
            admin.commit()
            admin.close()

    def test_execute_query_caps_a_wide_first_row(self) -> None:
        """A wide first row stays within CUBRID_MCP_MAX_CHARS and is flagged (#298)."""
        from dataclasses import replace

        from cubrid_mcp_server import server
        from tests.helpers import single_context

        server._context = single_context(
            config=replace(self.config, max_chars=4000), database=self.db
        )
        columns = ", ".join(f"REPEAT('x', 3990) AS c{i}" for i in range(60))
        result = server.execute_query(f"SELECT {columns}")
        assert result["row_count"] == 1
        assert result["truncated"] is True
        (row,) = result["rows"]
        assert len(row) == 60
        assert row[0] == "x" * 3990
        assert sum(len(value) for value in row) <= 4000 + 58

    def test_metadata_tools_tell_owners_apart(self) -> None:
        """Two owners' tables with one name stay apart on CUBRID 11.2 and later (#296)."""
        from dataclasses import replace

        import pycubrid

        from cubrid_mcp_server import server
        from tests.helpers import single_context
        from cubrid_mcp_server.database import Database

        if not self.db.owner_qualified_names():
            pytest.skip("table names are unique per database before CUBRID 11.2")
        table, other, reader = "mcp_it_owned", "mcp_it_owner_other", "mcp_it_owner_reader"
        owner = self.config.user.lower()
        admin = self._second_session()

        def drop_users() -> None:
            cursor = admin.cursor()
            cursor.execute(f"DROP TABLE IF EXISTS {other}.{table}")
            for user in (other, reader):
                cursor.execute(f"SELECT COUNT(*) FROM db_user WHERE name = '{user.upper()}'")
                if cursor.fetchall()[0][0]:
                    cursor.execute(f"DROP USER {user}")
            admin.commit()

        try:
            drop_users()
            cursor = admin.cursor()
            for sql in (
                f"DROP TABLE IF EXISTS {table}",
                f"CREATE TABLE {table} (id INT PRIMARY KEY, a INT)",
                f"INSERT INTO {table} VALUES (1, 1)",
                f"CREATE USER {other} PASSWORD 'pw296'",
                f"CREATE USER {reader} PASSWORD 'pw296'",
                f"GRANT SELECT ON {table} TO {reader}",
            ):
                cursor.execute(sql)
            admin.commit()
            other_session = pycubrid.connect(
                host=self.config.host,
                port=self.config.port,
                user=other,
                password="pw296",
                database=self.config.database,
                connect_timeout=10,
                read_timeout=30,
            )
            try:
                other_cursor = other_session.cursor()
                other_cursor.execute(
                    f"CREATE TABLE {table} (zz INT PRIMARY KEY, secret VARCHAR(10))"
                )
                other_cursor.execute(f"INSERT INTO {table} VALUES (5, 's'), (6, 't')")
                other_cursor.execute(f"GRANT SELECT ON {table} TO {reader}")
                other_session.commit()
            finally:
                other_session.close()

            config = replace(self.config, user=reader, password="pw296")
            database = Database(config)
            server._context = single_context(config=config, database=database)
            mine, theirs = f"{owner}.{table}", f"{other}.{table}"
            try:
                names = server.all_table_names()
                assert mine in names and theirs in names
                assert table not in names
                described = server.describe_table(theirs.upper())
                assert described["table"] == theirs
                assert [c["name"] for c in described["columns"]] == ["zz", "secret"]
                assert described["primary_key"] == ["zz"]
                assert [c["name"] for c in server.schema_definitions(mine)] == ["id", "a"]
                assert [i["columns"][0]["name"] for i in server.list_indexes(mine)] == ["id"]
                with pytest.raises(ValueError, match="ambiguous table name"):
                    server.describe_table(table)
                counts = server.table_row_counts([mine, theirs, table])["tables"]
                assert counts[0] == {"table": mine, "row_count": 1}
                assert counts[1] == {"table": theirs, "row_count": 2}
                assert counts[2]["row_count"] is None
                assert "ambiguous" in counts[2]["error"]
            finally:
                database.close()
        finally:
            admin.cursor().execute(f"DROP TABLE IF EXISTS {table}")
            admin.commit()
            drop_users()
            admin.close()

    def test_explain_query_matches_execute_query(self) -> None:
        """Leading keyword, kept session and plan cap in explain_query (#299)."""
        from dataclasses import replace

        from cubrid_mcp_server import server
        from tests.helpers import single_context
        from cubrid_mcp_server.database import DatabaseError

        for sql in ("SELECT*FROM db_root", "(SELECT 1)"):
            assert server.explain_query(sql)["sql"] == sql
        connection = self.db.connect()
        with pytest.raises(DatabaseError, match="query failed: ProgrammingError"):
            server.explain_query("SELECT * FROM mcp_it_definitely_missing_table")
        assert self.db.connect() is connection
        assert "plan" in server.explain_query("SELECT 1")
        assert self.db.connect() is connection
        server._context = single_context(
            config=replace(self.config, max_chars=20), database=self.db
        )
        result = server.explain_query("SELECT * FROM db_class")
        assert result["truncated"] is True
        assert len(result["plan"]) == 20

    def test_list_serials_tool(self) -> None:
        from cubrid_mcp_server import server

        serials = server.list_serials()
        assert isinstance(serials, list)

    def test_list_class_hierarchy_tool(self) -> None:
        from cubrid_mcp_server import server

        hierarchy = server.list_class_hierarchy()
        assert isinstance(hierarchy, list)

    def test_list_class_hierarchy_resolves_table_name(self) -> None:
        """Mixed-case names resolve like other schema tools; unknown names raise (#240)."""
        from cubrid_mcp_server import server

        parent, child = "mcp_it_hier_parent", "mcp_it_hier_child"
        self.db.execute_write(f"DROP TABLE IF EXISTS {child}")
        self.db.execute_write(f"DROP TABLE IF EXISTS {parent}")
        try:
            self.db.execute_write(f"CREATE TABLE {parent} (id INT)")
            self.db.execute_write(f"CREATE TABLE {child} UNDER {parent} (extra INT)")
            result = server.list_class_hierarchy(child.upper())
            # Owner-qualified from CUBRID 11.2 on (#296).
            prefix = f"{self.config.user.lower()}." if self.db.owner_qualified_names() else ""
            assert result == [{"class_name": prefix + child, "super_classes": [prefix + parent]}]
            with pytest.raises(ValueError, match="unknown table"):
                server.list_class_hierarchy("mcp_it_hier_missing")
        finally:
            self.db.execute_write(f"DROP TABLE IF EXISTS {child}")
            self.db.execute_write(f"DROP TABLE IF EXISTS {parent}")

    def test_explain_statement_rejected(self) -> None:
        """CUBRID has no EXPLAIN statement; execute_query rejects it up front (#250)."""
        from cubrid_mcp_server import server
        from cubrid_mcp_server.database import DatabaseError
        from cubrid_mcp_server.safety import UnsafeSQLError

        # The server itself rejects EXPLAIN as a syntax error...
        with pytest.raises(DatabaseError, match="ProgrammingError"):
            self.db.fetch_all("EXPLAIN SELECT 1")
        # ...so the read-only whitelist no longer admits it; plans come from explain_query.
        with pytest.raises(UnsafeSQLError):
            server.execute_query("EXPLAIN SELECT 1")
        assert "plan" in server.explain_query("SELECT 1")

    def test_default_read_only_execute_query_rejects_write(self, fixture_table: str) -> None:
        """A write through the default read-only execute_query is rejected, data unchanged (#403)."""
        from cubrid_mcp_server import server
        from cubrid_mcp_server.safety import UnsafeSQLError

        assert self.config.readonly is True
        for sql in (
            f"INSERT INTO {fixture_table} VALUES (2, 'second')",
            f"UPDATE {fixture_table} SET label = 'changed'",
            f"DELETE FROM {fixture_table}",
            f"DROP TABLE {fixture_table}",
        ):
            with pytest.raises(UnsafeSQLError):
                server.execute_query(sql)
        rows = server.execute_query(f"SELECT id, label FROM {fixture_table} ORDER BY id")["rows"]
        assert rows == [[1, "first"]]

    def test_safety_blocks_write(self) -> None:
        from cubrid_mcp_server.safety import UnsafeSQLError, ensure_read_only

        with pytest.raises(UnsafeSQLError):
            ensure_read_only("DROP TABLE nonexistent")

    def test_select_only_user_cannot_change_data_through_read_tools(self) -> None:
        """INCR, DECR, serial advances and the click counter are rejected (#295).

        A SELECT-only grant does not stop them: the control query below changes
        data as that user. Both read tools reject every form before execution,
        and so does execute_query with CUBRID_MCP_READONLY=0 (#301).
        """
        from dataclasses import replace

        import pycubrid

        from cubrid_mcp_server import server
        from tests.helpers import single_context
        from cubrid_mcp_server.database import Database, DatabaseError
        from cubrid_mcp_server.safety import UnsafeSQLError

        table, serial, user = "mcp_it_side_effects", "mcp_it_side_serial", "mcp_it_select_only"
        owner = self.config.user
        for sql in (
            f"DROP TABLE IF EXISTS {table}",
            f"DROP SERIAL IF EXISTS {serial}",
            f"CREATE TABLE {table} (id INT PRIMARY KEY, cnt INT)",
            f"INSERT INTO {table} VALUES (1, 10)",
            f"CREATE SERIAL {serial} START WITH 100",
        ):
            self.db.execute_write(sql)
        admin = self._second_session()
        try:
            cursor = admin.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM db_user WHERE name = '{user.upper()}'")
            if cursor.fetchall()[0][0]:
                cursor.execute(f"DROP USER {user}")
            cursor.execute(f"CREATE USER {user} PASSWORD 'pw295'")
            cursor.execute(f"GRANT SELECT ON {table} TO {user}")
            # Start the serial so later NEXT_VALUE calls visibly advance it.
            cursor.execute(f"SELECT {serial}.NEXT_VALUE")
            # Serials are owner-qualified from CUBRID 11.2 on, and global before it.
            cursor.execute("SELECT VERSION()")
            version = tuple(int(part) for part in str(cursor.fetchall()[0][0]).split(".")[:2])
            serial_ref = f"{owner}.{serial}" if version >= (11, 2) else serial
            admin.commit()

            def state() -> tuple[Any, Any]:
                cursor.execute(f"SELECT cnt FROM {table} WHERE id = 1")
                cnt = cursor.fetchall()[0][0]
                cursor.execute(f"SELECT current_val FROM db_serial WHERE name = '{serial}'")
                current = cursor.fetchall()[0][0]
                admin.commit()
                return cnt, int(current)

            # Control: sent directly, INCR and NEXT_VALUE change data as the
            # SELECT-only user, and the rollback does not undo either change.
            limited = pycubrid.connect(
                host=self.config.host,
                port=self.config.port,
                user=user,
                password="pw295",
                database=self.config.database,
                connect_timeout=10,
                read_timeout=30,
            )
            try:
                before = state()
                limited_cursor = limited.cursor()
                limited_cursor.execute(f"SELECT INCR(cnt) FROM {owner}.{table} WHERE id = 1")
                limited_cursor.fetchall()
                limited_cursor.execute(f"SELECT {serial_ref}.NEXT_VALUE")
                limited_cursor.fetchall()
                limited.rollback()
                assert state() == (before[0] + 1, before[1] + 1)
            finally:
                limited.close()

            config = replace(self.config, user=user, password="pw295", readonly=True)
            database = Database(config)
            server._context = single_context(config=config, database=database)
            # The same session with the whitelist off, for execute_query (#301).
            whitelist_off = single_context(
                config=replace(config, readonly=False), database=database
            )
            read_only = server._context
            qualified = f"{owner}.{table}"
            forms = [
                f"SELECT INCR(cnt) FROM {qualified} WHERE id = 1",
                f"SELECT incr /* c */ (cnt) FROM {qualified} WHERE id = 1",
                f"SELECT [incr](cnt) FROM {qualified} WHERE id = 1",
                f"SELECT DECR(cnt) FROM {qualified} WHERE id = 1",
                f"SELECT * FROM {qualified} WHERE id = 1 WITH INCREMENT FOR cnt",
                f"SELECT * FROM {qualified} WHERE id = 1 WITH DECREMENT FOR cnt",
                f"SELECT {serial_ref}.NEXT_VALUE",
                f"SELECT {serial_ref} . next_value",
                f"SELECT {serial_ref}.NEXTVAL",
                f"SELECT SERIAL_NEXT_VALUE({serial_ref}, 3)",
                f"SELECT (SELECT {serial_ref}.NEXT_VALUE) FROM {qualified}",
            ]
            try:
                before = state()
                for sql in forms:
                    with pytest.raises(UnsafeSQLError, match="not permitted in read-only mode"):
                        server.execute_query(sql)
                    with pytest.raises(UnsafeSQLError, match="not permitted in read-only mode"):
                        server.explain_query(sql)
                    server._context = whitelist_off
                    try:
                        with pytest.raises(UnsafeSQLError, match="not permitted in execute_query"):
                            server.execute_query(sql)
                    finally:
                        server._context = read_only
                assert state() == before
                # '#incr' is one name, not '#' + INCR (#303): the check lets it
                # through and the server rejects it as an undefined function.
                with pytest.raises(DatabaseError, match="ProgrammingError"):
                    server.execute_query(f"SELECT #incr(cnt) FROM {qualified} WHERE id = 1")
                # Reading the serial and the table still works for this user.
                current = server.execute_query(f"SELECT {serial_ref}.CURRENT_VALUE")["rows"]
                assert int(current[0][0]) == before[1]
                rows = server.execute_query(f"SELECT cnt FROM {qualified} WHERE id = 1")["rows"]
                assert rows == [[before[0]]]
                assert state() == before
            finally:
                database.close()
        finally:
            cursor = admin.cursor()
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            cursor.execute(f"DROP SERIAL IF EXISTS {serial}")
            cursor.execute(f"SELECT COUNT(*) FROM db_user WHERE name = '{user.upper()}'")
            if cursor.fetchall()[0][0]:
                cursor.execute(f"DROP USER {user}")
            admin.commit()
            admin.close()
