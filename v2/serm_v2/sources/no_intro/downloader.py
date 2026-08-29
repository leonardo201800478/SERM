"""Download No-Intro DAT metadata from DAT-o-MATIC."""
from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

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
    """Minimal response data needed by the DAT generation workflow."""

    url: str
    body: bytes
    status: int
    headers: dict[str, str]


class NoIntroDownloader:
    """Fetch No-Intro DAT files using the published Scene source by default."""

    BASE_URL = "https://datomatic.no-intro.org/"
    STANDARD_DAT_URL = "https://datomatic.no-intro.org/index.php?page=download&op=dat"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36 SERM-V2/2.0"
    )
    REQUEST_RETRIES = 3
    RETRY_DELAY_SECONDS = 1.5

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
        """Download the published Scene DAT; Standard generation remains available as fallback."""
        if not system.strip():
            raise ValueError("Sistema No-Intro não pode ser vazio.")
        if source_id:
            return self.download_scene_system(system, source_id, destination)
        logger.warning(
            "[NO-INTRO][DAT] sistema=%s sem source_id; usando Standard DAT como fallback",
            system,
        )
        return self._download_standard_system(system, destination)

    def download_scene_system(self, system: str, source_id: str, destination: Path) -> NoIntroDownload:
        """Download a published Scene DAT without running the Standard DAT generator."""
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
        logger.info("[NO-INTRO][SCENE] início sistema=%s id=%s", system, source_id)
        page_url = f"{scene.SCENE_URL}&s={source_id}"
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

    def _download_standard_system(self, system: str, destination: Path) -> NoIntroDownload:
        """Generate and download a Standard DAT for systems without a catalog ID."""
        raise NoIntroDownloadError(
            f"Standard DAT não está habilitado como fallback automático para '{system}'. "
            "O catálogo não forneceu source_id."
        )

    @staticmethod
    def _request_get(opener, url: str, headers: dict[str, str]) -> _HttpResult:
        """Perform a GET while preserving the opener session."""
        request = Request(url, headers=headers)
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
            request = Request(url, headers={**headers, "Referer": cls.STANDARD_DAT_URL})
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
        from urllib.parse import urljoin

        base_url = base_url or self.BASE_URL
        links = re.findall(
            r'href=["\']([^"\']+\.(?:dat|xml|zip)(?:\?[^"\']*)?)["\']',
            html,
            re.I,
        )
        return tuple(urljoin(base_url, link) for link in links)
