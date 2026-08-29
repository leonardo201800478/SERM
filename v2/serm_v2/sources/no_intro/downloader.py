"""Download No-Intro DAT metadata from DAT-o-MATIC."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

from .errors import NoIntroDownloadError

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


class NoIntroDownloader:
    """Fetch No-Intro DAT files while keeping network concerns out of the parser."""

    BASE_URL = "https://datomatic.no-intro.org/"
    STANDARD_DAT_URL = "https://datomatic.no-intro.org/index.php?page=download&op=dat"
    DEFAULT_FILTERS = {
        "inc_complete": "0",
        "inc_unl": "1",
        "inc_pirate": "1",
        "inc_physical": "0",
        "special1_filter": "all_specials1",
        "language_filter": "all_languages",
        "region_filter": "all_regions",
        "prepare_2": "Prepare",
    }

    def download_url(self, url: str, destination: Path, *, system: str) -> NoIntroDownload:
        """Download one DAT URL and return its local provenance information."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = Request(url, headers={"User-Agent": "SERM-V2/2.0"})
        try:
            with urlopen(request, timeout=30) as response:
                data = response.read()
        except OSError as exc:
            raise NoIntroDownloadError(f"Falha ao baixar DAT: {url}") from exc
        if not data:
            raise NoIntroDownloadError(f"DAT vazio recebido: {url}")
        destination.write_bytes(data)
        return NoIntroDownload(
            system=system,
            path=destination,
            sha256=hashlib.sha256(data).hexdigest(),
            source_url=url,
        )

    def download_system(self, system: str, destination: Path) -> NoIntroDownload:
        """Generate and download a Standard DAT for one DAT-o-MATIC system."""
        if not system.strip():
            raise ValueError("Sistema No-Intro não pode ser vazio.")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        opener = build_opener(HTTPCookieProcessor())
        headers = {"User-Agent": "SERM-V2/2.0"}
        logger.info("[NO-INTRO][DAT] selecionando sistema=%s", system)

        self._request_form(opener, self.STANDARD_DAT_URL, {"sel_s": system}, headers)
        prepared = self._request_form(opener, self.STANDARD_DAT_URL, self.DEFAULT_FILTERS, headers)
        logger.debug("[NO-INTRO][DAT] página de preparação=%s", prepared.url)
        data_url = self._find_download_url(prepared.body, prepared.url)
        if data_url is None:
            if prepared.body.startswith(b"PK"):
                data_url = prepared.url
            else:
                raise NoIntroDownloadError(
                    f"DAT-o-MATIC não apresentou link de download para '{system}'."
                )

        request = Request(data_url, headers=headers)
        try:
            with opener.open(request, timeout=60) as response:
                data = response.read()
                final_url = response.geturl()
        except OSError as exc:
            raise NoIntroDownloadError(f"Falha ao baixar DAT de '{system}'.") from exc
        if not data or not (
            data.startswith(b"PK")
            or data.startswith(b"<?xml")
            or b"<datafile" in data[:4096]
        ):
            raise NoIntroDownloadError(f"Resposta inválida para o DAT de '{system}'.")
        destination.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        logger.info(
            "[NO-INTRO][DAT] OK sistema=%s bytes=%d sha256=%s arquivo=%s",
            system,
            len(data),
            digest,
            destination,
        )
        return NoIntroDownload(system=system, path=destination, sha256=digest, source_url=final_url)

    @staticmethod
    def _request_form(opener, url: str, values: dict[str, str], headers: dict[str, str]) -> _HttpResult:
        """POST one DAT-o-MATIC form and return its final URL and body."""
        payload = urlencode(values).encode("utf-8")
        request = Request(
            url,
            data=payload,
            headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with opener.open(request, timeout=60) as response:
                return _HttpResult(response.geturl(), response.read())
        except OSError as exc:
            raise NoIntroDownloadError(f"Falha na etapa POST do DAT-o-MATIC: {url}") from exc

    def discover_downloads(self, html: str, *, base_url: str | None = None) -> tuple[str, ...]:
        """Extract DAT, XML or ZIP download links from a DAT-o-MATIC page."""
        base_url = base_url or self.BASE_URL
        links = re.findall(
            r'href=["\']([^"\']+\.(?:dat|xml|zip)(?:\?[^"\']*)?)["\']',
            html,
            re.I,
        )
        return tuple(urljoin(base_url, link) for link in links)

    def _find_download_url(self, body: bytes, base_url: str) -> str | None:
        """Find a generated DAT/ZIP link on the DAT-o-MATIC manager page."""
        text = body.decode("utf-8", errors="replace")
        links = self.discover_downloads(text, base_url=base_url)
        if links:
            return links[0]
        matches = re.findall(
            r'(?:href|action)=["\']([^"\']*?(?:download|manager)[^"\']*)["\']',
            text,
            re.I,
        )
        for link in matches:
            absolute = urljoin(base_url, link)
            if "download=" in absolute or absolute.endswith((".zip", ".dat", ".xml")):
                return absolute
        return None
