"""Application context bundling configuration and the database handles.

The MCP tools historically reached for two separate module-level singletons
(``_config`` and ``_database``). ``AppContext`` replaces those with a single,
explicitly constructed object so that configuration and its derived database
connections are always created and torn down together, and so that tests can
inject a fully-formed context instead of patching globals piecemeal.

With multi-connection support (issue #126) the context owns a *registry* of
named connections. Each named connection has its own :class:`Config` and its own
:class:`Database` instance (hence its own lock and stale-connection lifecycle);
there is no shared connection state. A deployment that configures only the bare
``CUBRID_*`` variables gets a single ``default`` connection and behaves exactly
as it did before.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from cubrid_mcp_server.audit import AuditLogger
from cubrid_mcp_server.config import (
    DEFAULT_CONNECTION,
    Config,
    ConnectionRegistry,
)
from cubrid_mcp_server.database import Database


@dataclass(frozen=True)
class AppContext:
    """Bundle of the resolved :class:`ConnectionRegistry` and its databases."""

    registry: ConnectionRegistry
    databases: Mapping[str, Database]
    audit: AuditLogger | None = None

    def __post_init__(self) -> None:
        # Derive a disabled/enabled audit logger from the default connection's
        # config when one is not explicitly injected, so every context always
        # has a usable ``audit``.
        if self.audit is None:
            object.__setattr__(self, "audit", AuditLogger(self.registry.config_for().audit_log))

    @classmethod
    def from_env(cls) -> "AppContext":
        """Build a context and its databases from environment configuration."""
        registry = ConnectionRegistry.from_env()
        databases = {name: Database(config) for name, config in registry.configs.items()}
        return cls(
            registry=registry,
            databases=databases,
            audit=AuditLogger(registry.config_for().audit_log),
        )

    @classmethod
    def single(
        cls,
        config: Config,
        database: Database,
        name: str = DEFAULT_CONNECTION,
        audit: AuditLogger | None = None,
    ) -> "AppContext":
        """Build a single-connection context (convenience for tests and callers)."""
        registry = ConnectionRegistry(configs={name: config}, default_name=name)
        return cls(registry=registry, databases={name: database}, audit=audit)

    def config_for(self, connection: str | None = None) -> Config:
        """Return the :class:`Config` for ``connection`` (default when ``None``)."""
        return self.registry.config_for(connection)

    def database_for(self, connection: str | None = None) -> Database:
        """Return the :class:`Database` for ``connection`` (default when ``None``).

        Validates the name through the registry first so an unknown connection
        raises the same clear, client-safe error as :meth:`config_for`.
        """
        self.registry.config_for(connection)
        name = (
            connection.strip().lower()
            if connection and connection.strip()
            else self.registry.default_name
        )
        return self.databases[name]

    def close(self) -> None:
        """Close every database connection, best-effort.

        Every database is closed even if an earlier one raises; the first error
        (if any) is re-raised once all databases have been given a chance to close.
        """
        first_error: Exception | None = None
        for database in self.databases.values():
            try:
                database.close()
            except Exception as exc:  # noqa: BLE001 - close all before re-raising
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error
