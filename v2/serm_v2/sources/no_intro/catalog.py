"""DAT-o-MATIC catalog discovery for No-Intro systems."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from .errors import NoIntroDownloadError


@dataclass(frozen=True, slots=True)
class NoIntroSystem:
    """A system advertised by DAT-o-MATIC."""

    name: str
    update_text: str | None = None


class NoIntroCatalog:
    """Discover No-Intro systems from the public DAT-o-MATIC catalog page."""

    CATALOG_URL = "https://datomatic.no-intro.org/index.php?page=download&s=31"

    def fetch_catalog(self) -> str:
        """Download the catalog HTML from DAT-o-MATIC."""
        request = Request(self.CATALOG_URL, headers={"User-Agent": "SERM-V2/2.0"})
        try:
            with urlopen(request, timeout=30) as response:
                data = response.read()
        except OSError as exc:
            raise NoIntroDownloadError("Falha ao acessar o catálogo DAT-o-MATIC.") from exc
        if not data:
            raise NoIntroDownloadError("O catálogo DAT-o-MATIC retornou conteúdo vazio.")
        return data.decode("utf-8", errors="replace")

    def systems(self, html_text: str) -> tuple[NoIntroSystem, ...]:
        """Extract No-Intro system names from catalog text."""
        text = html.unescape(re.sub(r"<[^>]+>", " ", html_text))
        systems: list[NoIntroSystem] = []
        for match in re.finditer(r"(?:^|\s)([^\n|]+?)\s*\(#\d+[^\n|]*?~\s*(\d{8}-\d{6})", text):
            name = " ".join(match.group(1).split())
            if " - " not in name or name.startswith(("Source Code -", "Unofficial -", "Non-Redump -", "Non-Game -")):
                continue
            systems.append(NoIntroSystem(name=name, update_text=match.group(2)))
        unique: dict[str, NoIntroSystem] = {}
        for item in systems:
            unique.setdefault(item.name.casefold(), item)
        return tuple(unique.values())

    def save_catalog(self, html_text: str, destination: Path) -> Path:
        """Persist a catalog snapshot outside the source package."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(html_text, encoding="utf-8")
        return destination
