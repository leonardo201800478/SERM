"""Shared dialogs with a persistent last-used directory."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget

from .ui_preferences import UiPreferences

_LAST_DIRECTORY_KEY = "dialogs/last_directory"


def get_existing_directory(
    parent: QWidget | None = None,
    caption: str = "",
    directory: str = "",
    options: QFileDialog.Option = QFileDialog.Option.ShowDirsOnly,
) -> str:
    """Open a folder picker in the last selected directory and remember the result."""
    settings = UiPreferences.settings()
    saved_value = str(settings.value(_LAST_DIRECTORY_KEY, "")).strip()
    saved = Path(saved_value).expanduser() if saved_value else None
    fallback = Path(directory).expanduser() if directory else Path.home()
    initial = saved if saved is not None and saved.is_dir() else (
        fallback if fallback.is_dir() else Path.home()
    )
    selected = QFileDialog.getExistingDirectory(parent, caption, str(initial), options)
    if selected:
        settings.setValue(_LAST_DIRECTORY_KEY, str(Path(selected).expanduser().resolve()))
        settings.sync()
    return selected


__all__ = ["get_existing_directory"]
