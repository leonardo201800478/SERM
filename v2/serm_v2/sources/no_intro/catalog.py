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
    source_id: str | None = None


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
        """Extract system names, revisions and DAT-o-MATIC system IDs."""
        source = html.unescape(html_text)
        row_pattern = re.compile(r"<tr\b[^>]*>(?P<row>.*?)</tr>", re.I | re.S)
        link_pattern = re.compile(
            r'href=["\'][^"\']*[?&]s=(?P<id>\d+)[^"\']*["\'][^>]*>(?P<label>.*?)</a>',
            re.I | re.S,
        )
        revision_pattern = re.compile(
            r"#\d+(?:\s*\+[^~|<]+)?\s*~\s*(?P<updated>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}|\d{8}-\d{6})"
        )
        systems: list[NoIntroSystem] = []
        for row_match in row_pattern.finditer(source):
            row = row_match.group("row")
            link = link_pattern.search(row)
            if not link:
                continue
            name = " ".join(re.sub(r"<[^>]+>", " ", link.group("label")).split())
            if not name or name.startswith(("Source Code -", "Unofficial -", "Non-Redump -", "Non-Game -")):
                continue
            revision = revision_pattern.search(re.sub(r"<[^>]+>", " ", row))
            systems.append(
                NoIntroSystem(
                    name=name,
                    update_text=revision.group("updated") if revision else None,
                    source_id=link.group("id"),
                )
            )

        if not systems:
            text = re.sub(r"<[^>]+>", " ", source)
            pattern = re.compile(
                r"(?P<name>[^|\n]+?\s+-\s+[^|\n]+?)\s*"
                r"\(#\d+(?:\s*\+[^~|\n]+)?\s*~\s*"
                r"(?P<updated>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}|\d{8}-\d{6})"
            )
            systems = [
                NoIntroSystem(
                    name=" ".join(match.group("name").split()),
                    update_text=match.group("updated"),
                )
                for match in pattern.finditer(text)
                if not match.group("name").strip().startswith(("Source Code -", "Unofficial -", "Non-Redump -", "Non-Game -"))
            ]

        unique: dict[str, NoIntroSystem] = {}
        for item in systems:
            unique.setdefault(item.name.casefold(), item)
        result = tuple(unique.values())
        logger.info("[NO-INTRO][CATALOG] sistemas extraídos=%d", len(result))
        logger.debug(
            "[NO-INTRO][CATALOG] primeiros sistemas=%s",
            [(item.name, item.source_id, item.update_text) for item in result[:20]],
        )
        return result

    def save_catalog(self, html_text: str, destination: Path) -> Path:
        """Persist a catalog snapshot outside the source package."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(html_text, encoding="utf-8")
        logger.info("[NO-INTRO][CATALOG] snapshot salvo em %s (%d bytes)", destination, len(html_text.encode("utf-8")))
        return destination
