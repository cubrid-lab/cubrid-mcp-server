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

from typing import Any

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword

READ_ONLY_KEYWORDS: frozenset[str] = frozenset(
    {"SELECT", "SHOW", "DESC", "DESCRIBE", "EXPLAIN", "WITH"}
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


def _strip_comments(sql: str) -> str:
    """Remove SQL comments before safety check.

    ``sqlparse`` can be confused by keywords inside comments (e.g.
    ``/* DROP TABLE */`` or ``-- DELETE FROM users``). Stripping
    comments ensures the safety checker only scans real SQL tokens.
    """
    return sqlparse.format(sql, strip_comments=True)


class UnsafeSQLError(ValueError):
    """Raised when a statement is rejected by the read-only checker."""


def ensure_read_only(sql: str) -> None:
    """Raise :class:`UnsafeSQLError` if ``sql`` is not a single read-only statement."""
    if not sql or not sql.strip():
        raise UnsafeSQLError("empty SQL statement")

    # Strip comments before parsing — keywords inside comments could
    # confuse the safety checker (defence-in-depth).
    sql = _strip_comments(sql)

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

    forbidden = _forbidden_keywords(statement)
    if forbidden:
        raise UnsafeSQLError(f"{sorted(forbidden)[0]} is not permitted in read-only mode")


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
