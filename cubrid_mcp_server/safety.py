"""Read-only SQL safety checker.

When the server runs in read-only mode (the default), every statement passed
to ``execute_query`` is inspected by :func:`ensure_read_only` before reaching
the database. Only the minimal set of statements needed to inspect data and
schemas is allowed, and multi-statement input is rejected outright.

The checker is a defence-in-depth layer. Operators are still expected to
configure CUBRID with a read-only user account for production use. See
``SECURITY.md`` for the recommended setup.
"""

from __future__ import annotations

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword

READ_ONLY_KEYWORDS: frozenset[str] = frozenset(
    {"SELECT", "SHOW", "DESC", "DESCRIBE", "EXPLAIN", "WITH"}
)


class UnsafeSQLError(ValueError):
    """Raised when a statement is rejected by the read-only checker."""


def ensure_read_only(sql: str) -> None:
    """Raise :class:`UnsafeSQLError` if ``sql`` is not a single read-only statement."""
    if not sql or not sql.strip():
        raise UnsafeSQLError("empty SQL statement")

    statements = [stmt for stmt in sqlparse.parse(sql) if _is_non_empty(stmt)]
    if len(statements) == 0:
        raise UnsafeSQLError("empty SQL statement")
    if len(statements) > 1:
        raise UnsafeSQLError("multi-statement SQL is not allowed in read-only mode")

    statement = statements[0]
    keyword = _leading_keyword(statement)
    if keyword is None:
        raise UnsafeSQLError("could not determine the leading SQL keyword")
    if keyword.upper() not in READ_ONLY_KEYWORDS:
        raise UnsafeSQLError(
            f"{keyword.upper()} is not permitted in read-only mode; "
            f"allowed statements: {', '.join(sorted(READ_ONLY_KEYWORDS))}"
        )


def _is_non_empty(statement: Statement) -> bool:
    stripped = statement.value.strip().rstrip(";").strip()
    return bool(stripped)


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
