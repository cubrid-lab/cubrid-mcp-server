"""Integration tests against a real CUBRID instance.

Run with: pytest -m integration
Requires CUBRID_HOST, CUBRID_USER, CUBRID_PASSWORD, CUBRID_DATABASE env vars.
"""

from __future__ import annotations

import os

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
        from cubrid_mcp_server.config import Config
        from cubrid_mcp_server.database import Database

        self.config = Config.from_env()
        self.db = Database(self.config)

    def teardown_method(self) -> None:
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
        rows = self.db.fetch_all(
            "SELECT class_name FROM db_class WHERE is_system_class = 'NO' ORDER BY class_name"
        )
        tables = [r[0] for r in rows]
        assert isinstance(tables, list)

    def test_schema_definitions_tool(self) -> None:
        rows = self.db.fetch_all(
            "SELECT class_name FROM db_class WHERE is_system_class = 'NO' LIMIT 1"
        )
        if not rows:
            pytest.skip("no user tables in database")
        table = rows[0][0]
        cols = self.db.fetch_all(
            "SELECT a.attr_name, a.data_type FROM db_attribute a "
            "WHERE a.class_name = ? ORDER BY a.def_order",
            (table,),
        )
        assert len(cols) > 0

    def test_execute_query_tool(self) -> None:
        rows = self.db.fetch_all("SELECT 1 + 1")
        assert rows[0][0] == 2

    def test_list_indexes_query(self) -> None:
        rows = self.db.fetch_all(
            "SELECT class_name FROM db_class WHERE is_system_class='NO' LIMIT 1"
        )
        if not rows:
            pytest.skip("no user tables")
        table = rows[0][0]
        result = self.db.fetch_all(
            "SELECT i.index_name, i.is_unique, i.is_primary_key, i.is_foreign_key, "
            "i.is_reverse, i.key_count, k.key_attr_name, k.key_order, k.asc_desc "
            "FROM db_index i, db_index_key k "
            "WHERE i.class_name = ? AND i.index_name = k.index_name "
            "AND i.class_name = k.class_name "
            "ORDER BY i.index_name, k.key_order",
            (table,),
        )
        assert isinstance(result, list)

    def test_list_serials_query(self) -> None:
        rows = self.db.fetch_all(
            "SELECT name, current_val, increment_val, max_val, min_val, "
            "cyclic, started, class_name, att_name, cached_num, comment "
            "FROM db_serial ORDER BY name"
        )
        assert isinstance(rows, list)

    def test_list_class_hierarchy_query(self) -> None:
        rows = self.db.fetch_all(
            "SELECT class_name, super_class_name FROM db_direct_super_class "
            "ORDER BY class_name LIMIT 5"
        )
        assert isinstance(rows, list)

    def test_v01_tools_via_server(self) -> None:
        from cubrid_mcp_server import server

        server._database = self.db
        server._config = self.config
        try:
            tables = server.all_table_names()
            assert isinstance(tables, list)
            if tables:
                desc = server.describe_table(tables[0])
                assert desc["table"] == tables[0]
                assert "columns" in desc and "indexes" in desc
                idx = server.list_indexes(tables[0])
                assert isinstance(idx, list)
                counts = server.table_row_counts([tables[0]])
                assert counts[0]["table"] == tables[0]
            explain = server.explain_query("SELECT COUNT(*) FROM db_class")
            assert "plan" in explain
            assert "SELECT" in explain["plan"] or explain["plan"] == ""
            serials = server.list_serials()
            assert isinstance(serials, list)
            hierarchy = server.list_class_hierarchy()
            assert isinstance(hierarchy, list)
        finally:
            server._database = None
            server._config = None

    def test_safety_blocks_write(self) -> None:
        from cubrid_mcp_server.safety import UnsafeSQLError, ensure_read_only

        with pytest.raises(UnsafeSQLError):
            ensure_read_only("DROP TABLE nonexistent")
