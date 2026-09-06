"""LaunchBox integration for SERM V2.

The integration treats LaunchBox as an optional external metadata/runtime
provider. SERM V2 owns its own configuration and never depends on LaunchBox
for application startup.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..runtime.paths import integrations_root


class LaunchBoxIntegration:
    """Discover, persist and launch a local LaunchBox installation."""

    CONFIG_PATH = integrations_root() / "launchbox.json"
    DEFAULT_CANDIDATES = (
        Path(r"G:\LaunchBox\LaunchBox.exe"),
        Path(r"C:\LaunchBox\LaunchBox.exe"),
        Path(r"D:\LaunchBox\LaunchBox.exe"),
        Path(r"E:\LaunchBox\LaunchBox.exe"),
    )

    def __init__(self) -> None:
        self.executable: Path | None = self._load()

    @property
    def installed(self) -> bool:
        """Return whether the configured LaunchBox executable exists."""
        return bool(self.executable and self.executable.is_file())

    def discover(self) -> Path | None:
        """Discover LaunchBox without requiring it to be installed in V2."""
        if self.installed:
            return self.executable
        for candidate in self.DEFAULT_CANDIDATES:
            if candidate.is_file():
                self.set_executable(candidate)
                return candidate
        return None

    def set_executable(self, executable: Path) -> None:
        """Set and persist a validated LaunchBox.exe path."""
        executable = Path(executable).expanduser().resolve()
        if executable.name.casefold() != "launchbox.exe":
            raise ValueError("O arquivo selecionado deve ser LaunchBox.exe.")
        if not executable.is_file():
            raise FileNotFoundError(f"LaunchBox.exe não encontrado: {executable}")
        self.executable = executable
        self._save()

    def launch(self) -> subprocess.Popen[bytes]:
        """Start LaunchBox using its installation directory as working directory."""
        executable = self.discover()
        if executable is None:
            raise FileNotFoundError("LaunchBox.exe não foi localizado.")
        return subprocess.Popen([str(executable)], cwd=str(executable.parent))

    def metadata_database(self) -> Path | None:
        """Return the LaunchBox metadata SQLite database when available."""
        root = self.discover()
        if root is None:
            return None
        candidate = root.parent / "Metadata" / "LaunchBox.Metadata.db"
        return candidate if candidate.is_file() else None

    def platforms_xml(self) -> Path | None:
        """Return LaunchBox Platforms.xml when available."""
        root = self.discover()
        if root is None:
            return None
        candidate = root.parent / "Metadata" / "Platforms.xml"
        return candidate if candidate.is_file() else None

    def _load(self) -> Path | None:
        """Load the configured executable from V2 data."""
        try:
            if self.CONFIG_PATH.is_file():
                data = json.loads(self.CONFIG_PATH.read_text(encoding="utf-8"))
                value = data.get("executable")
                return Path(value) if value else None
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        return None

    def _save(self) -> None:
        """Persist only the LaunchBox executable path in V2 data."""
        self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {"executable": str(self.executable) if self.executable else None}
        self.CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
