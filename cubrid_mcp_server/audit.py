"""Opt-in, redaction-safe audit logging for executed statements.

When ``CUBRID_MCP_AUDIT_LOG`` is enabled (off by default) the server emits one
structured JSON record per audited statement so operators can review what the
LLM ran — statement *category*, timing, row counts, and conservatively
extracted table identifiers. It is a security/observability aid, not a full
query log.

Redaction is a hard invariant:

- The **raw SQL text is never logged** — only its leading keyword (category),
  its length, and table identifiers that match a strict identifier regex.
- Bound parameters and literal values are never logged.
- Errors are reduced to the exception class name via
  :func:`cubrid_mcp_server.database.sanitize_error`, never the raw message.

Records are written to **stderr only**. stdout is reserved for the MCP
JSON-RPC protocol stream, so the audit logger uses a dedicated logger with a
late-bound stderr handler and ``propagate = False`` — it can never leak onto
stdout even if an embedder points root logging there.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterator, TextIO

from cubrid_mcp_server.database import sanitize_error
from cubrid_mcp_server.safety import lex_sql

_AUDIT_LOGGER_NAME = "cubrid_mcp_server.audit"

# A single, strict SQL identifier: a bare or double-quoted name, optionally
# schema-qualified (``schema.table``). Deliberately conservative — anything that
# does not match this shape is dropped rather than risk echoing a literal.
_IDENTIFIER = r'(?:"[A-Za-z_][A-Za-z0-9_]*"|[A-Za-z_][A-Za-z0-9_]*)'
_TABLE_REF = re.compile(
    rf"\b(?:FROM|JOIN)\s+({_IDENTIFIER}(?:\.{_IDENTIFIER})?)",
    re.IGNORECASE,
)
_LEADING_WORD = re.compile(r"[A-Za-z]+")

# A double-quoted name that :data:`_IDENTIFIER` can match. Any other quoted text
# (a string literal, or a quoted name that could be a literal when the server
# runs with ``ansi_quotes=no``) is noise.
_STRICT_QUOTED_IDENTIFIER = re.compile(r'"[A-Za-z_][A-Za-z0-9_]*"')


def _strip_noise(sql: str) -> str:
    """Blank out string literals and comments so neither identifier extraction
    nor category detection inspects quoted or commented text.

    Boundaries come from the CUBRID-aware scanner the SQL checks use
    (:func:`cubrid_mcp_server.safety.lex_sql`): ``--`` and ``//`` line comments,
    non-nesting block comments, quotes, and unterminated quotes or comments that
    run to the end of the input. The input is scanned both with and without
    backslash escapes (the server parameter ``no_backslash_escapes`` decides
    which applies), and text that is a literal or a comment under either reading
    is blanked, so a ``FROM``/``JOIN`` inside a literal or comment such as
    ``'JOIN secret'`` or ``-- JOIN secret`` can never echo an identifier, and a
    leading comment cannot hide or replace the category.
    """
    noise = [False] * len(sql)
    for backslash_escapes in (False, True):
        start = 0
        for kind, text in lex_sql(sql, backslash_escapes=backslash_escapes):
            end = start + len(text)
            if kind != "code" and not _STRICT_QUOTED_IDENTIFIER.fullmatch(text):
                noise[start:end] = [True] * len(text)
            start = end
    return "".join(" " if blank else ch for ch, blank in zip(sql, noise))


def _category(sql: str | None) -> str | None:
    """Return the leading SQL keyword (uppercased) or ``None``.

    Comments and string literals are stripped first (:func:`_strip_noise`), so
    ``-- note\nSELECT ...`` is ``SELECT`` and ``/* SELECT */ DELETE ...`` is
    ``DELETE``. Only the first alphabetic run is inspected, so no literal or
    identifier can be echoed through this field.
    """
    if not sql:
        return None
    match = _LEADING_WORD.match(_strip_noise(sql).lstrip())
    return match.group(0).upper() if match else None


def _identifiers(sql: str | None) -> list[str]:
    """Extract table identifiers following ``FROM``/``JOIN`` via a strict regex.

    Anything not matching :data:`_IDENTIFIER` is ignored, so values, quoted
    string literals, and expressions are never surfaced. Order-preserving and
    de-duplicated.
    """
    if not sql:
        return []
    seen: dict[str, None] = {}
    for raw in _TABLE_REF.findall(_strip_noise(sql)):
        name = raw.replace('"', "")
        if name not in seen:
            seen[name] = None
    return list(seen)


if TYPE_CHECKING:
    _BaseStreamHandler = logging.StreamHandler[TextIO]
else:
    _BaseStreamHandler = logging.StreamHandler


class _AuditHandler(_BaseStreamHandler):
    """Marker ``StreamHandler`` subclass so we can find and replace our own
    audit handler on the shared named logger (deduplication across repeated
    ``AuditLogger`` construction in tests / re-init) without touching handlers
    installed by anyone else.
    """


@dataclass
class _Outcome:
    """Mutable sink for values a caller learns *during* an audited call."""

    row_count: int | None = None
    truncated: bool | None = None


class AuditLogger:
    """Emit opt-in, redaction-safe audit records to stderr.

    When ``enabled`` is ``False`` every method is a cheap no-op, so the tools
    can call it unconditionally.
    """

    def __init__(self, enabled: bool, *, stream: TextIO | None = None) -> None:
        self.enabled = enabled
        self._logger = logging.getLogger(_AUDIT_LOGGER_NAME)
        if not enabled:
            return
        self._logger.setLevel(logging.INFO)
        # Never propagate to the root logger, which an embedder may have
        # pointed at stdout — audit output must stay on stderr.
        self._logger.propagate = False
        # This is a dedicated, non-propagating logger, so any pre-existing
        # handler (e.g. one an embedder pointed at stdout) must be removed —
        # not just our own marker handler — before installing the stderr one.
        # This also dedups repeated construction (tests, re-init).
        for handler in list(self._logger.handlers):
            self._logger.removeHandler(handler)
        emit = _AuditHandler(stream if stream is not None else sys.stderr)
        emit.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(emit)

    def record(
        self,
        *,
        tool: str,
        status: str,
        sql: str | None = None,
        row_count: int | None = None,
        truncated: bool | None = None,
        duration_ms: int | None = None,
        error_type: str | None = None,
    ) -> None:
        """Emit a single JSON audit record (no-op when disabled)."""
        if not self.enabled:
            return
        payload: dict[str, Any] = {
            "event": "statement",
            "tool": tool,
            "status": status,
            "category": _category(sql),
            "identifiers": _identifiers(sql),
            "sql_length": len(sql) if sql is not None else None,
            "row_count": row_count,
            "truncated": truncated,
            "duration_ms": duration_ms,
            "error_type": error_type,
        }
        self._logger.info(json.dumps(payload, separators=(",", ":"), sort_keys=True))

    @contextmanager
    def track(self, tool: str, sql: str | None = None) -> Iterator[_Outcome]:
        """Time an audited call, emitting a record on success and on failure.

        Yields a mutable :class:`_Outcome` the caller may populate with
        ``row_count``/``truncated``. Exceptions are audited (with a sanitized
        error type) and then re-raised unchanged.
        """
        outcome = _Outcome()
        start = time.perf_counter()
        try:
            yield outcome
        except BaseException as exc:
            self.record(
                tool=tool,
                status="error",
                sql=sql,
                duration_ms=int((time.perf_counter() - start) * 1000),
                error_type=sanitize_error(exc),
            )
            raise
        else:
            self.record(
                tool=tool,
                status="ok",
                sql=sql,
                row_count=outcome.row_count,
                truncated=outcome.truncated,
                duration_ms=int((time.perf_counter() - start) * 1000),
            )
