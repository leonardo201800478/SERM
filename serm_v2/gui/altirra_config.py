"""Section-aware, loss-minimizing access to Altirra's INI-like settings file."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

_SECTION = re.compile(r"^\s*\[([^\]]+)\]\s*(?:\r?\n)?$")
_ENTRY = re.compile(r'^(\s*)"([^"]+)"(\s*=\s*)(.*?)(\r?\n)?$')


class AltirraConfigEditor:
    """Edit numeric/bool entries without reserializing unrelated Altirra data."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._original = self.path.read_bytes()
        self._has_bom = self._original.startswith(b"\xef\xbb\xbf")
        text = self._original.decode("utf-8-sig")
        self._lines = text.splitlines(keepends=True)

    @staticmethod
    def _parse_lines(lines: list[str]):
        section = ""
        for index, line in enumerate(lines):
            section_match = _SECTION.match(line)
            if section_match:
                section = section_match.group(1)
                continue
            entry_match = _ENTRY.match(line)
            if entry_match:
                yield index, section, entry_match

    def values(self, section: str, key: str) -> list[str]:
        """Return values for a key in one exact section."""
        result: list[str] = []
        for _index, current_section, match in self._parse_lines(self._lines):
            if current_section == section and match.group(2) == key:
                result.append(match.group(4).strip().strip('"'))
        return result

    def set_value(self, section: str, key: str, value: str) -> None:
        """Replace an existing entry while retaining its spacing and value style."""
        for index, current_section, match in self._parse_lines(self._lines):
            if current_section != section or match.group(2) != key:
                continue
            old_value = match.group(4).strip()
            new_value = f'"{value}"' if old_value.startswith('"') else value
            newline = match.group(5) or ""
            self._lines[index] = f'{match.group(1)}"{key}"{match.group(3)}{new_value}{newline}'
            return
        raise KeyError(f"{section} / {key}")

    def save(self) -> Path:
        """Back up and atomically replace the file, preserving its UTF-8 BOM."""
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

    def active_profile_section(self) -> str:
        """Resolve Altirra's decimal Current profile ID to its hex section name."""
        base = "User\\Software\\virtualdub.org\\Altirra"
        profiles = f"{base}\\Profiles"
        values = self.values(profiles, "Current profile")
        if values:
            try:
                profile_id = int(values[0])
            except ValueError:
                profile_id = -1
            candidate = f"{profiles}\\{profile_id:08X}"
            if any(
                section == candidate for _index, section, _match in self._parse_lines(self._lines)
            ):
                return candidate
        return f"{profiles}\\00000000"


__all__ = ["AltirraConfigEditor"]
