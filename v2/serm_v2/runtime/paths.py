"""V2 filesystem path policy."""
from __future__ import annotations

import os
from pathlib import Path


def user_data_root() -> Path:
    """Return the operating-system user data root used by SERM V2."""
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "SERM"
    return Path.home() / ".local" / "share" / "serm"


def database_path() -> Path:
    """Return the V2 SQLite database path."""
    return user_data_root() / "database" / "serm.db"
