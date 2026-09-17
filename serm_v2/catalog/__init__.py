"""Providers de catálogo do Arcade Studio."""

from .base import ArcadeCatalogProvider
from .mame import MameCatalogProvider

__all__ = ["ArcadeCatalogProvider", "MameCatalogProvider"]
