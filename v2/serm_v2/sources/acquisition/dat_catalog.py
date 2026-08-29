"""Public DAT Catalog acquisition backend for SERM."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
import unicodedata
import urllib.request
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
    """Describe whether one local DAT matches the remote catalog entry."""

    entry: DatCatalogEntry
    path: Path
    state: str
    local_sha256: str | None = None


class PublicDatCatalogProvider:
    """Acquire DATs from the public Git-backed DAT catalog."""

    INDEX_URL_TEMPLATE = (
        "https://raw.githubusercontent.com/videogame-archive/dat-catalog/"
        "main/root/basic/{category}/index.csv"
    )
    USER_AGENT = "SERM/2.0"

    def __init__(self, *, root: Path | None = None, timeout: int = 30) -> None:
        """Initialize the provider and its local DAT/manifest directory."""
        self.root = Path(root).expanduser() if root else self._default_root()
        self.timeout = timeout
        self.manifest_path = self.root / "manifest.json"

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
        request = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except (HTTPError, URLError, OSError) as exc:
            raise DatCatalogError(
                f"Falha ao obter índice {category} do Public DAT Catalog: {exc}"
            ) from exc
        entries = self._parse_index(payload.decode("utf-8-sig"), category=category)
        logger.info(
            "[DAT-CATALOG][CATALOG] %s DATs disponíveis=%d", category, len(entries)
        )
        if not entries:
            raise DatCatalogError(
                f"O índice do Public DAT Catalog não contém DATs {category}."
            )
        return entries

    @classmethod
    def _parse_index(
        cls, text: str, *, category: str = "No-Intro"
    ) -> tuple[DatCatalogEntry, ...]:
        """Extract DAT files from the requested catalog section.

        No-Intro's index is a mixed CSV containing several directory sections.
        Only FILE rows belonging to the No-Intro directory are accepted.
        Other categories, such as Redump, publish their DAT files at the
        category root, so root files are accepted for those categories.
        """
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

            if kind != "FILE" or name.casefold() == "modified" or not name.lower().endswith(".dat"):
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

            entries.append(
                DatCatalogEntry(
                    name=name,
                    url=cls._normalize_url(url),
                    crc32=crc32,
                    size=size,
                    category=category,
                )
            )
        return tuple(entries)

    def match(
        self,
        systems: tuple[str, ...],
        entries: tuple[DatCatalogEntry, ...] | None = None,
    ) -> tuple[DatCatalogEntry, ...]:
        """Match LaunchBox system names against DAT filenames."""
        entries = entries if entries is not None else self.fetch_catalog()
        launchbox_keys: set[str] = set()
        for system in systems:
            key = self._normalize(system)
            launchbox_keys.add(key)
            launchbox_keys.update(self._aliases(key))
        aliases = {self._strip_vendor(key) for key in launchbox_keys}
        matches: list[DatCatalogEntry] = []
        for entry in entries:
            stem = self._normalize(Path(entry.name).stem)
            if stem in launchbox_keys or self._strip_vendor(stem) in aliases:
                matches.append(entry)
        logger.info(
            "[DAT-CATALOG][MATCH] LaunchBox=%d | DATs=%d | matches=%d",
            len(systems),
            len(entries),
            len(matches),
        )
        return tuple(matches)

    def status(self, entry: DatCatalogEntry) -> DatStatus:
        """Compare one local DAT with the CRC and size published by the catalog."""
        path = self.destination(entry)
        if not path.is_file():
            return DatStatus(entry=entry, path=path, state="missing")
        if path.stat().st_size != entry.size or self._crc32(path) != entry.crc32:
            return DatStatus(entry=entry, path=path, state="outdated")
        return DatStatus(
            entry=entry,
            path=path,
            state="current",
            local_sha256=self._sha256(path),
        )

    def download(self, entry: DatCatalogEntry) -> DatStatus:
        """Download one DAT, validate size/CRC, and update the manifest."""
        destination = self.destination(entry)
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_suffix(destination.suffix + ".part")
        url = self._normalize_url(entry.url)
        logger.info("[DAT-CATALOG][HTTP] GET %s", url)
        request = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = response.read()
        except (HTTPError, URLError, OSError) as exc:
            raise DatCatalogError(f"Falha ao baixar '{entry.name}': {exc}") from exc
        if len(data) != entry.size:
            raise DatCatalogError(
                f"Tamanho inválido para '{entry.name}': esperado={entry.size}, recebido={len(data)}"
            )
        crc32 = zlib.crc32(data) & 0xFFFFFFFF
        if crc32 != entry.crc32:
            raise DatCatalogError(
                f"CRC inválido para '{entry.name}': esperado={entry.crc32}, recebido={crc32}"
            )
        partial.write_bytes(data)
        partial.replace(destination)
        status = self.status(entry)
        if status.state != "current":
            raise DatCatalogError(f"DAT baixado não passou na validação: {entry.name}")
        self._write_manifest(entry, status)
        return status

    def update(self, entries: tuple[DatCatalogEntry, ...]) -> tuple[DatStatus, ...]:
        """Download only missing or outdated DATs."""
        results: list[DatStatus] = []
        for entry in entries:
            status = self.status(entry)
            results.append(status if status.state == "current" else self.download(entry))
        return tuple(results)

    def destination(self, entry: DatCatalogEntry) -> Path:
        """Return the stable local path for a catalog DAT."""
        safe = re.sub(r"[^A-Za-z0-9._()\- ]+", "", Path(entry.name).stem).strip()
        return self.root / f"{safe}.dat"

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Percent-encode unsafe URL path characters without altering its structure."""
        parts = urlsplit(url.strip())
        path = quote(parts.path, safe="/%:@-._~!$&'()*+,;=")
        return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))

    def _write_manifest(self, entry: DatCatalogEntry, status: DatStatus) -> None:
        """Persist remote provenance for diagnostics and future auditing."""
        manifest: dict[str, dict[str, object]] = {}
        if self.manifest_path.is_file():
            try:
                manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                manifest = {}
        manifest[entry.name] = {
            "category": entry.category,
            "url": entry.url,
            "crc32": entry.crc32,
            "size": entry.size,
            "sha256": status.local_sha256,
        }
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @staticmethod
    def _crc32(path: Path) -> int:
        """Calculate the unsigned CRC32 of a local DAT."""
        value = 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                value = zlib.crc32(chunk, value)
        return value & 0xFFFFFFFF

    @staticmethod
    def _sha256(path: Path) -> str:
        """Calculate the SHA-256 digest of a local DAT."""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize names for deterministic LaunchBox matching."""
        value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        value = value.casefold().replace("&", "and")
        return re.sub(r"[^a-z0-9]+", " ", value).strip()

    @classmethod
    def _strip_vendor(cls, value: str) -> str:
        """Strip common manufacturer prefixes from normalized DAT names."""
        prefixes = (
            "sony ", "nintendo ", "sega ", "microsoft ", "nec ", "panasonic ",
            "philips ", "snk ", "commodore ", "bandai ", "atari ", "fujitsu ",
            "mattel ", "apple ", "ibm ", "vm labs ", "vtech ", "tomy ",
        )
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
            "gamecube": {"nintendo gamecube"},
            "game cube": {"nintendo gamecube"},
            "wii": {"nintendo wii"},
            "saturn": {"sega saturn"},
            "dreamcast": {"sega dreamcast"},
        }
        return aliases.get(value, set())
