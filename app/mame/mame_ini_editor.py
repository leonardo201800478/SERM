"""Editor seguro para mame.ini preservando a estrutura original do arquivo."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IniEntry:
    """Representa uma opção encontrada no mame.ini."""
    key: str
    value: str
    line_index: int


class MameIniEditor:
    """Lê e altera valores do mame.ini sem reconstruir ou reformatar o arquivo."""

    _OPTION_RE = re.compile(r"^(?P<prefix>\s*)(?P<key>[^\s#;]+)(?P<sep>\s+)(?P<value>.*?)(?P<newline>\r?\n)?$")

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lines: list[str] = []
        self._entries: dict[str, IniEntry] = {}
        self.load()

    def load(self) -> None:
        """Carrega o arquivo preservando exatamente suas linhas e comentários."""
        if not self.path.is_file():
            raise FileNotFoundError(f"mame.ini não encontrado: {self.path}")
        text = self.path.read_text(encoding="utf-8-sig")
        self._lines = text.splitlines(keepends=True)
        self._entries.clear()
        for index, line in enumerate(self._lines):
            match = self._OPTION_RE.match(line)
            if not match:
                continue
            key = match.group("key")
            if key.startswith("#") or key.startswith(";"):
                continue
            value = match.group("value").rstrip("\r\n").strip()
            self._entries[key] = IniEntry(key, value, index)

    def get(self, key: str, default: str = "") -> str:
        """Retorna o valor atual de uma opção, ou default se ela não existir."""
        entry = self._entries.get(key)
        return entry.value if entry else default

    def has(self, key: str) -> bool:
        """Indica se uma opção existe no arquivo atual."""
        return key in self._entries

    def set(self, key: str, value: str | float) -> None:
        """Altera somente o valor da opção, mantendo indentação e quebra de linha."""
        entry = self._entries.get(key)
        if entry is None:
            raise KeyError(f"Opção não encontrada no mame.ini: {key}")
        old = self._lines[entry.line_index]
        newline = "\r\n" if old.endswith("\r\n") else "\n" if old.endswith("\n") else ""
        match = self._OPTION_RE.match(old)
        if not match:
            raise ValueError(f"Linha inválida para opção {key}")
        self._lines[entry.line_index] = (
            f"{match.group('prefix')}{key}{match.group('sep')}{value}{newline}"
        )
        self._entries[key] = IniEntry(key, str(value), entry.line_index)

    def set_many(self, values: dict[str, str | int | float]) -> None:
        """Aplica várias alterações sem tocar em opções que não existam no arquivo."""
        for key, value in values.items():
            if self.has(key):
                self.set(key, value)

    def save(self, create_backup: bool = True) -> None:
        """Salva atomicamente e opcionalmente cria mame.ini.bak antes da substituição."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if create_backup and self.path.exists():
            backup = self.path.with_name(self.path.name + ".bak")
            shutil.copy2(self.path, backup)
        fd, temporary = tempfile.mkstemp(prefix=".mame_ini_", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write("".join(self._lines))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def resolve_mame_ini(mame_path: Path | None, ini_path: Path | None) -> Path | None:
    """Resolve o mame.ini a partir das configurações existentes do aplicativo."""
    candidates: list[Path] = []
    if ini_path:
        p = Path(ini_path)
        candidates.append(p if p.suffix.lower() == ".ini" else p / "mame.ini")
    if mame_path:
        p = Path(mame_path)
        candidates.append(p if p.suffix.lower() == ".ini" else p / "mame.ini")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0] if candidates else None
