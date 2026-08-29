"""DAT-o-MATIC catalog discovery for No-Intro systems."""
from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from .errors import NoIntroDownloadError

logger = logging.getLogger(__name__)


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
        logger.info("[NO-INTRO][HTTP] GET %s", self.CATALOG_URL)
        request = Request(self.CATALOG_URL, headers={"User-Agent": "SERM-V2/2.0"})
        try:
            with urlopen(request, timeout=30) as response:
                data = response.read()
                status = getattr(response, "status", None)
        except OSError as exc:
            logger.exception("[NO-INTRO][HTTP] Falha ao acessar catálogo")
            raise NoIntroDownloadError("Falha ao acessar o catálogo DAT-o-MATIC.") from exc
        logger.info("[NO-INTRO][HTTP] resposta=%s bytes=%d", status or "?", len(data))
        if not data:
            raise NoIntroDownloadError("O catálogo DAT-o-MATIC retornou conteúdo vazio.")
        return data.decode("utf-8", errors="replace")

    def systems(self, html_text: str) -> tuple[NoIntroSystem, ...]:
        """Extract No-Intro systems from the current DAT-o-MATIC catalog format."""
        text = html.unescape(re.sub(r"<[^>]+>", " ", html_text))
        pattern = re.compile(
            r"(?P<name>[^|\n]+?\s+-\s+[^|\n]+?)\s*"
            r"\(#\d+(?:\s*\+[^~|\n]+)?\s*~\s*"
            r"(?P<updated>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"
        )
        systems: list[NoIntroSystem] = []
        for match in pattern.finditer(text):
            name = " ".join(match.group("name").split())
            if name.startswith(("Source Code -", "Unofficial -", "Non-Redump -", "Non-Game -")):
                continue
            systems.append(NoIntroSystem(name=name, update_text=match.group("updated")))

        unique: dict[str, NoIntroSystem] = {}
        for item in systems:
            unique.setdefault(item.name.casefold(), item)
        result = tuple(unique.values())
        logger.info("[NO-INTRO][CATALOG] sistemas extraídos=%d", len(result))
        logger.debug("[NO-INTRO][CATALOG] primeiros sistemas=%s", [item.name for item in result[:20]])
        return result

    def save_catalog(self, html_text: str, destination: Path) -> Path:
        """Persist a catalog snapshot outside the source package."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(html_text, encoding="utf-8")
        logger.info("[NO-INTRO][CATALOG] snapshot salvo em %s (%d bytes)", destination, len(html_text.encode("utf-8")))
        return destination
