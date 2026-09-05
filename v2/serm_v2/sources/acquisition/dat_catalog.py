"""Public DAT Catalog acquisition backend for SERM."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
import time
import unicodedata
import urllib.request
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit

logger = logging.getLogger(__name__)


class DatCatalogError(RuntimeError):
    """Raised when the Public DAT Catalog cannot be consumed."""


@dataclass(frozen=True, slots=True)
class DatCatalogEntry:
    """Describe one DAT published by the Public DAT Catalog."""

    name: str
    url: str
    crc32: int
    size: int
    category: str = "No-Intro"


@dataclass(frozen=True, slots=True)
class DatStatus:
    """Describe the local acquisition state of a DAT."""

    entry: DatCatalogEntry
    path: Path
    state: str
    local_sha256: str | None = None


class _RedirectPolicy(urllib.request.HTTPRedirectHandler):
    """Permite redirects HTTP/HTTPS sem alterar o comportamento do cliente."""


class PublicDatCatalogProvider:
    """Acquire DATs from the public Git-backed DAT catalog."""

    INDEX_URL_TEMPLATE = (
        "https://raw.githubusercontent.com/videogame-archive/dat-catalog/"
        "main/root/basic/{category}/index.csv"
    )
    USER_AGENT = "SERM/2.0 (DAT downloader)"
    STALE_REPOSITORY_HOST = "open-retrogaming-archive/dat-catalog"
    CANONICAL_REPOSITORY_HOST = "videogame-archive/dat-catalog"
    RETRIES = 3
    RETRY_DELAY_SECONDS = 0.75

    def __init__(self, *, root: Path | None = None, timeout: int = 30) -> None:
        """Initialize the provider and its local DAT/manifest directory."""
        self.root = Path(root).expanduser() if root else self._default_root()
        self.timeout = timeout
        self.manifest_path = self.root / "manifest.json"
        self._opener = urllib.request.build_opener(_RedirectPolicy())

    @staticmethod
    def _default_root() -> Path:
        """Return the repository-local No-Intro DAT directory."""
        return Path(__file__).resolve().parents[3] / "data" / "sources" / "no_intro" / "dats"

    def fetch_catalog(self, category: str = "No-Intro") -> tuple[DatCatalogEntry, ...]:
        """Download and parse the current DAT Catalog section."""
        if not category or any(
            char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_"
            for char in category
        ):
            raise ValueError(f"Categoria de catálogo inválida: {category!r}")
        url = self.INDEX_URL_TEMPLATE.format(category=quote(category, safe=""))
        logger.info("[DAT-CATALOG][HTTP] GET %s", url)
        request = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT, "Accept": "text/csv,*/*;q=0.8"})
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                payload = response.read()
        except (HTTPError, URLError, OSError) as exc:
            raise DatCatalogError(f"Falha ao obter índice {category}: {exc}") from exc
        entries = self._parse_index(payload.decode("utf-8-sig"), category=category)
        logger.info("[DAT-CATALOG][CATALOG] %s DATs disponíveis=%d", category, len(entries))
        if not entries:
            raise DatCatalogError(f"O índice não contém DATs {category}.")
        return entries

    @classmethod
    def _parse_index(cls, text: str, *, category: str = "No-Intro") -> tuple[DatCatalogEntry, ...]:
        """Extract DAT files belonging to the requested catalog category."""
        reader = csv.DictReader(io.StringIO(text))
        entries: list[DatCatalogEntry] = []
        current_directory: str | None = None
        is_no_intro = cls._normalize(category) == cls._normalize("No-Intro")
        for row in reader:
            kind = (row.get("Type") or "").strip().upper()
            name = (row.get("Name") or "").strip()
            if kind == "DIRECTORY":
                current_directory = name
                continue
            if kind != "FILE" or not name.lower().endswith(".dat"):
                continue
            if is_no_intro and current_directory != "No-Intro":
                continue
            url = (row.get("URL") or "").strip()
            if not url:
                continue
            try:
                crc32 = int((row.get("CRC") or "0").strip())
                size = int((row.get("Size") or "0").strip())
            except ValueError:
                logger.warning("[DAT-CATALOG][CATALOG] metadados inválidos: %s", name)
                continue
            entries.append(DatCatalogEntry(name, cls._normalize_url(url), crc32, size, category))
        return tuple(entries)

    def match(self, systems: tuple[str, ...], entries: tuple[DatCatalogEntry, ...] | None = None) -> tuple[DatCatalogEntry, ...]:
        """Match LaunchBox system names against DAT filenames."""
        entries = entries if entries is not None else self.fetch_catalog()
        keys: set[str] = set()
        for system in systems:
            key = self._normalize(system)
            keys.add(key)
            keys.update(self._aliases(key))
        aliases = {self._strip_vendor(key) for key in keys}
        matches = tuple(
            entry for entry in entries
            if self._normalize(Path(entry.name).stem) in keys
            or self._strip_vendor(self._normalize(Path(entry.name).stem)) in aliases
        )
        logger.info("[DAT-CATALOG][MATCH] LaunchBox=%d | DATs=%d | matches=%d", len(systems), len(entries), len(matches))
        return matches

    def status(self, entry: DatCatalogEntry) -> DatStatus:
        """Determine freshness from manifest provenance, with local CRC/size fallback."""
        path = self.destination(entry)
        if not path.is_file():
            return DatStatus(entry, path, "missing")
        recorded = self._read_manifest().get(entry.name)
        if not recorded:
            if path.stat().st_size == entry.size and self._crc32(path) == entry.crc32:
                return DatStatus(entry, path, "current", self._sha256(path))
            return DatStatus(entry, path, "outdated")
        if (
            recorded.get("crc32") != entry.crc32
            or recorded.get("size") != entry.size
            or recorded.get("url") != entry.url
        ):
            return DatStatus(entry, path, "outdated")
        return DatStatus(entry, path, "current", recorded.get("sha256"))

    def download(self, entry: DatCatalogEntry) -> DatStatus:
        """Download a DAT or ZIP, extract a DAT when necessary, and record provenance."""
        destination = self.destination(entry)
        destination.parent.mkdir(parents=True, exist_ok=True)
        url = self._normalize_url(entry.url)
        logger.info("[DAT-CATALOG][HTTP] GET %s", url)
        data, content_type, resolved_url = self._get_with_retry(url)
        dat_data = self._extract_dat(data, entry.name, content_type)
        partial = destination.with_suffix(destination.suffix + ".part")
        partial.write_bytes(dat_data)
        partial.replace(destination)
        sha256 = self._sha256(destination)
        self._write_manifest(entry, sha256, len(data), zlib.crc32(data) & 0xFFFFFFFF, resolved_url)
        logger.info(
            "[DAT-CATALOG][OK] name=%s bytes=%d resolved=%s sha256=%s",
            entry.name,
            len(dat_data),
            resolved_url,
            sha256[:16],
        )
        return DatStatus(entry, destination, "current", sha256)

    def _get_with_retry(self, url: str) -> tuple[bytes, str, str]:
        """Fetch bytes with retries for transient transport failures and expose the final URL."""
        last_error: Exception | None = None
        current_url = url
        for attempt in range(1, self.RETRIES + 1):
            started = time.perf_counter()
            request = urllib.request.Request(
                current_url,
                headers={
                    "User-Agent": self.USER_AGENT,
                    "Accept": "application/zip,application/octet-stream,application/x-zip-compressed,text/plain,*/*;q=0.5",
                    "Accept-Encoding": "identity",
                    "Connection": "keep-alive",
                },
            )
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    data = response.read()
                    content_type = response.headers.get("Content-Type", "")
                    resolved = response.geturl()
                elapsed = time.perf_counter() - started
                logger.info(
                    "[DAT-CATALOG][HTTP] OK attempt=%d status=%s bytes=%d elapsed=%.3fs final=%s",
                    attempt,
                    getattr(response, "status", "?"),
                    len(data),
                    elapsed,
                    resolved,
                )
                return data, content_type, resolved
            except HTTPError as exc:
                elapsed = time.perf_counter() - started
                body_preview = b""
                try:
                    body_preview = exc.read(256)
                except OSError:
                    pass
                logger.warning(
                    "[DAT-CATALOG][HTTP] HTTPError attempt=%d status=%s reason=%s elapsed=%.3fs url=%s body=%r",
                    attempt,
                    exc.code,
                    exc.reason,
                    elapsed,
                    current_url,
                    body_preview[:120],
                )
                if exc.code in {403, 404}:
                    raise DatCatalogError(
                        f"HTTP {exc.code} {exc.reason} ao baixar URL: {current_url}"
                    ) from exc
                last_error = exc
            except (URLError, OSError) as exc:
                elapsed = time.perf_counter() - started
                logger.warning(
                    "[DAT-CATALOG][HTTP] transport-error attempt=%d elapsed=%.3fs url=%s error=%r",
                    attempt,
                    elapsed,
                    current_url,
                    exc,
                )
                last_error = exc
            if attempt < self.RETRIES:
                time.sleep(self.RETRY_DELAY_SECONDS * attempt)
        if last_error is not None:
            raise DatCatalogError(f"Falha ao baixar URL: {current_url} | {last_error}") from last_error
        raise DatCatalogError(f"Falha ao baixar URL: {current_url}")

    @staticmethod
    def _is_pointer(data: bytes, content_type: str) -> bool:
        """Identify a catalog relative pointer without mistaking DAT/XML content."""
        if "html" in content_type.lower():
            return False
        try:
            value = data.decode("utf-8-sig").strip()
        except UnicodeDecodeError:
            return False
        return bool(value) and "\n" not in value and "\r" not in value and value.lower().endswith(".dat") and (
            value.startswith("../") or value.startswith("./") or value.startswith("normalized/")
        )

    @staticmethod
    def _extract_dat(data: bytes, entry_name: str, content_type: str) -> bytes:
        """Return the DAT payload from either direct content or a ZIP archive."""
        if not data:
            raise DatCatalogError(f"Resposta vazia ao baixar '{entry_name}'.")
        if data.startswith(b"PK\x03\x04") or "zip" in content_type.lower():
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    candidates = [
                        info for info in archive.infolist()
                        if not info.is_dir() and info.filename.lower().endswith(".dat")
                    ]
                    if not candidates:
                        raise DatCatalogError(f"ZIP de '{entry_name}' não contém arquivo DAT.")
                    wanted = Path(entry_name).name.casefold()
                    candidate = next((item for item in candidates if Path(item.filename).name.casefold() == wanted), candidates[0])
                    payload = archive.read(candidate)
            except (zipfile.BadZipFile, OSError, KeyError) as exc:
                raise DatCatalogError(f"ZIP inválido para '{entry_name}'.") from exc
            if not PublicDatCatalogProvider._looks_like_dat(payload):
                raise DatCatalogError(f"Arquivo extraído de '{entry_name}' não é um DAT válido.")
            return payload
        if not PublicDatCatalogProvider._looks_like_dat(data):
            preview = data[:120].decode("utf-8", errors="replace").replace("\n", " ")
            raise DatCatalogError(f"Resposta inválida para '{entry_name}' (não é DAT/ZIP): {preview!r}")
        return data

    @staticmethod
    def _looks_like_dat(data: bytes) -> bool:
        """Recognize common DAT/XML headers and reject arbitrary text/HTML."""
        sample = data[:4096].lstrip(b"\xef\xbb\xbf \t\r\n")
        lowered = sample.lower()
        return lowered.startswith(b"clrmamepro (") or lowered.startswith(b"<datafile") or lowered.startswith(b"<?xml") or b"<clrmamepro>" in lowered[:512]

    def _read_manifest(self) -> dict[str, dict[str, object]]:
        """Read the local DAT provenance manifest."""
        if not self.manifest_path.is_file():
            return {}
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}

    def destination(self, entry: DatCatalogEntry) -> Path:
        """Return the stable local path for a catalog DAT."""
        safe = re.sub(r"[^A-Za-z0-9._()\- ]+", "", Path(entry.name).stem).strip()
        return self.root / f"{safe}.dat"

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Percent-encode unsafe URL path characters without changing its structure."""
        parts = urlsplit(url.strip())
        path = quote(parts.path, safe="/%:@-._~!$&'()*+,;=")
        return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))

    def _write_manifest(self, entry: DatCatalogEntry, sha256: str, downloaded_size: int, downloaded_crc32: int, resolved_url: str) -> None:
        """Persist remote and resolved artifact provenance."""
        manifest = self._read_manifest()
        manifest[entry.name] = {
            "category": entry.category,
            "url": entry.url,
            "resolved_url": resolved_url,
            "crc32": entry.crc32,
            "size": entry.size,
            "downloaded_size": downloaded_size,
            "downloaded_crc32": downloaded_crc32,
            "sha256": sha256,
        }
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _sha256(path: Path) -> str:
        """Calculate the SHA-256 digest of a local DAT."""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _crc32(path: Path) -> int:
        """Calculate an unsigned CRC32 for a local DAT."""
        value = 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                value = zlib.crc32(chunk, value)
        return value & 0xFFFFFFFF

    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize names for deterministic LaunchBox matching."""
        value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        value = value.casefold().replace("&", "and")
        return re.sub(r"[^a-z0-9]+", " ", value).strip()

    @classmethod
    def _strip_vendor(cls, value: str) -> str:
        """Strip common manufacturer prefixes from normalized DAT names."""
        prefixes = ("sony ", "nintendo ", "sega ", "microsoft ", "nec ", "panasonic ", "philips ", "snk ", "commodore ", "bandai ", "atari ", "fujitsu ", "mattel ", "apple ", "ibm ", "vm labs ", "vtech ", "tomy ")
        for prefix in prefixes:
            if value.startswith(prefix):
                return value[len(prefix):]
        return value

    @classmethod
    def _aliases(cls, value: str) -> set[str]:
        """Return normalized aliases for common LaunchBox platform names."""
        aliases = {
            "nes": {"nintendo entertainment system", "nintendo nintendo entertainment system"},
            "famicom": {"nintendo entertainment system", "nintendo nintendo entertainment system"},
            "snes": {"super nintendo entertainment system", "nintendo super nintendo entertainment system"},
            "super nes": {"super nintendo entertainment system", "nintendo super nintendo entertainment system"},
            "genesis": {"mega drive genesis", "sega mega drive genesis"},
            "sega genesis": {"mega drive genesis", "sega mega drive genesis"},
            "sms": {"master system mark iii", "sega master system mark iii"},
            "master system": {"master system mark iii", "sega master system mark iii"},
            "playstation": {"sony playstation"},
            "psx": {"sony playstation"},
            "ps1": {"sony playstation"},
            "playstation 2": {"sony playstation 2"},
            "ps2": {"sony playstation 2"},
            "playstation 3": {"sony playstation 3"},
            "ps3": {"sony playstation 3"},
            "playstation portable": {"sony playstation portable"},
            "psp": {"sony playstation portable"},
            "dreamcast": {"sega dreamcast"},
            "saturn": {"sega saturn"},
            "gamecube": {"nintendo gamecube"},
            "3do": {"3do interactive multiplayer", "panasonic 3do interactive multiplayer"},
            "jaguar cd": {"atari jaguar cd interactive multimedia system"},
            "atari jaguar cd": {"atari jaguar cd interactive multimedia system"},
            "amiga cd": {"commodore amiga cd"},
            "amiga cd32": {"commodore amiga cd32"},
            "amiga cdtv": {"commodore amiga cdtv"},
            "pc engine cd": {"nec pc engine cd and turbografx cd"},
            "turbografx cd": {"nec pc engine cd and turbografx cd"},
            "pc engine cd and turbografx cd": {"nec pc engine cd and turbografx cd"},
            "pc fx": {"nec pc fx and pc fxga"},
            "pc fxga": {"nec pc fx and pc fxga"},
            "nec pc fx": {"nec pc fx and pc fxga"},
            "mega cd": {"sega mega cd and sega cd"},
            "sega cd": {"sega mega cd and sega cd"},
            "mega cd and sega cd": {"sega mega cd and sega cd"},
            "cdi": {"philips cd i"},
            "cd i": {"philips cd i"},
            "xbox": {"microsoft xbox"},
            "xbox 360": {"microsoft xbox 360"},
            "naomi": {"sega naomi"},
            "naomi 2": {"sega naomi 2"},
            "neo geo cd": {"neo geo cd"},
        }
        return aliases.get(value, set())


__all__ = ["DatCatalogEntry", "DatCatalogError", "DatStatus", "PublicDatCatalogProvider"]
