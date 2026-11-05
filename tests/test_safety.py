from typing import Any

import pytest

from cubrid_mcp_server.safety import (
    QUERY_REJECTED_KEYWORDS,
    WRITE_KEYWORDS,
    UnsafeSQLError,
    ensure_query_statement,
    ensure_read_only,
    ensure_write_allowed,
    strip_comments,
)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "select * from users where id = 1",
        "SHOW TABLES",
        "DESC users",
        "DESCRIBE users",
        "WITH recent AS (SELECT * FROM users) SELECT * FROM recent",
        "  SELECT 1  ",
        "SELECT 1;",
    ],
)
def test_ensure_read_only_allows_read_statements(sql: str) -> None:
    ensure_read_only(sql)


@pytest.mark.parametrize("sql", ["EXPLAIN SELECT * FROM users", "explain select 1"])
def test_ensure_read_only_rejects_explain(sql: str) -> None:
    # CUBRID 11.4 has no EXPLAIN statement (it is a syntax error at the server);
    # plans come from the explain_query tool (SET TRACE / SHOW TRACE) instead.
    with pytest.raises(UnsafeSQLError):
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


# --- ensure_query_statement: execute_query with the whitelist disabled ---
#
# CUBRID_MCP_READONLY=0 relaxes the read-only whitelist so execute_query can run
# other result-set reads, but execute_query must still never write: writes, DDL
# and transaction control are rejected and point the caller to execute_write,
# which has its own opt-in gate (CUBRID_MCP_WRITE=1). A leading comment must not
# hide the real statement (#235).


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
        "PREPARE s FROM 'DELETE FROM users'",
        "EXECUTE s",
        "DEALLOCATE PREPARE s",
        "DO 1",
        # Method calls and session control are rejected too: CALL and EVALUATE run
        # methods, CALL login(...) ON CLASS db_user switches the user of the shared
        # session for every later tool call, and KILL ends other sessions'
        # transactions (#297).
        "CALL my_proc()",
        "CALL login('dba', '') ON CLASS db_user",
        "call login('dba', '') on class db_user",
        "/* note */ CALL login('dba', '') ON CLASS [db_user]",
        "EVALUATE 1 + 1",
        "evaluate login('dba', '') ON CLASS db_user",
        "-- note\nEVALUATE 1",
        "KILL 3",
        "KILL QUERY 3",
        "kill transaction 3",
        "/* note */ KILL 3",
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
        "SELECT * FROM users FOR UPDATE",
        # Names that only start like a rejected keyword, and a column named kill.
        "SELECT call_count FROM users",
        "SELECT kill FROM users",
        # GET only reads a server setting (it returns no result set, so the
        # database read path rejects it after the keyword check).
        "GET OPTIMIZATION LEVEL",
    ],
)
def test_ensure_query_statement_allows_result_set_statements(sql: str) -> None:
    ensure_query_statement(sql)


@pytest.mark.parametrize(
    ("sql", "keyword"),
    [
        ("CREATE TABLE x (a INT)", "CREATE"),
        ("CREATE OR REPLACE VIEW v AS SELECT 1", "CREATE"),
        ("create or replace procedure p() as begin null; end", "CREATE"),
        ("CREATE UNIQUE INDEX i ON users (a)", "CREATE"),
        ("DROP TABLE IF EXISTS users", "DROP"),
        ("ALTER TABLE users ADD COLUMN b INT", "ALTER"),
        # sqlparse reads KILL and EVALUATE as names; the first word still counts.
        ("KILL 3", "KILL"),
        ("EVALUATE 1", "EVALUATE"),
        ("CALL login('dba', '') ON CLASS db_user", "CALL"),
    ],
)
def test_ensure_query_statement_matches_first_word_of_leading_keyword(
    sql: str, keyword: str
) -> None:
    with pytest.raises(UnsafeSQLError, match=f"^{keyword} is not permitted in execute_query"):
        ensure_query_statement(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; DELETE FROM users",
        "SELECT 1; SELECT 2",
        "SELECT 1;\nSELECT 2;",
    ],
)
def test_ensure_query_statement_rejects_multi_statement(sql: str) -> None:
    with pytest.raises(UnsafeSQLError, match="multi-statement SQL is not allowed in execute_query"):
        ensure_query_statement(sql)


def test_ensure_query_statement_allows_trailing_semicolon() -> None:
    ensure_query_statement("SELECT 1;")


def test_ensure_query_statement_strips_comments_before_matching() -> None:
    # Without strip_comments a trailing block comment would count as a second
    # statement, and comment-only input would not count as empty.
    ensure_query_statement("SELECT 1; /* note */")
    with pytest.raises(UnsafeSQLError, match="empty"):
        ensure_query_statement("/* SELECT 1 */")


@pytest.mark.parametrize("sql", ["", "   ", "-- only a comment", "/* c */", ";", " ; ;"])
def test_ensure_query_statement_rejects_empty(sql: str) -> None:
    with pytest.raises(UnsafeSQLError, match="empty"):
        ensure_query_statement(sql)


@pytest.mark.parametrize(
    ("checker", "sql", "word"),
    [
        # sqlparse reads KILL, EVALUATE and other unknown words as names and
        # returns the SELECT/UPDATE inside the parentheses as the leading
        # keyword; the first word of the statement decides (#297).
        (ensure_read_only, "KILL (SELECT 1)", "KILL"),
        (ensure_read_only, "EVALUATE (SELECT 1)", "EVALUATE"),
        (ensure_read_only, "/* c */ evaluate (SELECT 1)", "EVALUATE"),
        (ensure_read_only, "foo SELECT 1", "FOO"),
        (ensure_write_allowed, "EVALUATE (UPDATE t SET a = 1)", "EVALUATE"),
        (ensure_write_allowed, "x (DELETE FROM t)", "X"),
        (ensure_query_statement, "KILL (SELECT 1)", "KILL"),
        (ensure_query_statement, "EVALUATE (SELECT 1)", "EVALUATE"),
    ],
)
def test_checkers_match_the_first_word_of_the_statement(checker: Any, sql: str, word: str) -> None:
    with pytest.raises(UnsafeSQLError, match=f"^{word} is not permitted"):
        checker(sql)


@pytest.mark.parametrize("sql", ["(SELECT 1)", "((SELECT 1))", "(SELECT 1) UNION (SELECT 2)"])
def test_read_paths_allow_parenthesized_queries(sql: str) -> None:
    ensure_read_only(sql)
    ensure_query_statement(sql)


def test_query_rejected_keywords_cover_write_keywords() -> None:
    assert WRITE_KEYWORDS <= QUERY_REJECTED_KEYWORDS


# --- CUBRID comment and quote rules ---
#
# The checker splits comments, quotes and statements the way the CUBRID server
# does, not the way sqlparse's generic lexer does: CUBRID has ``//`` line
# comments, does not treat ``#`` as a comment, and treats a backslash inside a
# quote as an ordinary character by default (no_backslash_escapes=yes).

CHECKERS = [ensure_read_only, ensure_query_statement, ensure_write_allowed]


@pytest.mark.parametrize(
    "sql",
    [
        "-- c\nSELECT 1",
        "/* c */ SELECT 1",
        "/*c*/SELECT 1",
        "// c\nSELECT 1",
        "-- c\r\nSELECT 1",
        "-- c\rSELECT 1",
        "  \n\t-- c\n  /* d */\n\tSELECT 1",
        "/* a */ -- b\n /* c */ // d\n WITH x AS (SELECT 1) SELECT * FROM x",
        "/*+ RECOMPILE */ SELECT 1",
        "SELECT 1 // DELETE FROM t",
        "SELECT 'a;b' FROM t",
        "SELECT 'it''s' FROM t",
        "SELECT 'a//b', 'c--d', 'e/*f*/' FROM t",
        'SELECT "a;--b" FROM t',
        "SELECT `a;b`, [c;d] FROM t",
        'SELECT `a``;b`, "c"";d" FROM t',
        "SELECT 'C:\\temp' FROM t",
    ],
)
def test_read_paths_allow_reads_behind_comments_and_in_quotes(sql: str) -> None:
    ensure_read_only(sql)
    ensure_query_statement(sql)


@pytest.mark.parametrize(
    "sql",
    [
        # A write or DDL statement behind a comment that names a read keyword.
        "-- SELECT\nDELETE FROM t",
        "/* SELECT */ DELETE FROM t",
        "// SELECT\nDELETE FROM t",
        "// SELECT\nDROP TABLE t",
        "// SELECT\nSET SYSTEM PARAMETERS 'x=1'",
        "/* SELECT */ -- SELECT\n // SELECT\n UPDATE t SET a = 1",
        "-- SELECT\rINSERT INTO t VALUES (1)",
        # CUBRID block comments do not nest: the text after the first */ is SQL.
        "/* /* SELECT */ DROP TABLE t */",
    ],
)
def test_read_paths_reject_writes_hidden_behind_comments(sql: str) -> None:
    for checker in (ensure_read_only, ensure_query_statement):
        with pytest.raises(UnsafeSQLError, match="is not permitted"):
            checker(sql)


@pytest.mark.parametrize(
    "sql",
    [
        # A DDL statement behind a comment that names a write keyword.
        "// INSERT\nDROP TABLE t",
        "-- INSERT\nDROP TABLE t",
        "/* UPDATE */ CREATE TABLE t (a INT)",
        "// DELETE\nSELECT * FROM t",
    ],
)
def test_write_path_rejects_statements_hidden_behind_comments(sql: str) -> None:
    with pytest.raises(UnsafeSQLError, match="is not permitted in write mode"):
        ensure_write_allowed(sql)


@pytest.mark.parametrize(
    ("checker", "sql"),
    [
        # sqlparse reads ``#`` as a comment; CUBRID does not, so ``;`` follows.
        (ensure_read_only, "SELECT 1 # ; DELETE FROM t"),
        (ensure_query_statement, "SELECT 1 # ; DELETE FROM t"),
        (ensure_write_allowed, "DELETE FROM t # ; DROP TABLE t"),
        # sqlparse reads ``$$ ... $$`` as one string; CUBRID splits on the ``;``.
        (ensure_read_only, "SELECT $$; DELETE FROM t; $$"),
        (ensure_query_statement, "SELECT $$; DROP TABLE t; $$"),
        (ensure_query_statement, "SELECT $a$; DROP TABLE t; $a$"),
        (ensure_write_allowed, "INSERT INTO t SELECT $$; DROP TABLE t; $$"),
    ],
)
def test_checkers_reject_statements_only_cubrid_splits(checker: Any, sql: str) -> None:
    with pytest.raises(UnsafeSQLError, match="multi-statement"):
        checker(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT '\\'; DELETE FROM t; -- '",
        "SELECT 'a\\' , '; DELETE FROM t; -- '",
        'SELECT "a\\"; DELETE FROM t; -- "',
    ],
)
def test_checkers_reject_backslash_quote_ambiguity(sql: str) -> None:
    # Whether a backslash escapes a quote depends on the server parameter
    # no_backslash_escapes, so the statements CUBRID runs cannot be known here.
    for checker in CHECKERS:
        with pytest.raises(UnsafeSQLError, match="ambiguous") as excinfo:
            checker(sql)
        assert "('' or \"\")" in str(excinfo.value)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 'abc",
        'SELECT "abc',
        "SELECT `abc",
        "SELECT [abc",
        "SELECT 'a'' ; DELETE FROM t",
        "SELECT `a``; DELETE FROM t",
    ],
)
def test_checkers_reject_unterminated_quotes(sql: str) -> None:
    for checker in CHECKERS:
        with pytest.raises(UnsafeSQLError, match="unterminated"):
            checker(sql)


@pytest.mark.parametrize(
    "sql", ["/* unterminated SELECT 1", "// SELECT 1", "-- SELECT 1\r", "// a\r-- b\n/* c */"]
)
def test_checkers_treat_comment_only_input_as_empty_or_unknown(sql: str) -> None:
    for checker in CHECKERS:
        with pytest.raises(UnsafeSQLError, match="empty|leading SQL keyword|not permitted"):
            checker(sql)


def test_strip_comments_uses_cubrid_comment_rules() -> None:
    assert strip_comments("// c\nSELECT 1").split() == ["SELECT", "1"]
    assert strip_comments("SELECT 'x -- y' -- z").split() == ["SELECT", "''"]
    assert strip_comments("SELECT 1 # x").split() == ["SELECT", "1", "x"]


# Functions, serial attributes and the click counter that change data inside a
# SELECT (#295). Each form below changed data on a CUBRID 11.4 server, except the
# NEXT_VALUE(...) / NEXTVAL(...) call forms, which are rejected as a precaution.
_SIDE_EFFECT_SQL = [
    ("SELECT INCR(cnt) FROM t WHERE id = 1", "INCR"),
    ("select incr(cnt) from t where id = 1", "INCR"),
    ("SELECT DECR(cnt) FROM t WHERE id = 1", "DECR"),
    ("SELECT InCr (cnt) FROM t WHERE id = 1", "INCR"),
    ("SELECT INCR\n(cnt) FROM t WHERE id = 1", "INCR"),
    ("SELECT INCR/**/(cnt) FROM t WHERE id = 1", "INCR"),
    ("SELECT INCR -- note\n(cnt) FROM t WHERE id = 1", "INCR"),
    ("SELECT INCR // note\n(cnt) FROM t WHERE id = 1", "INCR"),
    ('SELECT "INCR"(cnt) FROM t WHERE id = 1', "INCR"),
    ("SELECT [incr](cnt) FROM t WHERE id = 1", "INCR"),
    ("SELECT `decr`(cnt) FROM t WHERE id = 1", "DECR"),
    ("SELECT INCR(t.cnt) FROM t WHERE id = 1", "INCR"),
    ("SELECT * FROM (SELECT INCR(cnt) FROM t) x", "INCR"),
    ("WITH q AS (SELECT DECR(cnt) AS c FROM t) SELECT * FROM q", "DECR"),
    ("SELECT s.NEXT_VALUE", "NEXT_VALUE"),
    ("SELECT s . next_value", "NEXT_VALUE"),
    ("SELECT s./* c */next_value", "NEXT_VALUE"),
    ("SELECT dba.s.NEXT_VALUE", "NEXT_VALUE"),
    ("SELECT [s].[next_value]", "NEXT_VALUE"),
    ('SELECT "s"."NEXT_VALUE"', "NEXT_VALUE"),
    ("SELECT s.NEXTVAL", "NEXTVAL"),
    ("SELECT dba.s.nextval FROM db_root", "NEXTVAL"),
    ("SELECT (SELECT s.next_value) FROM t", "NEXT_VALUE"),
    ("SELECT id FROM t WHERE id < s.next_value", "NEXT_VALUE"),
    ("SELECT SERIAL_NEXT_VALUE(s, 3)", "SERIAL_NEXT_VALUE"),
    ("SELECT serial_next_value (s, 1)", "SERIAL_NEXT_VALUE"),
    ("SELECT [serial_next_value](s, 1)", "SERIAL_NEXT_VALUE"),
    ("SELECT NEXT_VALUE(s)", "NEXT_VALUE"),
    ("SELECT NEXTVAL(s)", "NEXTVAL"),
    ("SELECT * FROM t WHERE id = 1 WITH INCREMENT FOR cnt", "WITH INCREMENT FOR"),
    ("SELECT * FROM t WHERE id = 1 with decrement for cnt", "WITH DECREMENT FOR"),
    ("SELECT * FROM t WHERE id = 1 WITH /* c */ INCREMENT\n FOR cnt", "WITH INCREMENT FOR"),
    ("SELECT * FROM t WHERE id = 1 WITH INCREMENT FOR [cnt]", "WITH INCREMENT FOR"),
]


@pytest.mark.parametrize(("sql", "name"), _SIDE_EFFECT_SQL)
def test_ensure_read_only_rejects_side_effect_functions(sql: str, name: str) -> None:
    with pytest.raises(UnsafeSQLError, match=f"^{name} is not permitted in read-only mode"):
        ensure_read_only(sql)


@pytest.mark.parametrize(("sql", "name"), _SIDE_EFFECT_SQL)
def test_ensure_query_statement_rejects_side_effect_functions(sql: str, name: str) -> None:
    # execute_query with CUBRID_MCP_READONLY=0 stays read-only (#301).
    with pytest.raises(
        UnsafeSQLError, match=f"^{name} is not permitted in execute_query.*execute_write"
    ):
        ensure_query_statement(sql)


@pytest.mark.parametrize(
    ("sql", "name"),
    [
        # A '#'-prefixed name elsewhere does not hide a real side effect (#303).
        ("SELECT #a, INCR(cnt) FROM t WHERE id = 1", "INCR"),
        ("SELECT #s.NEXT_VALUE", "NEXT_VALUE"),
        # A lone '#' is not part of the next name (a syntax error on CUBRID).
        ("SELECT # incr(cnt) FROM t", "INCR"),
    ],
)
def test_checkers_reject_side_effects_next_to_hash_names(sql: str, name: str) -> None:
    for checker in (ensure_read_only, ensure_query_statement):
        with pytest.raises(UnsafeSQLError, match=f"^{name} is not permitted"):
            checker(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT s.CURRENT_VALUE",
        "SELECT dba.s.current_value",
        "SELECT s.CURRVAL",
        "SELECT SERIAL_CURRENT_VALUE(s)",
        "SELECT incr_total, decr_count, next_value_at FROM t",
        "SELECT t.incr_total FROM t",
        "SELECT my_incr(cnt) FROM t",
        "SELECT incr# FROM t",
        'SELECT "incr "(cnt) FROM t',
        "SELECT [ incr](cnt) FROM t",
        "SELECT 'INCR(cnt)', 's.NEXT_VALUE', 'WITH INCREMENT FOR x' FROM t",
        "SELECT * FROM t WHERE note = 'incr(' AND label = '.nextval'",
        "SELECT cnt AS incr FROM t",
        "SELECT next_value FROM t",
        "SELECT 1 -- INCR(cnt)\nFROM t",
        "SELECT /* s.NEXT_VALUE */ 1 FROM t",
        "WITH increment AS (SELECT 1 AS x) SELECT x FROM increment",
        "SELECT * FROM t WHERE increment > 0 FOR x",
        # '#' may start a CUBRID name, so '#incr' is one name, not '#' + INCR (#303).
        "SELECT #incr(cnt) FROM t",
        "SELECT #DECR (cnt) FROM t",
        "SELECT #serial_next_value(s, 1)",
        "SELECT s.#next_value",
        "SELECT s.#nextval FROM t",
        "SELECT cnt AS #incr FROM t",
        "SELECT #incr# FROM t",
    ],
)
def test_ensure_read_only_allows_lookalikes_of_side_effect_functions(sql: str) -> None:
    ensure_read_only(sql)
    ensure_query_statement(sql)
