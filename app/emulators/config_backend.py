"""Backend for effective emulator configuration files."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


class ConfigBackendError(RuntimeError):
    """Base error for configuration I/O."""


class ConfigFileNotFound(ConfigBackendError):
    """Configuration file does not exist."""


class ConfigWriteError(ConfigBackendError):
    """Configuration could not be written safely."""


@dataclass(frozen=True, slots=True)
class ConfigLocation:
    """Physical configuration location and write state."""
    emulator: str
    path: Path
    exists: bool
    writable: bool


@dataclass(frozen=True, slots=True)
class ConfigValue:
    """Value read from a physical configuration file."""
    emulator: str
    key: str
    value: Any
    exists: bool


class EmulatorConfigBackend:
    """Read and atomically update simple ``key = value`` configuration files."""

    def __init__(self, emulator: str, config_path: str | Path, *, backup: bool = True) -> None:
        self.emulator = emulator.strip().lower()
        if not self.emulator:
            raise ValueError("O identificador do emulador não pode ser vazio.")
        self.config_path = Path(config_path)
        self.backup_enabled = backup

    def location(self) -> ConfigLocation:
        """Return existence and writeability information."""
        parent = self.config_path.parent
        return ConfigLocation(self.emulator, self.config_path, self.config_path.is_file(), parent.exists() and os.access(parent, os.W_OK))

    def read(self) -> str:
        """Read the complete configuration without transforming it."""
        if not self.config_path.is_file():
            raise ConfigFileNotFound(f"Arquivo não encontrado: {self.config_path}")
        try:
            return self.config_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigBackendError(f"Falha ao ler {self.config_path}: {exc}") from exc

    @staticmethod
    def parse_value(text: str) -> str:
        """Normalize a textual configuration value."""
        return text.strip()

    @classmethod
    def get_value_from_text(cls, text: str, key: str, emulator: str = "") -> ConfigValue:
        """Find a key in ``key=value`` or ``key = value`` text."""
        wanted = key.strip()
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("#", ";")) or "=" not in line:
                continue
            current_key, current_value = line.split("=", 1)
            if current_key.strip() == wanted:
                return ConfigValue(emulator, wanted, cls.parse_value(current_value), True)
        return ConfigValue(emulator, wanted, None, False)

    def get(self, key: str, default: Any = None) -> Any:
        """Return a physical setting or ``default`` when absent."""
        try:
            result = self.get_value_from_text(self.read(), key, self.emulator)
        except ConfigFileNotFound:
            return default
        return result.value if result.exists else default

    @staticmethod
    def _replace_key(text: str, key: str, value: str) -> tuple[str, bool]:
        """Replace an existing key or append it while preserving other lines."""
        lines = text.splitlines(keepends=True)
        wanted = key.strip()
        for index, raw_line in enumerate(lines):
            stripped = raw_line.strip()
            if not stripped or stripped.startswith(("#", ";")) or "=" not in stripped:
                continue
            current_key, _ = stripped.split("=", 1)
            if current_key.strip() == wanted:
                newline = "\n" if raw_line.endswith("\n") else ""
                lines[index] = f"{wanted} = {value}{newline}"
                return "".join(lines), True
        if text and not text.endswith(("\n", "\r")):
            text += "\n"
        return f"{text}{wanted} = {value}\n", False

    @staticmethod
    def serialize_value(value: Any) -> str:
        """Serialize a schema value into INI-style text."""
        if isinstance(value, bool):
            return "1" if value else "0"
        if value is None:
            return ""
        if isinstance(value, float):
            return format(value, ".12g")
        return str(value)

    def set(self, key: str, value: Any) -> None:
        """Persist one setting."""
        self.update({key: value})

    def update(self, values: dict[str, Any]) -> None:
        """Persist multiple settings in one atomic disk transaction."""
        if not values:
            return
        try:
            original = self.read() if self.config_path.exists() else ""
            if self.backup_enabled and self.config_path.exists():
                self._create_backup()
            text = original
            for key, value in values.items():
                text, _ = self._replace_key(text, key, self.serialize_value(value))
            self._atomic_write(text)
        except ConfigBackendError:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise ConfigWriteError(f"Falha ao gravar {self.config_path}: {exc}") from exc

    def _create_backup(self) -> Path:
        """Create a backup before replacing the live configuration."""
        backup = self.config_path.with_suffix(self.config_path.suffix + ".bak")
        try:
            shutil.copy2(self.config_path, backup)
        except OSError as exc:
            raise ConfigWriteError(f"Falha ao criar backup: {exc}") from exc
        return backup

    def _atomic_write(self, text: str) -> None:
        """Write a temporary sibling and atomically replace the target."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=self.config_path.parent, prefix=f".{self.config_path.name}.", suffix=".tmp", delete=False) as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = handle.name
            os.replace(temporary, self.config_path)
            temporary = None
        except OSError as exc:
            raise ConfigWriteError(f"Falha na escrita atômica: {exc}") from exc
        finally:
            if temporary:
                try:
                    Path(temporary).unlink(missing_ok=True)
                except OSError:
                    pass
