"""Application-facing catalog service boundary."""
from __future__ import annotations


class CatalogService:
    """Coordinate catalog operations without knowing provider internals."""

    def list_sources(self) -> list[str]:
        """Return registered source identifiers.

        The initial V2 implementation has no persisted sources yet.
        """
        return []
