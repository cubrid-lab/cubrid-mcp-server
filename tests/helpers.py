"""Shared test helpers that production code does not need."""

from __future__ import annotations

from cubrid_mcp_server.audit import AuditLogger
from cubrid_mcp_server.config import DEFAULT_CONNECTION, Config, ConnectionRegistry
from cubrid_mcp_server.context import AppContext
from cubrid_mcp_server.database import Database


def single_context(
    config: Config,
    database: Database,
    name: str = DEFAULT_CONNECTION,
    audit: AuditLogger | None = None,
) -> AppContext:
    """Build a single-connection :class:`AppContext` around ``config`` and ``database``."""
    registry = ConnectionRegistry(configs={name: config}, default_name=name)
    return AppContext(registry=registry, databases={name: database}, audit=audit)
