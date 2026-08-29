"""No-Intro DAT-o-MATIC Scene source access."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import parse_qs, urljoin, urlparse

from .errors import NoIntroDownloadError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NoIntroSceneTarget:
    """Describe a Scene DAT published for one No-Intro system."""

    system: str
    url: str
    revision: str | None = None


class NoIntroScene:
    """Resolve published Scene DAT links without using Standard DAT generation."""

    BASE_URL = "https://datomatic.no-intro.org/"
    SCENE_URL = "https://datomatic.no-intro.org/index.php?op=scene&page=download"

    def target_from_html(self, system: str, html: str, base_url: str) -> NoIntroSceneTarget:
        """Find the Scene DAT link for a system in a DAT-o-MATIC response."""
        wanted = self._normalize(system)
        candidates: list[NoIntroSceneTarget] = []
        for href, label in self._links(html):
            absolute = urljoin(base_url, href)
            if not self._is_download_candidate(absolute):
                continue
            haystack = self._normalize(f"{label} {absolute}")
            if wanted not in haystack and not self._name_tokens_match(wanted, haystack):
                continue
            revision = self._revision(label) or self._revision(absolute)
            candidates.append(NoIntroSceneTarget(system=system, url=absolute, revision=revision))
        if not candidates:
            raise NoIntroDownloadError(f"Scene DAT não encontrado para '{system}'.")
        return candidates[0]

    def fetch_target(self, system: str, source_id: str, fetch_html) -> NoIntroSceneTarget:
        """Fetch the Scene page for a DAT-o-MATIC numeric system ID."""
        if not source_id or not source_id.isdigit():
            raise NoIntroDownloadError(f"ID DAT-o-MATIC inválido para '{system}'.")
        url = f"{self.SCENE_URL}&s={source_id}"
        logger.info("[NO-INTRO][SCENE] consultando sistema=%s id=%s", system, source_id)
        body, final_url, status = fetch_html(url)
        logger.debug(
            "[NO-INTRO][SCENE] status=%d url=%s bytes=%d",
            status,
            final_url,
            len(body),
        )
        return self.target_from_html(system, body.decode("utf-8", errors="replace"), final_url)

    @staticmethod
    def _links(html: str) -> tuple[tuple[str, str], ...]:
        """Extract href and visible label pairs from HTML."""
        pattern = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
        return tuple(
            (
                href,
                re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", label))).strip(),
            )
            for href, label in pattern.findall(html)
        )

    @staticmethod
    def _is_download_candidate(url: str) -> bool:
        """Accept published DAT/ZIP/XML links and Scene manager downloads."""
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        path = parsed.path.casefold()
        return (
            path.endswith((".dat", ".zip", ".xml"))
            or bool(query.get("download"))
            or "scene" in path
            or query.get("op", [""])[0].casefold() == "scene"
        )

    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize a display name for conservative matching."""
        return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()

    @staticmethod
    def _name_tokens_match(wanted: str, haystack: str) -> bool:
        """Match all meaningful system-name tokens without requiring exact formatting."""
        tokens = [token for token in wanted.split() if len(token) > 1]
        return bool(tokens) and all(token in haystack for token in tokens)

    @staticmethod
    def _revision(value: str) -> str | None:
        """Extract DAT-o-MATIC timestamp revisions when present."""
        match = re.search(r"\b(20\d{2}[-_]?\d{2}[-_]?\d{2}[ _-]\d{2}:\d{2}:\d{2})\b", value)
        return match.group(1) if match else None
