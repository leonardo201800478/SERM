"""Section-aware editor for WinUAE's global ``winuae.ini`` settings."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

_SECTION = re.compile(r"^\s*\[([^\]]+)\]\s*(?:\r?\n)?$")
_ENTRY = re.compile(r"^(\s*)([^=\r\n]+?)(\s*=\s*)(.*?)(\r?\n)?$")


class WinUAEConfigEditor:
    """Read/write only keys in WinUAE's exact ``[WinUAE]`` section."""

    SECTION = "WinUAE"

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._original = self.path.read_bytes()
        self._has_bom = self._original.startswith(b"\xef\xbb\xbf")
        self._lines = self._original.decode("utf-8-sig").splitlines(keepends=True)

    @staticmethod
    def _entries(lines: list[str]):
        section = ""
        for index, line in enumerate(lines):
            section_match = _SECTION.match(line)
            if section_match:
                section = section_match.group(1)
                continue
            entry = _ENTRY.match(line)
            if entry:
                yield index, section, entry

    def values(self, key: str) -> list[str]:
        return [
            entry.group(4).strip()
            for _index, section, entry in self._entries(self._lines)
            if section == self.SECTION and entry.group(2).strip() == key
        ]

    def set_value(self, key: str, value: str) -> None:
        for index, section, entry in self._entries(self._lines):
            if section != self.SECTION or entry.group(2).strip() != key:
                continue
            newline = entry.group(5) or ""
            self._lines[index] = f"{entry.group(1)}{entry.group(2)}{entry.group(3)}{value}{newline}"
            return
        raise KeyError(f"[{self.SECTION}] {key}")

    def save(self) -> Path:
        backup = self.path.with_name(f"{self.path.name}.bak")
        shutil.copy2(self.path, backup)
        content = "".join(self._lines).encode("utf-8")
        if self._has_bom:
            content = b"\xef\xbb\xbf" + content
        fd, temporary_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, self.path)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise
        return backup


__all__ = ["WinUAEConfigEditor"]
