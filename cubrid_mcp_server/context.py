"""Application context bundling configuration and the database handle.

The MCP tools historically reached for two separate module-level singletons
(``_config`` and ``_database``). ``AppContext`` replaces those with a single,
explicitly constructed object so that configuration and its derived database
connection are always created and torn down together, and so that tests can
inject a fully-formed context instead of patching globals piecemeal.
"""

from __future__ import annotations

from dataclasses import dataclass

from cubrid_mcp_server.audit import AuditLogger
from cubrid_mcp_server.config import Config
from cubrid_mcp_server.database import Database


@dataclass(frozen=True)
class AppContext:
    """Bundle of the resolved :class:`Config` and its :class:`Database`."""

    config: Config
    database: Database
    audit: AuditLogger | None = None

    def __post_init__(self) -> None:
        # Derive a disabled/enabled audit logger from config when one is not
        # explicitly injected, so every context always has a usable ``audit``.
        if self.audit is None:
            object.__setattr__(self, "audit", AuditLogger(self.config.audit_log))

    @classmethod
    def from_env(cls) -> "AppContext":
        """Build a context from environment configuration."""
        config = Config.from_env()
        return cls(
            config=config,
            database=Database(config),
            audit=AuditLogger(config.audit_log),
        )

    def close(self) -> None:
        """Release the underlying database connection."""
        self.database.close()
