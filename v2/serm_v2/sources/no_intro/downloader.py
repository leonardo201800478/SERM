"""Download No-Intro DAT metadata from DAT-o-MATIC."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .errors import NoIntroDownloadError


@dataclass(frozen=True, slots=True)
class NoIntroDownload:
    """Describe a downloaded DAT without interpreting its contents."""

    system: str
    path: Path
    sha256: str
    source_url: str


class NoIntroDownloader:
    """Fetch No-Intro DAT files while keeping network concerns out of the parser."""

    BASE_URL = "https://datomatic.no-intro.org/"

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

    def discover_downloads(self, html: str, *, base_url: str | None = None) -> tuple[str, ...]:
        """Extract DAT download links from a DAT-o-MATIC download page."""
        base_url = base_url or self.BASE_URL
        links = re.findall(r'href=["\']([^"\']+\.(?:dat|xml)(?:\?[^"\']*)?)["\']', html, re.I)
        return tuple(urljoin(base_url, link) for link in links)
