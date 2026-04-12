import pytest

from cubrid_mcp_server.safety import UnsafeSQLError, ensure_read_only


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "select * from users where id = 1",
        "SHOW TABLES",
        "DESC users",
        "DESCRIBE users",
        "EXPLAIN SELECT * FROM users",
        "WITH recent AS (SELECT * FROM users) SELECT * FROM recent",
        "  SELECT 1  ",
        "SELECT 1;",
    ],
)
def test_ensure_read_only_allows_read_statements(sql: str) -> None:
    ensure_read_only(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO users VALUES (1)",
        "UPDATE users SET name='x'",
        "DELETE FROM users",
        "DROP TABLE users",
        "TRUNCATE TABLE users",
        "CREATE TABLE t (id INT)",
        "ALTER TABLE users ADD COLUMN x INT",
        "GRANT SELECT ON users TO mcp",
    ],
)
def test_ensure_read_only_rejects_write_statements(sql: str) -> None:
    with pytest.raises(UnsafeSQLError):
        ensure_read_only(sql)


def test_ensure_read_only_rejects_multi_statement() -> None:
    with pytest.raises(UnsafeSQLError, match="multi-statement"):
        ensure_read_only("SELECT 1; SELECT 2")


def test_ensure_read_only_rejects_select_then_drop() -> None:
    with pytest.raises(UnsafeSQLError, match="multi-statement"):
        ensure_read_only("SELECT 1; DROP TABLE users")


@pytest.mark.parametrize("sql", ["", "   ", ";", "   ;  "])
def test_ensure_read_only_rejects_empty(sql: str) -> None:
    with pytest.raises(UnsafeSQLError, match="empty"):
        ensure_read_only(sql)
