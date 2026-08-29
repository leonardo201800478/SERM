"""DAT-o-MATIC catalog discovery for No-Intro systems."""
from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from ..routing import SystemSourceRouter
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
    MIN_EXPECTED_SYSTEMS = 10

    def __init__(self, router: SystemSourceRouter | None = None) -> None:
        self.router = router or SystemSourceRouter()

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

    @staticmethod
    def _clean_text(value: str) -> str:
        """Remove HTML and normalize whitespace from one catalog fragment."""
        return " ".join(re.sub(r"<[^>]+>", " ", html.unescape(value)).split())

    @staticmethod
    def _is_excluded(name: str) -> bool:
        """Return whether a catalog entry is outside the normal No-Intro domain."""
        return name.startswith(("Source Code -", "Unofficial -", "Non-Redump -", "Non-Game -"))

    def _accept(self, name: str) -> bool:
        """Accept only entries that are not explicitly owned by Redump."""
        if not name or self._is_excluded(name):
            return False
        if self.router.is_redump_system(name):
            logger.debug("[NO-INTRO][ROUTING] ignorando Redump='%s'", name)
            return False
        return True

    @staticmethod
    def _extract_entry(text: str, match: re.Match[str]) -> tuple[str, str]:
        """Extract the system name and revision directly preceding a DAT marker."""
        prefix = text[: match.start()]
        name_match = re.search(r"(?P<name>[A-Za-z0-9À-ÿ][^\n|]*?\s+-\s+[^\n|]+?)\s+$", prefix)
        if not name_match:
            raise ValueError("Nome de sistema não localizado antes do marcador DAT.")
        return " ".join(name_match.group("name").split()), match.group("updated")

    def systems(self, html_text: str) -> tuple[NoIntroSystem, ...]:
        """Extract systems, revisions and DAT-o-MATIC IDs despite markup changes."""
        source = html.unescape(html_text)
        systems: list[NoIntroSystem] = []

        row_pattern = re.compile(r"<tr\b[^>]*>(?P<row>.*?)</tr>", re.I | re.S)
        link_pattern = re.compile(
            r'href=["\'][^"\']*[?&]s=(?P<id>\d+)[^"\']*["\'][^>]*>(?P<label>.*?)</a>',
            re.I | re.S,
        )
        revision_pattern = re.compile(
            r"#(?P<revision>\d+)(?:\s*\+[^~|<]+)?\s*~\s*"
            r"(?P<updated>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}|\d{8}-\d{6})"
        )

        for row_match in row_pattern.finditer(source):
            row = row_match.group("row")
            row_text = self._clean_text(row)
            revision = revision_pattern.search(row_text)
            if not revision:
                continue
            link = link_pattern.search(row)
            if link:
                name = self._clean_text(link.group("label"))
                source_id = link.group("id")
            else:
                name = row_text.split("(#", 1)[0].strip()
                source_id = None
            if not self._accept(name):
                continue
            systems.append(NoIntroSystem(name=name, update_text=revision.group("updated"), source_id=source_id))

        if len(systems) < self.MIN_EXPECTED_SYSTEMS:
            text = self._clean_text(source)
            text_pattern = re.compile(
                r"(?:^|\s)(?P<name>[A-Za-z0-9À-ÿ][^\n|]*?\s+-\s+[^\n|]+?)\s+"
                r"\(#(?P<revision>\d+)(?:\s*\+[^~|]+)?\s*~\s*"
                r"(?P<updated>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}|\d{8}-\d{6})"
            )
            for match in text_pattern.finditer(text):
                name = " ".join(match.group("name").split())
                if not self._accept(name):
                    continue
                systems.append(NoIntroSystem(name=name, update_text=match.group("updated")))

        unique: dict[str, NoIntroSystem] = {}
        for item in systems:
            key = item.name.casefold()
            current = unique.get(key)
            if current is None or (current.source_id is None and item.source_id is not None):
                unique[key] = item

        result = tuple(unique.values())
        logger.info("[NO-INTRO][CATALOG] sistemas extraídos=%d", len(result))
        if len(result) < self.MIN_EXPECTED_SYSTEMS:
            logger.warning(
                "[NO-INTRO][CATALOG] resultado suspeito: apenas %d sistema(s) extraído(s)",
                len(result),
            )
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
        logger.info(
            "[NO-INTRO][CATALOG] snapshot salvo em %s (%d bytes)",
            destination,
            len(html_text.encode("utf-8")),
        )
        return destination
