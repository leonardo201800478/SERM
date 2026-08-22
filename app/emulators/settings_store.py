"""Layer-3 persistence adapter for emulator settings."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


class JsonSettingsStore:
    """Atomic JSON settings store grouped by emulator."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load persisted settings; malformed files are safely ignored."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._data = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            self._data = {}

    def get(self, emulator: str, key: str, default: Any = None) -> Any:
        """Read one setting with a fallback default."""
        return self._data.get(emulator, {}).get(key, default)

    def set(self, emulator: str, key: str, value: Any) -> None:
        """Persist one setting immediately and atomically."""
        self._data.setdefault(emulator, {})[key] = value
        self._write()

    def update(self, emulator: str, values: dict[str, Any]) -> None:
        """Persist several settings in one atomic write."""
        self._data.setdefault(emulator, {}).update(values)
        self._write()

    def reset(self, emulator: str, defaults: dict[str, Any]) -> None:
        """Replace the persisted values for an emulator with defaults."""
        self._data[emulator] = dict(defaults)
        self._write()

    def _write(self) -> None:
        """Write without exposing a partially written configuration file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as tmp:
            json.dump(self._data, tmp, ensure_ascii=False, indent=2, sort_keys=True)
            tmp.write("\n")
            temp_name = tmp.name
        os.replace(temp_name, self.path)
