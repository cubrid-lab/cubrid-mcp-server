"""Read-only SQL safety checker.

When the server runs in read-only mode (the default), every statement passed
to ``execute_query`` is inspected by :func:`ensure_read_only` before reaching
the database. Only the minimal set of statements needed to inspect data and
schemas is allowed, and multi-statement input is rejected outright. With the
whitelist disabled, :func:`ensure_query_statement` still rejects write, DDL and
transaction-control statements, and the functions that change data inside a
``SELECT``.

The checker is a defence-in-depth layer. Operators are still expected to
configure CUBRID with a read-only user account for production use. See
``SECURITY.md`` for the recommended setup.
"""

from __future__ import annotations

import re
from typing import Any

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword

READ_ONLY_KEYWORDS: frozenset[str] = frozenset({"SELECT", "SHOW", "DESC", "DESCRIBE", "WITH"})

# Statements permitted in opt-in write mode (CUBRID_MCP_WRITE=1). Deliberately
# limited to single-statement DML: DDL is not offered because ``execute_write`` is
# a DML-only tool and ``execute_query`` is read-only. This whitelist is
# only ever consulted on the explicitly-gated write path; the read-only default
# path (:func:`ensure_read_only`) is untouched.
WRITE_KEYWORDS: frozenset[str] = frozenset({"INSERT", "UPDATE", "DELETE"})

# Leading keywords that ``execute_query`` rejects even when the read-only whitelist
# is disabled (CUBRID_MCP_READONLY=0): writes, DDL and transaction control. The
# tool only serves result-set reads; writes go through ``execute_write``. Consulted
# by :func:`ensure_query_statement` only; the read-only default path uses
# :data:`READ_ONLY_KEYWORDS` instead.
# ``CALL`` and ``EVALUATE`` run methods, and ``CALL login(...) ON CLASS db_user``
# changes the user of the shared session for every later tool call; ``KILL`` ends
# other sessions' transactions. ``LOCK`` is not a CUBRID statement (a syntax error
# on 10.2 and 11.4) and ``GET`` only reads a server setting, so neither is listed.
QUERY_REJECTED_KEYWORDS: frozenset[str] = WRITE_KEYWORDS | frozenset(
    {
        "CALL",
        "EVALUATE",
        "KILL",
        "REPLACE",
        "MERGE",
        "CREATE",
        "ALTER",
        "DROP",
        "TRUNCATE",
        "RENAME",
        "GRANT",
        "REVOKE",
        "COMMIT",
        "ROLLBACK",
        "SAVEPOINT",
        "SET",
        "PREPARE",
        "EXECUTE",
        "DEALLOCATE",
        "DO",
    }
)

# Keywords that mutate data/schema or otherwise escape read-only mode. Even when a
# statement begins with an allowed keyword (e.g. a CTE ``WITH ... AS (...) DELETE`` or
# a ``SELECT ... FOR UPDATE``), the presence of any of these anywhere in the token
# stream is rejected as defence-in-depth.
FORBIDDEN_KEYWORDS: frozenset[str] = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "REPLACE",
        "MERGE",
        "DROP",
        "CREATE",
        "ALTER",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
        "RENAME",
        "CALL",
        "EXECUTE",
        "COMMIT",
        "ROLLBACK",
        "LOCK",
        "INTO",
    }
)


# CUBRID functions and serial attributes that change data although they appear in
# a SELECT: ``INCR(col)``/``DECR(col)`` update the row they read, and
# ``serial.NEXT_VALUE``, ``serial.NEXTVAL`` and ``SERIAL_NEXT_VALUE(serial, n)``
# advance a serial. The server rollback after a read does not undo either, and a
# SELECT-only grant does not prevent them. ``sqlparse`` reads these names as
# ``Name`` tokens (or as a string symbol when double-quoted), so they are never
# seen by the keyword scan; :func:`_side_effect` finds them instead. A name counts
# when it is followed by ``(`` or preceded by ``.``, whether bare or quoted, in
# any case. ``CURRENT_VALUE``, ``CURRVAL`` and ``SERIAL_CURRENT_VALUE`` only read
# a serial and stay allowed.
SIDE_EFFECT_NAMES: frozenset[str] = frozenset(
    {"INCR", "DECR", "NEXT_VALUE", "NEXTVAL", "SERIAL_NEXT_VALUE"}
)

# The click-counter clause ``SELECT ... WITH INCREMENT FOR col`` (or
# ``WITH DECREMENT FOR col``) updates ``col`` in the rows it reads.
CLICK_COUNTER_NAMES: frozenset[str] = frozenset({"INCREMENT", "DECREMENT"})

# A CUBRID identifier (``#`` is an identifier character, also as the first one, so
# ``incr#`` and ``#incr`` are each one name), a number, or one other non-space
# character.
_CODE_TOKEN = re.compile(r"(?:[^\W\d]|#)[\w#]*|\d+|[^\w\s]")


class UnsafeSQLError(ValueError):
    """Raised when a statement is rejected by the read-only checker."""


def lex_sql(sql: str, *, backslash_escapes: bool) -> list[tuple[str, str]]:
    """Split ``sql`` into ``(kind, text)`` segments following CUBRID's lexical rules.

    ``kind`` is ``"code"``, ``"comment"``, ``"quoted"`` (a string literal or
    quoted identifier) or ``"unterminated"`` (a quote that is never closed).
    ``sqlparse`` uses a generic lexer whose rules differ from CUBRID's: it does
    not know CUBRID's ``//`` line comments, it treats ``#`` as a comment (CUBRID
    does not), and it treats a backslash as an escape inside quotes. So the
    boundaries of comments, literals and statements are decided here instead,
    the way the CUBRID server decides them. The audit log uses the same scanner
    to blank out literals and comments.

    CUBRID comments are ``--`` and ``//`` up to the end of the line (``\n`` or
    ``\r``) and ``/* ... */``, which does not nest; an unterminated block comment
    runs to the end of the input. Quotes are ``'...'``, ``"..."`` and ```...```
    (a doubled quote character escapes itself) and ``[...]``. A backslash
    escapes the next character inside ``'...'`` and ``"..."`` only when
    ``backslash_escapes`` is true, which models a server running with
    ``no_backslash_escapes=no``.
    """
    segments: list[tuple[str, str]] = []
    code_start = 0
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        two = sql[i : i + 2]
        if two in ("--", "//"):
            end = i
            while end < n and sql[end] not in "\r\n":
                end += 1
            kind = "comment"
        elif two == "/*":
            close = sql.find("*/", i + 2)
            end = n if close == -1 else close + 2
            kind = "comment"
        elif ch in "'\"`":
            end = i + 1
            kind = "unterminated"
            while end < n:
                if backslash_escapes and ch != "`" and sql[end] == "\\":
                    end += 2
                elif sql[end] != ch:
                    end += 1
                elif sql[end + 1 : end + 2] == ch:
                    end += 2
                else:
                    end += 1
                    kind = "quoted"
                    break
            end = min(end, n)
        elif ch == "[":
            close = sql.find("]", i + 1)
            end = n if close == -1 else close + 1
            kind = "unterminated" if close == -1 else "quoted"
        else:
            i += 1
            continue
        if code_start < i:
            segments.append(("code", sql[code_start:i]))
        segments.append((kind, sql[i:end]))
        i = code_start = end
    if code_start < n:
        segments.append(("code", sql[code_start:]))
    return segments


def _render(segments: list[tuple[str, str]]) -> str:
    """Rebuild SQL for ``sqlparse`` with CUBRID's boundaries made unambiguous.

    Comments become a space. Quoted text is replaced by an empty quote of the
    same kind, so ``sqlparse`` cannot read a quote boundary differently. ``#``
    in code becomes a space, so ``sqlparse`` cannot read it as a comment and
    hide the tokens after it.
    """
    parts: list[str] = []
    for kind, text in segments:
        if kind == "comment":
            parts.append(" ")
        elif kind in ("quoted", "unterminated"):
            parts.append("[]" if text[0] == "[" else text[0] * 2)
        else:
            parts.append(text.replace("#", " "))
    return "".join(parts)


def strip_comments(sql: str) -> str:
    """Remove SQL comments before the safety check, using CUBRID's comment rules.

    Keywords inside comments (e.g. ``/* DROP TABLE */``, ``-- DELETE FROM users``
    or ``// DELETE FROM users``) must not be scanned, and a comment must not hide
    the real leading keyword. Quoted text is reduced to an empty quote (see
    :func:`_render`); the result is only for analysis, never for execution.
    """
    return _render(lex_sql(sql, backslash_escapes=False))


def _cubrid_statements(sql: str) -> list[str]:
    """Return the non-empty statements CUBRID would see, comment-stripped.

    Statements are split on ``;`` outside comments and quotes. The input is
    lexed both with and without backslash escapes (the CUBRID server parameter
    ``no_backslash_escapes`` decides which applies); if the two readings find
    different comment or quote boundaries the input is rejected, because the
    statements the server runs cannot be known here. An unterminated quote is
    rejected too: everything after it would otherwise be hidden from the checks.
    """
    segments = lex_sql(sql, backslash_escapes=False)
    if segments != lex_sql(sql, backslash_escapes=True):
        raise UnsafeSQLError(
            "a backslash inside a quoted literal makes the statement ambiguous; "
            "escape a quote by doubling the quote character used ('' or \"\") instead"
        )
    if any(kind == "unterminated" for kind, _ in segments):
        raise UnsafeSQLError("unterminated quoted literal or identifier")
    rendered = _render(segments)
    return [part for part in rendered.split(";") if part.strip()]


def _parse(sql: str, mode: str) -> tuple[Statement, bool]:
    """Parse ``sql`` and return ``(statement, more_by_cubrid)``.

    Empty and comment-only input, and input ``sqlparse`` splits into more than
    one statement, are rejected here. ``more_by_cubrid`` is true when CUBRID's
    own rules (see :func:`_cubrid_statements`) find more than one statement
    although ``sqlparse`` found one, for example when ``sqlparse`` groups a
    ``BEGIN ... END`` block. Callers check the leading keyword first, so a
    statement that is rejected anyway keeps its specific error, and then
    reject ``more_by_cubrid`` with :func:`_multi_statement_error`. ``mode``
    names the path in the error message.
    """
    if not sql or not sql.strip():
        raise UnsafeSQLError("empty SQL statement")

    cubrid_statements = _cubrid_statements(sql)
    statements = [
        stmt for stmt in sqlparse.parse(";".join(cubrid_statements)) if _is_non_empty(stmt)
    ]
    if not statements:
        raise UnsafeSQLError("empty SQL statement")
    if len(statements) > 1:
        raise _multi_statement_error(mode)
    return statements[0], len(cubrid_statements) > 1


def _multi_statement_error(mode: str) -> UnsafeSQLError:
    return UnsafeSQLError(f"multi-statement SQL is not allowed in {mode}")


def ensure_read_only(sql: str) -> None:
    """Raise :class:`UnsafeSQLError` if ``sql`` is not a single read-only statement."""
    # Comments are stripped before parsing, so keywords inside them cannot
    # confuse the checker or hide the leading keyword (defence-in-depth).
    statement, more_by_cubrid = _parse(sql, "read-only mode")
    keyword = _first_name(sql) or _leading_keyword(statement)
    if keyword is None:
        raise UnsafeSQLError("could not determine the leading SQL keyword")
    if keyword.upper() not in READ_ONLY_KEYWORDS:
        raise UnsafeSQLError(
            f"{keyword.upper()} is not permitted in read-only mode; "
            f"allowed statements: {', '.join(sorted(READ_ONLY_KEYWORDS))}"
        )

    forbidden = _forbidden_keywords(statement)
    if forbidden:
        raise UnsafeSQLError(f"{sorted(forbidden)[0]} is not permitted in read-only mode")
    side_effect = _side_effect(sql)
    if side_effect is not None:
        raise UnsafeSQLError(
            f"{side_effect} is not permitted in read-only mode: it changes data "
            "even inside a SELECT, and the rollback after the read does not undo it"
        )
    if more_by_cubrid:
        raise _multi_statement_error("read-only mode")


def statement_keyword(sql: str) -> str | None:
    """Return the leading keyword of the single statement in ``sql``, in upper case.

    Uses the same reading as the checks: CUBRID's comment, quote and statement
    rules, the first word of the statement, then the leading ``sqlparse``
    keyword (so ``(SELECT 1)`` and ``SELECT*FROM t`` read as ``SELECT``). Empty,
    ambiguous and multi-statement input raise :class:`UnsafeSQLError`.
    """
    statement, more_by_cubrid = _parse(sql, "read-only mode")
    if more_by_cubrid:
        raise _multi_statement_error("read-only mode")
    keyword = _first_name(sql) or _leading_keyword(statement)
    return keyword.split()[0].upper() if keyword is not None else None


def ensure_query_statement(sql: str) -> None:
    """Raise :class:`UnsafeSQLError` unless ``sql`` is a single non-write statement.

    Consulted by ``execute_query`` when the read-only whitelist is disabled
    (``CUBRID_MCP_READONLY=0``): that flag relaxes the whitelist for result-set
    reads but never turns ``execute_query`` into a write path. Empty and
    multi-statement input are rejected, as in :func:`ensure_read_only`. The
    first word of the leading keyword is matched against
    :data:`QUERY_REJECTED_KEYWORDS`, so ``CREATE OR REPLACE ...`` is rejected
    like ``CREATE``. So is the first word of the statement (see
    :func:`_first_name`). The data-changing functions, serial advances and click
    counter that read-only mode rejects (see :func:`_side_effect`) are rejected
    too: they change data inside a ``SELECT`` and the rollback does not undo
    them. Other statements pass; the database read path still rejects any that
    return no result set.
    """
    # Same parsing as ensure_read_only: a leading comment must not hide the real
    # leading keyword, and comment-only input counts as empty.
    statement, more_by_cubrid = _parse(sql, "execute_query")
    keyword = _leading_keyword(statement)
    leading_word = keyword.split()[0].upper() if keyword is not None else None
    for word in (_first_name(sql), leading_word):
        if word in QUERY_REJECTED_KEYWORDS:
            raise UnsafeSQLError(
                f"{word} is not permitted in execute_query, which only runs reads; "
                "use execute_write for INSERT/UPDATE/DELETE (requires CUBRID_MCP_WRITE=1)"
            )
    side_effect = _side_effect(sql)
    if side_effect is not None:
        raise UnsafeSQLError(
            f"{side_effect} is not permitted in execute_query: it changes data even "
            "inside a SELECT, and the rollback after the read does not undo it; "
            "use execute_write for writes (requires CUBRID_MCP_WRITE=1)"
        )
    if more_by_cubrid:
        raise _multi_statement_error("execute_query")


def ensure_write_allowed(sql: str) -> None:
    """Raise :class:`UnsafeSQLError` unless ``sql`` is a single write statement.

    Only consulted on the opt-in write path (``CUBRID_MCP_WRITE=1``). Accepts a
    single ``INSERT``/``UPDATE``/``DELETE`` statement; rejects everything else
    (reads, DDL, transaction-control, multi-statement, and empty input) so that
    enabling write mode cannot smuggle in DDL or read escapes. Like the read
    checks, it matches the first word of the statement (see :func:`_first_name`)
    before the leading ``sqlparse`` keyword.
    """
    statement, more_by_cubrid = _parse(sql, "write mode")
    keyword = _first_name(sql) or _leading_keyword(statement)
    if keyword is None:
        raise UnsafeSQLError("could not determine the leading SQL keyword")
    if keyword.upper() not in WRITE_KEYWORDS:
        raise UnsafeSQLError(
            f"{keyword.upper()} is not permitted in write mode; "
            f"allowed statements: {', '.join(sorted(WRITE_KEYWORDS))}"
        )
    if more_by_cubrid:
        raise _multi_statement_error("write mode")


def _is_non_empty(statement: Statement) -> bool:
    stripped = statement.value.strip().rstrip(";").strip()
    return bool(stripped)


def _first_name(sql: str) -> str | None:
    """Return the first word of ``sql`` in upper case, or ``None`` if it is not a name.

    ``sqlparse`` reads ``KILL`` and ``EVALUATE`` as names, not keywords, so
    :func:`_leading_keyword` skips them and returns a later keyword, such as the
    ``SELECT`` of ``KILL (SELECT 1)``. The first word decides which statement
    CUBRID runs, so the checks read it with CUBRID's lexical rules; ``(`` and
    other punctuation are not names, so ``(SELECT 1)`` falls back to the
    leading keyword. Callers have already rejected empty input.
    """
    kind, value = _code_tokens(sql)[0]
    return value if kind == "name" else None


def _leading_keyword(statement: Statement) -> str | None:
    for token in statement.tokens:
        if token.is_whitespace:
            continue
        if token.ttype is not None and token.ttype in Keyword:
            return str(token.value)
        if token.ttype is None and hasattr(token, "tokens"):
            inner = _leading_keyword(token)
            if inner is not None:
                return inner
    return None


def _forbidden_keywords(statement: Statement) -> set[str]:
    """Return any forbidden keyword tokens found anywhere in ``statement``."""
    found: set[str] = set()
    _collect_forbidden(statement, found)
    return found


def _collect_forbidden(token: Any, found: set[str]) -> None:
    for child in getattr(token, "tokens", []):
        if child.ttype is not None and child.ttype in Keyword:
            upper = str(child.value).upper()
            if upper in FORBIDDEN_KEYWORDS:
                found.add(upper)
        if hasattr(child, "tokens"):
            _collect_forbidden(child, found)


def _code_tokens(sql: str) -> list[tuple[str, str]]:
    """Return ``(kind, upper_text)`` tokens of ``sql``, without whitespace and comments.

    ``kind`` is ``"name"`` for a bare or quoted identifier (``"..."``, ```...```,
    ``[...]``, unquoted with doubled quote characters undone and whitespace kept, since
    CUBRID reads ``"incr "`` as a different name), ``"literal"``
    for a ``'...'`` string and ``"code"`` for anything else. Comments are dropped,
    so ``INCR/**/(`` reads as ``INCR (``. Callers have already rejected input whose
    quote boundaries are ambiguous or unterminated (see :func:`_cubrid_statements`).
    """
    tokens: list[tuple[str, str]] = []
    for kind, text in lex_sql(sql, backslash_escapes=False):
        if kind == "comment":
            continue
        if kind != "code":
            quote = text[0]
            if quote == "'":
                tokens.append(("literal", ""))
            elif quote == "[":
                tokens.append(("name", text[1:-1].upper()))
            else:
                inner = text[1:-1].replace(quote * 2, quote)
                tokens.append(("name", inner.upper()))
            continue
        for match in _CODE_TOKEN.finditer(text):
            value = match.group().upper()
            is_name = value[0].isalpha() or value[0] in "_#"
            tokens.append(("name" if is_name else "code", value))
    return tokens


def _side_effect(sql: str) -> str | None:
    """Return the first data-changing function, serial advance or click counter in ``sql``.

    See :data:`SIDE_EFFECT_NAMES` and :data:`CLICK_COUNTER_NAMES`. The whole input
    is scanned, so subqueries and CTEs are covered; string literals are not names,
    and a longer name such as ``incr_total`` is a different identifier.
    """
    tokens = _code_tokens(sql)
    for i, (kind, value) in enumerate(tokens):
        if kind != "name":
            continue
        before = tokens[i - 1] if i > 0 else ("", "")
        after = tokens[i + 1] if i + 1 < len(tokens) else ("", "")
        if value in SIDE_EFFECT_NAMES and (after == ("code", "(") or before == ("code", ".")):
            return value
        if value in CLICK_COUNTER_NAMES and before[1] == "WITH" and after[1] == "FOR":
            return f"WITH {value} FOR"
    return None
