"""Download No-Intro DAT metadata from DAT-o-MATIC."""
from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import Request, urljoin
from urllib.request import HTTPCookieProcessor, build_opener, urlopen
from urllib.request import Request as UrlRequest

from .catalog import NoIntroCatalog
from .errors import NoIntroDownloadError
from .scene import NoIntroScene

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NoIntroDownload:
    """Describe a downloaded DAT without interpreting its contents."""

    system: str
    path: Path
    sha256: str
    source_url: str


@dataclass(frozen=True, slots=True)
class _HttpResult:
    """Minimal response data needed by the source workflow."""

    url: str
    body: bytes
    status: int
    headers: dict[str, str]


class NoIntroDownloader:
    """Fetch No-Intro DAT files using the published Scene source by default."""

    BASE_URL = "https://datomatic.no-intro.org/"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36 SERM-V2/2.0"
    )
    REQUEST_RETRIES = 3
    RETRY_DELAY_SECONDS = 1.5

    def __init__(self) -> None:
        """Initialize the downloader with a lazy Scene system-ID cache."""
        self._scene_ids: dict[str, str] | None = None

    def download_url(self, url: str, destination: Path, *, system: str) -> NoIntroDownload:
        """Download one DAT URL and return its local provenance information."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = Request(url, headers={"User-Agent": self.USER_AGENT})
        try:
            with urlopen(request, timeout=60) as response:
                data = response.read()
                source_url = response.geturl()
        except OSError as exc:
            raise NoIntroDownloadError(f"Falha ao baixar DAT: {url}") from exc
        if not data:
            raise NoIntroDownloadError(f"DAT vazio recebido: {url}")
        if not self._looks_like_dat_archive(data):
            raise NoIntroDownloadError(f"Resposta inválida para o DAT de '{system}'.")
        destination.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        return NoIntroDownload(system=system, path=destination, sha256=digest, source_url=source_url)

    def download_system(self, system: str, destination: Path, *, source_id: str | None = None) -> NoIntroDownload:
        """Download the published Scene DAT, resolving its catalog ID when needed."""
        if not system.strip():
            raise ValueError("Sistema No-Intro não pode ser vazio.")
        resolved_id = source_id or self._resolve_scene_id(system)
        if not resolved_id:
            raise NoIntroDownloadError(f"Sistema '{system}' não possui ID Scene no catálogo.")
        return self.download_scene_system(system, resolved_id, destination)

    def download_scene_system(self, system: str, source_id: str, destination: Path) -> NoIntroDownload:
        """Download a published Scene DAT without running Standard DAT generation."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        opener = build_opener(HTTPCookieProcessor())
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": self.BASE_URL,
        }
        scene = NoIntroScene()
        page_url = f"{scene.SCENE_URL}&s={source_id}"
        logger.info("[NO-INTRO][SCENE] início sistema=%s id=%s", system, source_id)
        page = self._request_get(opener, page_url, headers)
        logger.debug(
            "[NO-INTRO][SCENE] página status=%d url=%s bytes=%d",
            page.status,
            page.url,
            len(page.body),
        )
        target = scene.target_from_html(system, page.body.decode("utf-8", errors="replace"), page.url)
        logger.info(
            "[NO-INTRO][SCENE] alvo encontrado sistema=%s revision=%s url=%s",
            system,
            target.revision or "desconhecida",
            target.url,
        )
        data = self._download_with_retry(opener, target.url, headers, system)
        if not self._looks_like_dat_archive(data.body):
            raise NoIntroDownloadError(
                f"Resposta inválida para o Scene DAT de '{system}' "
                f"(content-type={data.headers.get('Content-Type', '')})."
            )
        destination.write_bytes(data.body)
        digest = hashlib.sha256(data.body).hexdigest()
        logger.info(
            "[NO-INTRO][SCENE] OK sistema=%s bytes=%d sha256=%s arquivo=%s",
            system,
            len(data.body),
            digest,
            destination,
        )
        return NoIntroDownload(system=system, path=destination, sha256=digest, source_url=data.url)

    def _resolve_scene_id(self, system: str) -> str | None:
        """Resolve and cache a DAT-o-MATIC numeric system ID from the catalog."""
        if self._scene_ids is None:
            logger.info("[NO-INTRO][SCENE] carregando IDs de sistemas do catálogo")
            catalog = NoIntroCatalog()
            systems = catalog.systems(catalog.fetch_catalog())
            self._scene_ids = {item.name.casefold(): item.source_id for item in systems if item.source_id}
            logger.info("[NO-INTRO][SCENE] IDs Scene disponíveis=%d", len(self._scene_ids))
        exact = self._scene_ids.get(system.casefold())
        if exact:
            return exact
        normalized = self._normalize(system)
        for name, source_id in self._scene_ids.items():
            if self._normalize(name) == normalized:
                return source_id
        return None

    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize a source name for fallback ID matching."""
        return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()

    @staticmethod
    def _request_get(opener, url: str, headers: dict[str, str]) -> _HttpResult:
        """Perform a GET while preserving the opener session."""
        request = UrlRequest(url, headers=headers)
        try:
            with opener.open(request, timeout=60) as response:
                return _HttpResult(
                    response.geturl(),
                    response.read(),
                    response.status,
                    dict(response.headers.items()),
                )
        except (HTTPError, URLError, OSError) as exc:
            raise NoIntroDownloadError(f"Falha no GET do DAT-o-MATIC: {url}") from exc

    @classmethod
    def _download_with_retry(cls, opener, url: str, headers: dict[str, str], system: str) -> _HttpResult:
        """Download a published DAT with limited retry/backoff for transient failures."""
        last_exc: Exception | None = None
        for attempt in range(1, cls.REQUEST_RETRIES + 1):
            request = Request(url, headers={**headers, "Referer": cls.BASE_URL})
            try:
                with opener.open(request, timeout=60) as response:
                    result = _HttpResult(
                        response.geturl(),
                        response.read(),
                        response.status,
                        dict(response.headers.items()),
                    )
                logger.info(
                    "[NO-INTRO][HTTP] download tentativa=%d/%d status=%d bytes=%d url=%s",
                    attempt,
                    cls.REQUEST_RETRIES,
                    result.status,
                    len(result.body),
                    result.url,
                )
                return result
            except (HTTPError, URLError, OSError) as exc:
                last_exc = exc
                logger.warning(
                    "[NO-INTRO][HTTP] download tentativa=%d/%d falhou sistema=%s: %s",
                    attempt,
                    cls.REQUEST_RETRIES,
                    system,
                    exc,
                )
                if attempt < cls.REQUEST_RETRIES:
                    time.sleep(cls.RETRY_DELAY_SECONDS * attempt)
        raise NoIntroDownloadError(
            f"Falha ao baixar DAT de '{system}' após {cls.REQUEST_RETRIES} tentativas."
        ) from last_exc

    @staticmethod
    def _looks_like_dat_archive(data: bytes) -> bool:
        """Recognize archive/XML signatures returned by DAT-o-MATIC."""
        if not data:
            return False
        stripped = data.lstrip()
        return (
            data.startswith(b"PK")
            or stripped.startswith(b"<?xml")
            or b"<datafile" in stripped[:4096].lower()
        )

    def discover_downloads(self, html: str, *, base_url: str | None = None) -> tuple[str, ...]:
        """Extract direct DAT, XML or ZIP links from a DAT-o-MATIC page."""
        base_url = base_url or self.BASE_URL
        links = re.findall(
            r'href=["\']([^"\']+\.(?:dat|xml|zip)(?:\?[^"\']*)?)["\']',
            html,
            re.I,
        )
        return tuple(urljoin(base_url, link) for link in links)
