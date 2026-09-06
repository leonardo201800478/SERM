"""Compatibility entry point for the restored emulator Home."""

from __future__ import annotations

from PySide6.QtCore import Qt

from . import emulator_home as _implementation

# The restored legacy-shaped module only needs Qt for QListWidget user data.
# Injecting the symbol here keeps the implementation isolated while fixing the
# compatibility edge without duplicating the Home implementation.
_implementation.Qt = Qt
EmulatorHomePage = _implementation.EmulatorHomePage

__all__ = ["EmulatorHomePage"]
