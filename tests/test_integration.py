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
