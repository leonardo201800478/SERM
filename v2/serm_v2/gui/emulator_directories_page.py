"""Compatibility entry point for the SERM V2 directory guide."""
from __future__ import annotations

from .directories_guide_page import DirectoryGuidePage


class DirectoriesPage(DirectoryGuidePage):
    """Expose the configuration-aware directory guide under the legacy import name."""


__all__ = ["DirectoriesPage"]
