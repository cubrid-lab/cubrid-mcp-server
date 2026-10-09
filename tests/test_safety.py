import pytest

from cubrid_mcp_server.safety import (
    QUERY_REJECTED_KEYWORDS,
    WRITE_KEYWORDS,
    UnsafeSQLError,
    ensure_query_statement,
    ensure_read_only,
)


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


# --- ensure_query_statement: execute_query with the whitelist disabled (#235) ---


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO users VALUES (1)",
        "insert into users values (1)",
        "UPDATE users SET name='x'",
        "DELETE FROM users",
        "REPLACE INTO users VALUES (1)",
        "MERGE INTO users USING src ON (1=1) WHEN MATCHED THEN UPDATE SET a=1",
        "CREATE TABLE x (a INT)",
        "ALTER TABLE users ADD COLUMN b INT",
        "DROP TABLE users",
        "TRUNCATE users",
        "RENAME TABLE users AS people",
        "GRANT SELECT ON users TO u",
        "REVOKE SELECT ON users FROM u",
        "COMMIT",
        "COMMIT WORK",
        "ROLLBACK",
        "SAVEPOINT s1",
        "SET TRANSACTION ISOLATION LEVEL 4",
        "/* note */ INSERT INTO users VALUES (1)",
        "-- note\nDELETE FROM users",
        "SELECT 1; DELETE FROM users",
    ],
)
def test_ensure_query_statement_rejects_write_ddl_and_tcl(sql: str) -> None:
    with pytest.raises(UnsafeSQLError, match="not permitted in execute_query.*execute_write"):
        ensure_query_statement(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "WITH recent AS (SELECT * FROM users) SELECT * FROM recent",
        "SHOW TABLES",
        "DESC users",
        "EXPLAIN SELECT * FROM users",
        "CALL my_proc()",
        "SELECT * FROM users FOR UPDATE",
    ],
)
def test_ensure_query_statement_allows_result_set_statements(sql: str) -> None:
    ensure_query_statement(sql)


@pytest.mark.parametrize("sql", ["", "   "])
def test_ensure_query_statement_rejects_empty(sql: str) -> None:
    with pytest.raises(UnsafeSQLError, match="empty"):
        ensure_query_statement(sql)


def test_query_rejected_keywords_cover_write_keywords() -> None:
    assert WRITE_KEYWORDS <= QUERY_REJECTED_KEYWORDS
