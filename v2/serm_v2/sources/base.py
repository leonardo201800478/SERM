"""Provider contract for external data sources."""
from __future__ import annotations

from abc import ABC, abstractmethod


class SourceProvider(ABC):
    """Base contract shared by preservation and metadata providers."""

    @abstractmethod
    def source_key(self) -> str:
        """Return the stable provider identifier."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, source_path: str) -> object:
        """Parse one source artifact into provider-owned data."""
        raise NotImplementedError
