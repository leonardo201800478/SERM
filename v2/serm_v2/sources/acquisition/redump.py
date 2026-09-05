"""Redump DAT acquisition through Redump's direct datfile endpoints."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .dat_catalog import DatCatalogEntry, DatCatalogError, DatStatus, PublicDatCatalogProvider


class RedumpError(DatCatalogError):
    """Raised when a Redump DAT cannot be discovered or downloaded."""


@dataclass(frozen=True, slots=True)
class RedumpEntry:
    """Describe one Redump DAT and its direct Redump download endpoint."""

    name: str
    url: str
    crc32: int
    size: int
    category: str = "Redump"

    @classmethod
    def from_catalog(cls, entry: DatCatalogEntry) -> RedumpEntry:
        """Convert a catalog entry and replace its mirror URL with Redump's direct endpoint."""
        direct_url = RedumpProvider.direct_url_for_name(entry.name)
        if direct_url is None:
            raise RedumpError(
                f"Não existe endpoint Redump conhecido para '{entry.name}'."
            )
        return cls(entry.name, direct_url, entry.crc32, entry.size, entry.category)

    def as_catalog_entry(self) -> DatCatalogEntry:
        """Convert this Redump entry to the generic acquisition model."""
        return DatCatalogEntry(self.name, self.url, self.crc32, self.size, self.category)


class RedumpProvider:
    """Discover Redump systems from the public catalog and download DATs directly.

    The public DAT Catalog remains the machine-readable discovery source, but it
    is never used to acquire the Redump payload. Downloads go to Redump's
    ``/datfile/<system>/`` endpoint, which returns the ZIP containing the DAT.
    This avoids the GitHub normalized/basic mirror and avoids browser download
    reputation checks, Selenium and CAPTCHA handling.
    """

    # Prefer HTTPS explicitly. The previous HTTP endpoint was consistently
    # subject to long TCP connection timeouts on some direct ISP routes, while
    # browser/VPN HTTPS access was responsive. HTTPS also avoids relying on a
    # server-side HTTP -> HTTPS redirect before the actual DAT is transferred.
    REDUMP_DAT_BASE_URL = "https://redump.org/datfile"

    # Redump's platform codes.  These are stable endpoint identifiers and are
    # intentionally kept separate from LaunchBox names and DAT filenames.
    SYSTEM_CODES: dict[str, str] = {
        "Acorn Archimedes.dat": "arch",
        "Apple Macintosh.dat": "mac",
        "Atari Jaguar CD Interactive Multimedia System.dat": "ajcd",
        "Bandai Pippin.dat": "pippin",
        "Bandai Playdia Quick Interactive System.dat": "qis",
        "Commodore Amiga CD.dat": "acd",
        "Commodore Amiga CD32.dat": "cd32",
        "Commodore Amiga CDTV.dat": "cdtv",
        "funworld Photo Play.dat": "fpp",
        "Fujitsu FM Towns series.dat": "fmt",
        "IBM PC compatible.dat": "pc",
        "Incredible Technologies Eagle.dat": "ite",
        "Konami e-Amusement.dat": "kea",
        "Konami FireBeat.dat": "kfb",
        "Konami M2.dat": "km2",
        "Konami System 573.dat": "ks573",
        "Konami System GV.dat": "ksgv",
        "Konami Twinkle.dat": "kt",
        "Mattel Fisher-Price iXL.dat": "ixl",
        "Mattel HyperScan.dat": "hs",
        "Memorex Visual Information System.dat": "vis",
        "Microsoft Xbox.dat": "xbox",
        "Microsoft Xbox 360.dat": "xbox360",
        "Namco · Sega · Nintendo Triforce.dat": "trf",
        "Namco System 246.dat": "ns246",
        "Namco System 12.dat": "ns12",
        "NEC PC-88 series.dat": "pc-88",
        "NEC PC-98 series.dat": "pc-98",
        "NEC PC Engine CD & TurboGrafx CD.dat": "pce",
        "NEC PC-FX & PC-FXGA.dat": "pc-fx",
        "Neo Geo CD.dat": "ngcd",
        "Nintendo GameCube.dat": "gc",
        "Nintendo Wii.dat": "wii",
        "Panasonic 3DO Interactive Multiplayer.dat": "3do",
        "Palm OS.dat": "palm",
        "Philips CD-i.dat": "cdi",
        "Photo CD.dat": "photo-cd",
        "Pocket PC.dat": "ppc",
        "PlayStation GameShark Updates.dat": "psxgs",
        "Sega Chihiro.dat": "chihiro",
        "Sega Dreamcast.dat": "dc",
        "Sega Lindbergh.dat": "lindbergh",
        "Sega Mega CD & Sega CD.dat": "mcd",
        "Sega Naomi.dat": "naomi",
        "Sega Naomi 2.dat": "naomi2",
        "Sega Prologue 21 Multimedia Karaoke System.dat": "sp21",
        "Sega RingEdge.dat": "sre",
        "Sega RingEdge 2.dat": "sre2",
        "Sega Saturn.dat": "ss",
        "Sharp X68000.dat": "x68k",
        "Sony PlayStation.dat": "psx",
        "Sony PlayStation 2.dat": "ps2",
        "Sony PlayStation 3.dat": "ps3",
        "Sony PlayStation Portable.dat": "psp",
        "TAB-Austria Quizard.dat": "quizard",
        "Tomy Kiss-Site.dat": "ksite",
        "VTech V.Flash & V.Smile Pro.dat": "vflash",
        "VM Labs NUON.dat": "nuon",
        "ZAPiT Games Game Wave Family Entertainment System.dat": "gamewave",
    }

    def __init__(self, *, root: Path | None = None, timeout: int = 60) -> None:
        """Initialize the provider and its local DAT directory."""
        default_root = Path(__file__).resolve().parents[3] / "data" / "sources" / "redump" / "dats"
        self.catalog = PublicDatCatalogProvider(root=root or default_root, timeout=timeout)

    @classmethod
    def direct_url_for_name(cls, name: str) -> str | None:
        """Build Redump's direct DAT endpoint for a catalog filename."""
        code = cls.SYSTEM_CODES.get(name)
        if code is None:
            return None
        return f"{cls.REDUMP_DAT_BASE_URL}/{code}/"

    def fetch_catalog(self) -> tuple[RedumpEntry, ...]:
        """Fetch Redump metadata and convert entries to direct Redump URLs."""
        try:
            entries = self.catalog.fetch_catalog("Redump")
            converted: list[RedumpEntry] = []
            skipped = 0
            for entry in entries:
                try:
                    converted.append(RedumpEntry.from_catalog(entry))
                except RedumpError:
                    skipped += 1
            if skipped:
                import logging

                logging.getLogger(__name__).warning(
                    "[REDUMP][CATALOG] entradas sem endpoint direto=%d", skipped
                )
            return tuple(converted)
        except DatCatalogError as exc:
            raise RedumpError(str(exc)) from exc

    def match(
        self,
        systems: tuple[str, ...],
        entries: tuple[RedumpEntry, ...] | None = None,
    ) -> tuple[RedumpEntry, ...]:
        """Match LaunchBox platforms against the Redump catalog."""
        source = entries if entries is not None else self.fetch_catalog()
        catalog_entries = tuple(entry.as_catalog_entry() for entry in source)
        matches = self.catalog.match(systems, catalog_entries)
        return tuple(RedumpEntry.from_catalog(entry) for entry in matches)

    def status(self, entry: RedumpEntry) -> DatStatus:
        """Return the validated local state of one Redump DAT."""
        return self.catalog.status(entry.as_catalog_entry())

    def destination(self, entry: RedumpEntry) -> Path:
        """Return the stable local path for one Redump DAT."""
        return self.catalog.destination(entry.as_catalog_entry())

    def download(self, entry: RedumpEntry) -> DatStatus:
        """Download the ZIP from Redump, extract its DAT and store it locally."""
        if not entry.url.startswith(f"{self.REDUMP_DAT_BASE_URL}/"):
            raise RedumpError(f"URL de aquisição Redump inválida: {entry.url}")
        try:
            return self.catalog.download(entry.as_catalog_entry())
        except DatCatalogError as exc:
            raise RedumpError(str(exc)) from exc

    def update(self, entries: tuple[RedumpEntry, ...]) -> tuple[DatStatus, ...]:
        """Download only missing or outdated Redump DATs."""
        results: list[DatStatus] = []
        for entry in entries:
            if self.status(entry).state != "current":
                results.append(self.download(entry))
        return tuple(results)
