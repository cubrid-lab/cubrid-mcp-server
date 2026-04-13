"""Unit tests for cubrid_mcp_server.server tools with a mocked Database."""

from __future__ import annotations

from typing import Any

import pytest

from cubrid_mcp_server import server
from cubrid_mcp_server.config import Config

_TEST_CONFIG = Config(
    host="h", port=33000, user="u", password="", database="d",
    readonly=True, max_chars=4000,
)


class FakeDatabase:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.responses: list[list[tuple[Any, ...]]] = []

    def queue(self, rows: list[tuple[Any, ...]]) -> None:
        self.responses.append(rows)

    def fetch_all(
        self, sql: str, params: tuple[Any, ...] | None = None
    ) -> list[tuple[Any, ...]]:
        self.calls.append((sql, params or ()))
        if not self.responses:
            return []
        return self.responses.pop(0)


@pytest.fixture
def fake_db(monkeypatch: pytest.MonkeyPatch) -> FakeDatabase:
    fake = FakeDatabase()
    monkeypatch.setattr(server, "_db", lambda: fake)
    monkeypatch.setattr(server, "_config", _TEST_CONFIG)
    return fake


def test_all_table_names(fake_db: FakeDatabase) -> None:
    fake_db.queue([("users",), ("orders",)])
    assert server.all_table_names() == ["users", "orders"]


def test_filter_table_names(fake_db: FakeDatabase) -> None:
    fake_db.queue([("users",), ("orders",), ("user_roles",)])
    assert server.filter_table_names("user") == ["users", "user_roles"]


def test_filter_table_names_empty(fake_db: FakeDatabase) -> None:
    assert server.filter_table_names("   ") == []


def test_schema_definitions(fake_db: FakeDatabase) -> None:
    fake_db.queue(
        [
            ("id", "INTEGER", "NO", None),
            ("name", "VARCHAR", "YES", "''"),
        ]
    )
    fake_db.queue([("id",)])
    result = server.schema_definitions("users")
    assert result == [
        {
            "name": "id",
            "type": "INTEGER",
            "nullable": False,
            "default": None,
            "primary_key": True,
        },
        {
            "name": "name",
            "type": "VARCHAR",
            "nullable": True,
            "default": "''",
            "primary_key": False,
        },
    ]


def test_list_indexes_groups_columns(fake_db: FakeDatabase) -> None:
    fake_db.queue(
        [
            ("pk_users", "YES", "YES", "NO", "NO", 1, "id", 0, "ASC"),
            ("idx_name", "NO", "NO", "NO", "NO", 2, "last", 0, "ASC"),
            ("idx_name", "NO", "NO", "NO", "NO", 2, "first", 1, "ASC"),
        ]
    )
    result = server.list_indexes("users")
    assert result[0]["name"] == "pk_users"
    assert result[0]["primary_key"] is True
    assert result[0]["columns"] == [{"name": "id", "order": 0, "asc_desc": "ASC"}]
    assert result[1]["name"] == "idx_name"
    assert len(result[1]["columns"]) == 2


def test_describe_table(fake_db: FakeDatabase) -> None:
    fake_db.queue([("id", "INTEGER", "NO", None)])
    fake_db.queue([("id",)])
    fake_db.queue([("pk_users", "YES", "YES", "NO", "NO", 1, "id", 0, "ASC")])
    result = server.describe_table("users")
    assert result["table"] == "users"
    assert result["primary_key"] == ["id"]
    assert len(result["columns"]) == 1
    assert len(result["indexes"]) == 1


class FakeCursor:
    def __init__(self, parent: "FakeConnDatabase") -> None:
        self.parent = parent
        self.executed: list[str] = []
        self._fetch: list[tuple[Any, ...]] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        self.executed.append(sql)
        upper = sql.strip().upper()
        if upper.startswith("SET TRACE") or upper == "":
            self._fetch = []
        elif upper.startswith("SHOW TRACE"):
            self._fetch = [("\nTrace Statistics:\n  SELECT (time: 1)\n",)]
        else:
            self._fetch = [(1,)]

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._fetch


class FakeConnDatabase(FakeDatabase):
    def __init__(self) -> None:
        super().__init__()
        self.cursors: list[FakeCursor] = []
        self.rolled_back = False

    def cursor(self) -> Any:
        from contextlib import contextmanager

        @contextmanager
        def _cm() -> Any:
            cur = FakeCursor(self)
            self.cursors.append(cur)
            try:
                yield cur
            finally:
                pass

        return _cm()

    def connect(self) -> Any:
        outer = self

        class _Conn:
            def rollback(self_inner) -> None:
                outer.rolled_back = True

        return _Conn()


def test_explain_query_uses_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeConnDatabase()
    monkeypatch.setattr(server, "_db", lambda: fake)
    monkeypatch.setattr(server, "_config", _TEST_CONFIG)
    result = server.explain_query("SELECT 1")
    assert result["sql"] == "SELECT 1"
    assert "Trace Statistics" in result["plan"]
    executed = [s for cur in fake.cursors for s in cur.executed]
    assert any("SET TRACE ON" in s for s in executed)
    assert any("SHOW TRACE" in s for s in executed)
    assert any("SET TRACE OFF" in s for s in executed)
    assert fake.rolled_back is True


def test_explain_query_rejects_non_select(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_db", lambda: FakeConnDatabase())
    monkeypatch.setattr(server, "_config", _TEST_CONFIG)
    with pytest.raises(ValueError):
        server.explain_query("DROP TABLE users")


def test_explain_query_rejects_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_db", lambda: FakeConnDatabase())
    monkeypatch.setattr(server, "_config", _TEST_CONFIG)
    with pytest.raises(ValueError):
        server.explain_query("   ")


def test_table_row_counts_explicit(fake_db: FakeDatabase) -> None:
    fake_db.queue([(42,)])
    fake_db.queue([(7,)])
    result = server.table_row_counts(["users", "orders"])
    assert result == [
        {"table": "users", "row_count": 42},
        {"table": "orders", "row_count": 7},
    ]


def test_table_row_counts_defaults_to_all(fake_db: FakeDatabase) -> None:
    fake_db.queue([("users",)])
    fake_db.queue([(3,)])
    result = server.table_row_counts()
    assert result == [{"table": "users", "row_count": 3}]


def test_list_serials(fake_db: FakeDatabase) -> None:
    fake_db.queue(
        [
            (
                "order_seq",
                100,
                1,
                9999999,
                1,
                0,
                1,
                "orders",
                "id",
                10,
                "order pk",
            )
        ]
    )
    result = server.list_serials()
    assert result[0]["name"] == "order_seq"
    assert result[0]["current_value"] == 100
    assert result[0]["started"] is True
    assert result[0]["cyclic"] is False


def test_list_class_hierarchy_all(fake_db: FakeDatabase) -> None:
    fake_db.queue([("child", "parent"), ("child", "mixin"), ("grand", "child")])
    result = server.list_class_hierarchy()
    assert {r["class_name"] for r in result} == {"child", "grand"}
    child = next(r for r in result if r["class_name"] == "child")
    assert set(child["super_classes"]) == {"parent", "mixin"}


def test_list_class_hierarchy_single(fake_db: FakeDatabase) -> None:
    fake_db.queue([("users", "base")])
    result = server.list_class_hierarchy("users")
    assert result == [{"class_name": "users", "super_classes": ["base"]}]
    assert fake_db.calls[0][1] == ("users",)


def test_execute_query_renders_and_truncates(
    fake_db: FakeDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = Config(
        host="h", port=33000, user="u", password="", database="d",
        readonly=True, max_chars=10,
    )
    monkeypatch.setattr(server, "_config", cfg)
    fake_db.queue([("short",), ("a-much-longer-row",)])
    result = server.execute_query("SELECT 1")
    assert result["row_count"] == 2
    assert result["truncated"] is True
