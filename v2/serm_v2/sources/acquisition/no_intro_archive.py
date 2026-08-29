"""No-Intro bulk DAT acquisition from the maintained GitHub release archive."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)


class NoIntroArchiveError(RuntimeError):
    """Raised when the No-Intro bulk archive cannot be consumed."""


@dataclass(frozen=True, slots=True)
class NoIntroArchiveEntry:
    """Describe one DAT extracted from the No-Intro parent/clone archive."""

    name: str
    path: Path
    category: str = "No-Intro"


@dataclass(frozen=True, slots=True)
class NoIntroArchiveStatus:
    """Describe the local availability of an extracted No-Intro DAT."""

    entry: NoIntroArchiveEntry
    state: str


class NoIntroArchiveProvider:
    """Download one No-Intro archive and expose its DATs as local entries.

    The provider intentionally does not use DAT-o-MATIC, Selenium, Firefox,
    geckodriver or per-system HTTP endpoints. The release archive is the single
    acquisition operation; every accepted ``.dat`` is then copied to the stable
    local SERM No-Intro directory.
    """

    ARCHIVE_URL = (
        "https://github.com/hugo19941994/auto-datfile-generator/"
        "releases/latest/download/no-intro_parent-clone.zip"
    )
    USER_AGENT = "SERM/2.0"
    EXCLUDED_PREFIXES = (
        "Non-Redump -",
        "Source Code -",
        "Unofficial -",
    )
    EXCLUDED_MARKERS = (
        "(Development Kit",
        "(Updates and DLC)",
        "(Title Updates)",
    )

    def __init__(self, *, root: Path | None = None, timeout: int = 120) -> None:
        """Initialize the bulk archive provider and local cache paths."""
        default_root = Path(__file__).resolve().parents[3] / "data" / "sources" / "no_intro"
        self.root = Path(root).expanduser() if root else default_root
        self.dat_root = self.root / "dats"
        self.archive_path = self.root / "no-intro_parent-clone.zip"
        self.manifest_path = self.root / "manifest.json"
        self.timeout = timeout

    def fetch_catalog(self) -> tuple[NoIntroArchiveEntry, ...]:
        """Download the current bulk archive, extract accepted DATs and index them."""
        archive = self._download_archive()
        return self._extract_archive(archive)

    def match(
        self,
        systems: tuple[str, ...],
        entries: tuple[NoIntroArchiveEntry, ...] | None = None,
    ) -> tuple[NoIntroArchiveEntry, ...]:
        """Match LaunchBox platform names against extracted No-Intro DAT names."""
        source = entries if entries is not None else self.fetch_catalog()
        keys: set[str] = set()
        for system in systems:
            normalized = self._normalize(system)
            keys.add(normalized)
            keys.update(self._aliases(normalized))

        stripped = {self._strip_vendor(value) for value in keys}
        matches = tuple(
            entry
            for entry in source
            if self._matches_name(entry.name, keys, stripped)
        )
        logger.info(
            "[NO-INTRO][MATCH] LaunchBox=%d DATs=%d matches=%d",
            len(systems), len(source), len(matches),
        )
        return matches

    def status(self, entry: NoIntroArchiveEntry) -> NoIntroArchiveStatus:
        """Return whether the extracted DAT is available locally."""
        return NoIntroArchiveStatus(entry=entry, state="current" if entry.path.is_file() else "missing")

    def destination(self, entry: NoIntroArchiveEntry) -> Path:
        """Return the stable path used for an extracted DAT."""
        safe = re.sub(r"[^A-Za-z0-9._()\- ]+", "", Path(entry.name).name).strip()
        return self.dat_root / safe

    def download(self, entry: NoIntroArchiveEntry) -> NoIntroArchiveStatus:
        """Ensure the bulk archive is extracted and return the selected DAT status."""
        if not entry.path.is_file():
            self.fetch_catalog()
        refreshed = self._find_entry(entry.name)
        if refreshed is None or not refreshed.path.is_file():
            raise NoIntroArchiveError(f"DAT No-Intro não encontrado: {entry.name}")
        return NoIntroArchiveStatus(entry=refreshed, state="current")

    def update(self, entries: tuple[NoIntroArchiveEntry, ...]) -> tuple[NoIntroArchiveStatus, ...]:
        """Refresh the archive once and return the status of the requested DATs."""
        refreshed = self.fetch_catalog()
        requested = {entry.name.casefold() for entry in entries}
        return tuple(
            NoIntroArchiveStatus(entry=entry, state="current")
            for entry in refreshed
            if entry.name.casefold() in requested
        )

    def _download_archive(self) -> Path:
        """Download the single No-Intro release archive atomically."""
        self.root.mkdir(parents=True, exist_ok=True)
        logger.info("[NO-INTRO][ARCHIVE] GET %s", self.ARCHIVE_URL)
        request = urllib.request.Request(self.ARCHIVE_URL, headers={"User-Agent": self.USER_AGENT})
        temporary = self.archive_path.with_suffix(".zip.part")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = response.read()
        except (HTTPError, URLError, OSError) as exc:
            raise NoIntroArchiveError(f"Falha ao baixar o arquivo No-Intro: {exc}") from exc
        if not data.startswith(b"PK\x03\x04"):
            preview = data[:160].decode("utf-8", errors="replace").replace("\n", " ")
            raise NoIntroArchiveError(f"Download No-Intro inválido; esperado ZIP: {preview!r}")
        temporary.write_bytes(data)
        temporary.replace(self.archive_path)
        logger.info("[NO-INTRO][ARCHIVE] arquivo recebido bytes=%d", len(data))
        return self.archive_path

    def _extract_archive(self, archive_path: Path) -> tuple[NoIntroArchiveEntry, ...]:
        """Extract accepted DAT files and rebuild the local manifest."""
        if not archive_path.is_file():
            raise NoIntroArchiveError(f"Arquivo No-Intro não encontrado: {archive_path}")
        self.dat_root.mkdir(parents=True, exist_ok=True)
        entries: list[NoIntroArchiveEntry] = []
        temporary_paths: list[Path] = []
        try:
            with zipfile.ZipFile(archive_path) as archive:
                infos = [
                    info for info in archive.infolist()
                    if not info.is_dir() and info.filename.lower().endswith(".dat")
                ]
                if not infos:
                    raise NoIntroArchiveError("O arquivo No-Intro não contém DATs.")
                for info in infos:
                    name = Path(info.filename).name
                    if not self._accept(name):
                        continue
                    destination = self.dat_root / self._safe_filename(name)
                    temporary = destination.with_suffix(destination.suffix + ".part")
                    temporary.write_bytes(archive.read(info))
                    temporary_paths.append(temporary)
                    temporary.replace(destination)
                    entries.append(NoIntroArchiveEntry(name=name, path=destination))
        except (zipfile.BadZipFile, OSError, KeyError) as exc:
            raise NoIntroArchiveError(f"Falha ao extrair o arquivo No-Intro: {exc}") from exc
        finally:
            for path in temporary_paths:
                path.unlink(missing_ok=True)

        entries.sort(key=lambda item: self._normalize(item.name))
        archive_sha256 = self._sha256(archive_path)
        self.manifest_path.write_text(
            json.dumps(
                {
                    "archive_url": self.ARCHIVE_URL,
                    "archive_sha256": archive_sha256,
                    "dat_count": len(entries),
                    "dats": [entry.name for entry in entries],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        logger.info("[NO-INTRO][ARCHIVE] DATs extraídos=%d", len(entries))
        return tuple(entries)

    def _find_entry(self, name: str) -> NoIntroArchiveEntry | None:
        """Find an already extracted DAT by case-insensitive filename."""
        target = Path(name).name.casefold()
        for path in self.dat_root.glob("*.dat"):
            if path.name.casefold() == target:
                return NoIntroArchiveEntry(path.name, path)
        return None

    @classmethod
    def _accept(cls, name: str) -> bool:
        """Return whether a DAT belongs to the official parent/clone set."""
        if not name.lower().endswith(".dat"):
            return False
        if any(name.startswith(prefix) for prefix in cls.EXCLUDED_PREFIXES):
            return False
        return not any(marker in name for marker in cls.EXCLUDED_MARKERS)

    @staticmethod
    def _safe_filename(name: str) -> str:
        """Keep the DAT filename while removing filesystem-unsafe characters."""
        safe = re.sub(r"[<>:\"/\\|?*]", "", name).strip()
        return safe or "unknown.dat"

    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize a platform/DAT name for deterministic matching."""
        value = Path(value).stem
        value = re.sub(r"\s*\([^)]*\d{8}-\d{6}\)\s*$", "", value)
        value = re.sub(r"\s*\(Parent-Clone\)\s*$", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s+", " ", value)
        value = value.casefold().replace("&", "and")
        return re.sub(r"[^a-z0-9]+", " ", value).strip()

    @classmethod
    def _strip_vendor(cls, value: str) -> str:
        """Remove common manufacturer prefixes from a normalized name."""
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
        """Return common LaunchBox aliases."""
        return {
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
            "playstation portable": {"sony playstation portable"},
            "psp": {"sony playstation portable"},
            "nintendo ds": {"nintendo ds"},
            "game boy": {"game boy"},
            "game boy color": {"game boy color"},
            "game boy advance": {"game boy advance"},
            "mega drive": {"sega mega drive genesis"},
            "sega cd": {"sega mega cd sega cd"},
        }.get(value, set())

    @classmethod
    def _matches_name(cls, name: str, keys: set[str], stripped: set[str]) -> bool:
        """Match a DAT filename while ignoring format/date suffixes."""
        normalized = cls._normalize(name)
        if normalized in keys:
            return True
        if cls._strip_vendor(normalized) in stripped:
            return True
        # Parent/clone archives contain format qualifiers such as Headered,
        # BigEndian and Decrypted. Match the platform prefix as a controlled
        # fallback without turning arbitrary substrings into matches.
        for key in keys:
            if normalized.startswith(f"{key} "):
                suffix = normalized[len(key):].strip()
                if suffix in {
                    "headered", "headerless", "bigendian", "byteswapped", "decrypted",
                    "encrypted", "parent clone", "parent clone headered",
                }:
                    return True
        return False

    @staticmethod
    def _sha256(path: Path) -> str:
        """Calculate SHA-256 for the cached archive."""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
