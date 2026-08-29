"""Download No-Intro DAT metadata from DAT-o-MATIC."""
from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
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
    status: int
    headers: dict[str, str]


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
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": self.BASE_URL,
        }
        logger.info("[NO-INTRO][DAT] selecionando sistema=%s", system)

        # DAT-o-MATIC requires the initial Standard DAT GET before the
        # selection POST. This establishes the session/form state used by the
        # following POST requests. Omitting it can produce a valid HTTP 200
        # response while silently discarding the selected system.
        standard = self._request_get(opener, self.STANDARD_DAT_URL, headers)
        logger.debug(
            "[NO-INTRO][HTTP] GET standard status=%d url=%s bytes=%d",
            standard.status,
            standard.url,
            len(standard.body),
        )

        selected = self._request_form(
            opener,
            self.STANDARD_DAT_URL,
            {"sel_s": system},
            headers,
            stage="seleção",
        )
        logger.info(
            "[NO-INTRO][DAT] seleção recebida status=%d url=%s bytes=%d",
            selected.status,
            selected.url,
            len(selected.body),
        )
        self._log_page_diagnostics("seleção", selected.body, selected.url)

        prepared = self._request_form(
            opener,
            self.STANDARD_DAT_URL,
            self.DEFAULT_FILTERS,
            {**headers, "Referer": selected.url},
            stage="Prepare",
        )
        logger.info(
            "[NO-INTRO][DAT] preparação recebida status=%d url=%s bytes=%d",
            prepared.status,
            prepared.url,
            len(prepared.body),
        )
        self._log_page_diagnostics("Prepare", prepared.body, prepared.url)

        data_url = self._find_download_url(prepared.body, prepared.url)
        if data_url is None:
            parsed = urlparse(prepared.url)
            logger.error(
                "[NO-INTRO][DAT] URL de download ausente sistema=%s "
                "final_url=%s page=%s download=%s",
                system,
                prepared.url,
                parse_qs(parsed.query).get("page", [""])[0],
                parse_qs(parsed.query).get("download", [""])[0],
            )
            raise NoIntroDownloadError(
                f"DAT-o-MATIC não apresentou link de download para '{system}'. "
                "Verifique o log [NO-INTRO][HTTP]/[DIAG]."
            )

        logger.info("[NO-INTRO][DAT] URL de download resolvida=%s", data_url)
        data = self._download_with_retry(opener, data_url, headers, system)

        if not self._looks_like_dat_archive(data.body):
            content_type = data.headers.get("Content-Type", "")
            logger.warning(
                "[NO-INTRO][DAT] resposta inesperada sistema=%s bytes=%d "
                "content_type=%s url=%s",
                system,
                len(data.body),
                content_type,
                data.url,
            )
            raise NoIntroDownloadError(
                f"Resposta inválida para o DAT de '{system}' "
                "(não é ZIP/XML/DAT reconhecível)."
            )

        destination.write_bytes(data.body)
        digest = hashlib.sha256(data.body).hexdigest()
        logger.info(
            "[NO-INTRO][DAT] OK sistema=%s bytes=%d sha256=%s arquivo=%s",
            system,
            len(data.body),
            digest,
            destination,
        )
        return NoIntroDownload(system=system, path=destination, sha256=digest, source_url=data.url)

    @staticmethod
    def _request_get(opener, url: str, headers: dict[str, str]) -> _HttpResult:
        """Perform the initial DAT-o-MATIC GET that establishes session state."""
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
            raise NoIntroDownloadError(f"Falha no GET inicial do DAT-o-MATIC: {url}") from exc

    @classmethod
    def _request_form(
        cls,
        opener,
        url: str,
        values: dict[str, str],
        headers: dict[str, str],
        *,
        stage: str,
    ) -> _HttpResult:
        """POST one DAT-o-MATIC form and return its final URL and body."""
        payload = urlencode(values).encode("utf-8")
        logger.debug(
            "[NO-INTRO][HTTP] POST stage=%s url=%s fields=%s",
            stage,
            url,
            ",".join(values),
        )
        last_exc: Exception | None = None
        for attempt in range(1, cls.REQUEST_RETRIES + 1):
            request = Request(
                url,
                data=payload,
                headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
            )
            try:
                with opener.open(request, timeout=60) as response:
                    result = _HttpResult(
                        response.geturl(),
                        response.read(),
                        response.status,
                        dict(response.headers.items()),
                    )
                logger.debug(
                    "[NO-INTRO][HTTP] POST stage=%s tentativa=%d status=%d "
                    "final_url=%s bytes=%d",
                    stage,
                    attempt,
                    result.status,
                    result.url,
                    len(result.body),
                )
                return result
            except (HTTPError, URLError, OSError) as exc:
                last_exc = exc
                logger.warning(
                    "[NO-INTRO][HTTP] POST stage=%s tentativa=%d/%d falhou: %s",
                    stage,
                    attempt,
                    cls.REQUEST_RETRIES,
                    exc,
                )
                if attempt < cls.REQUEST_RETRIES:
                    time.sleep(cls.RETRY_DELAY_SECONDS * attempt)
        raise NoIntroDownloadError(f"Falha na etapa POST ({stage}) do DAT-o-MATIC: {url}") from last_exc

    @classmethod
    def _download_with_retry(cls, opener, url: str, headers: dict[str, str], system: str) -> _HttpResult:
        """Download the generated DAT with limited retry/backoff for transient failures."""
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
    def _log_page_diagnostics(stage: str, body: bytes, url: str) -> None:
        """Log compact diagnostics when DAT-o-MATIC returns unexpected HTML."""
        text = body.decode("utf-8", errors="replace")
        title = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
        forms = len(re.findall(r"<form\b", text, re.I))
        inputs = len(re.findall(r"<input\b", text, re.I))
        manager = bool(re.search(r"page=manager|name=[\"']download[\"']", text, re.I))
        logger.debug(
            "[NO-INTRO][DIAG] stage=%s url=%s title=%r forms=%d inputs=%d manager_hint=%s",
            stage,
            url,
            re.sub(r"\s+", " ", title.group(1)).strip()[:160] if title else None,
            forms,
            inputs,
            manager,
        )

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
