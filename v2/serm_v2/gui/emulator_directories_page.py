"""Compatibility entry point for the SERM V2 directory guide."""
from __future__ import annotations

from PySide6.QtWidgets import QLineEdit

from . import directories_guide_page
from .directories_guide_page import DirectoryGuidePage

# Compatibility injection for the current directory-guide implementation.
# The guide instantiates QLineEdit in _config_header(); keeping the symbol
# available here prevents the startup NameError without changing its config
# editing/persistence logic.
directories_guide_page.QLineEdit = QLineEdit


class DirectoriesPage(DirectoryGuidePage):
    """Expose the configuration-aware directory guide under the legacy import name."""


__all__ = ["DirectoriesPage"]
