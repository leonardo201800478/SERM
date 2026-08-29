"""Parser for standard No-Intro DAT/XML files."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ..contracts.models import SourceHash, SourceProvenance
from .errors import NoIntroParseError
from .models import NoIntroDatInfo, NoIntroRomRecord, NoIntroSetRecord


class NoIntroParser:
    """Parse No-Intro DAT/XML input into deterministic source records."""

    def parse(self, path: Path) -> tuple[NoIntroDatInfo, tuple[NoIntroSetRecord, ...]]:
        """Read a DAT file and return its metadata and source-defined sets."""
        path = Path(path)
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError) as exc:
            raise NoIntroParseError(f"Não foi possível ler o DAT: {path}") from exc

        header = root.find("header")
        dat_info = NoIntroDatInfo(
            name=self._text(header, "name"),
            version=self._text(header, "version"),
            date=self._text(header, "date"),
        )
        sets: list[NoIntroSetRecord] = []
        for game in root.findall("game"):
            name = game.get("name") or self._text(game, "description")
            if not name:
                raise NoIntroParseError("Registro game sem nome/descrição.")
            roms = tuple(self._rom(record) for record in game.findall("rom"))
            sets.append(
                NoIntroSetRecord(
                    name=name,
                    description=self._text(game, "description"),
                    platform=game.get("source") or game.get("category"),
                    roms=roms,
                    provenance=SourceProvenance(
                        source="No-Intro",
                        source_version=dat_info.version,
                        source_file=str(path),
                        source_identifier=name,
                    ),
                )
            )
        return dat_info, tuple(sets)

    @staticmethod
    def _rom(element: ET.Element) -> NoIntroRomRecord:
        """Convert one source ROM element without altering its original name."""
        filename = element.get("name")
        if not filename:
            raise NoIntroParseError("Registro rom sem nome.")
        hashes = tuple(
            SourceHash(algorithm=key, value=value)
            for key in ("crc", "md5", "sha1")
            if (value := element.get(key))
        )
        size = element.get("size")
        return NoIntroRomRecord(
            filename=filename,
            size=int(size) if size and size.isdigit() else None,
            hashes=hashes,
            status=element.get("status"),
        )

    @staticmethod
    def _text(parent: ET.Element | None, tag: str) -> str | None:
        """Return normalized text from a child element, if present."""
        if parent is None:
            return None
        child = parent.find(tag)
        return child.text.strip() if child is not None and child.text else None
