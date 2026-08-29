"""Download No-Intro DAT metadata from DAT-o-MATIC."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
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

        selected = self._request_form(opener, self.STANDARD_DAT_URL, {"sel_s": system}, headers)
        logger.debug("[NO-INTRO][DAT] sistema selecionado URL=%s bytes=%d", selected.url, len(selected.body))

        prepared = self._request_form(opener, self.STANDARD_DAT_URL, self.DEFAULT_FILTERS, headers)
        logger.debug(
            "[NO-INTRO][DAT] preparação concluída URL=%s bytes=%d",
            prepared.url,
            len(prepared.body),
        )

        # DAT-o-MATIC redirects the Prepare POST to the generated manager URL:
        #   index.php?page=manager&download=<id>
        # urllib follows that redirect automatically, so the final response URL
        # is itself the download identifier even when the HTML contains no href.
        data_url = self._find_download_url(prepared.body, prepared.url)
        if data_url is None:
            raise NoIntroDownloadError(
                f"DAT-o-MATIC não apresentou link de download para '{system}'."
            )

        logger.debug("[NO-INTRO][DAT] URL de download resolvida=%s", data_url)
        request = Request(data_url, headers=headers)
        try:
            with opener.open(request, timeout=60) as response:
                data = response.read()
                final_url = response.geturl()
        except OSError as exc:
            raise NoIntroDownloadError(f"Falha ao baixar DAT de '{system}'.") from exc

        if not self._looks_like_dat_archive(data):
            content_type = ""
            logger.warning(
                "[NO-INTRO][DAT] resposta inesperada sistema=%s bytes=%d content_type=%s url=%s",
                system,
                len(data),
                content_type,
                final_url,
            )
            raise NoIntroDownloadError(
                f"Resposta inválida para o DAT de '{system}' (não é ZIP/XML/DAT reconhecível)."
            )

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
        """Resolve the generated DAT URL, including DAT-o-MATIC manager redirects."""
        text = body.decode("utf-8", errors="replace")

        # Current DAT-o-MATIC behavior: the Prepare POST redirects to a URL
        # such as /index.php?page=manager&download=9113. The generated artifact
        # is addressed by this URL, although the response HTML may contain no
        # .zip/.dat href at all.
        parsed = urlparse(base_url)
        query = parse_qs(parsed.query)
        if query.get("page", [""])[0].casefold() == "manager" and query.get("download"):
            return base_url

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
            parsed_link = urlparse(absolute)
            query_link = parse_qs(parsed_link.query)
            if query_link.get("download") or absolute.endswith((".zip", ".dat", ".xml")):
                return absolute
        return None

    @staticmethod
    def _looks_like_dat_archive(data: bytes) -> bool:
        """Recognize the archive/XML signatures returned by DAT-o-MATIC."""
        if not data:
            return False
        stripped = data.lstrip()
        return (
            data.startswith(b"PK")
            or stripped.startswith(b"<?xml")
            or b"<datafile" in stripped[:4096].lower()
        )
