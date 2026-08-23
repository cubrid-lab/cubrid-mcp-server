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


# --- Edge cases locking in defense-in-depth behavior (issue #102) ---
#
# These document the *intended* behavior of the sqlparse-based checker. The
# checker is a UX guardrail, NOT a security boundary: database-level read-only
# grants are the real enforcement layer (see SECURITY.md). The cases below
# confirm that keyword-shaped text inside comments, string literals, and quoted
# identifiers does not cause false positives, while genuine mutating keywords
# (including inside CTEs, FOR UPDATE, and INTO) are rejected.


@pytest.mark.parametrize(
    "sql",
    [
        # Keywords inside block/line comments are stripped before scanning.
        "SELECT /* DROP TABLE x */ 1",
        "SELECT * FROM t -- DELETE FROM t\n",
        # Keywords inside string literals are tokenized as strings, not keywords.
        "SELECT 'DELETE FROM users' AS note",
        "SELECT 'DROP', 'INSERT' FROM t",
        # Quoted identifiers that happen to spell a forbidden keyword are names.
        'SELECT "into" FROM t',
        'SELECT "call" FROM t',
        # A column alias containing a forbidden word as a substring is fine.
        "SELECT col AS into_thing FROM t",
        # A function whose name embeds a forbidden keyword is a Name, not a keyword.
        "select insert_something(1) from t",
        # Ordinary read-only CTEs and function calls.
        "WITH x AS (SELECT 1) SELECT * FROM x",
        "SELECT COUNT(*) FROM t",
        "SELECT LENGTH(name) FROM t",
    ],
)
def test_ensure_read_only_allows_safe_edge_cases(sql: str) -> None:
    ensure_read_only(sql)


@pytest.mark.parametrize(
    "sql",
    [
        # A mutating statement hidden inside a CTE body is still rejected.
        "WITH x AS (DELETE FROM t RETURNING *) SELECT 1",
        # Row-level locking escapes read-only mode.
        "SELECT * FROM t FOR UPDATE",
        # SELECT ... INTO can write to files/variables and is rejected.
        "SELECT * INTO OUTFILE '/tmp/x' FROM t",
    ],
)
def test_ensure_read_only_rejects_hidden_writes(sql: str) -> None:
    with pytest.raises(UnsafeSQLError):
        ensure_read_only(sql)
