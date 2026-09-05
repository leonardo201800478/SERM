"""Redump DAT acquisition through the official redump.info download endpoints."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .dat_catalog import DatCatalogEntry, DatCatalogError, DatStatus, PublicDatCatalogProvider

logger = logging.getLogger(__name__)


class RedumpError(DatCatalogError):
    """Raised when a Redump DAT cannot be discovered or downloaded."""


@dataclass(frozen=True, slots=True)
class RedumpEntry:
    """Describe one Redump DAT and its direct redump.info download endpoint."""

    name: str
    url: str
    crc32: int
    size: int
    category: str = "Redump"

    @classmethod
    def from_catalog(cls, entry: DatCatalogEntry) -> RedumpEntry:
        """Convert a catalog entry to the official redump.info DAT endpoint."""
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
    """Discover Redump systems and download DATs from the official new site.

    The public DAT Catalog remains useful for metadata when available, but the
    authoritative list of Redump systems comes from the official Downloads
    page. This allows SERM to expose newly added Redump DATs even before the
    third-party DAT Catalog is updated.
    """

    REDUMP_DOWNLOADS_URL = "https://redump.info/downloads"
    REDUMP_DAT_BASE_URL = "https://redump.info/datfile"

    # Complete system list exposed by redump.info/downloads. The values are
    # the identifiers used by the official /datfile/<SYSTEM> endpoints.
    SYSTEM_CODES: dict[str, str] = {
        "3DO Interactive Multiplayer.dat": "3DO",
        "Acorn Archimedes & Risc PC.dat": "ARCH",
        "American Laser Games 3DO-based Arcade.dat": "3DOARCADE",
        "Apple Macintosh.dat": "MAC",
        "Apple Newton.dat": "NEWTON",
        "Apple Pippin.dat": "PIPPIN",
        "Atari Jaguar CD Interactive Multimedia System.dat": "AJCD",
        "Atari ST series.dat": "ATARIST",
        "Audio CD.dat": "AUDIO-CD",
        "Bandai Playdia Quick Interactive System.dat": "QIS",
        "BD-Video.dat": "BD-VIDEO",
        "Capcom Play System III.dat": "CPS3",
        "Commodore Amiga CD.dat": "ACD",
        "Commodore Amiga CD32.dat": "CD32",
        "Commodore Amiga CDTV.dat": "CDTV",
        "Cybiko.dat": "CYBIKO",
        "Datel PlayStation Cheat Device Updates.dat": "PSXGS",
        "DVD-Video.dat": "DVD-VIDEO",
        "Enhanced CD.dat": "ENHANCED-CD",
        "Fujitsu FM Towns series.dat": "FMT",
        "Funworld Photo Play.dat": "FPP",
        "FuRyu & Omron Purikura.dat": "FPURI",
        "Hasbro iON Educational Gaming System.dat": "ION",
        "Hasbro VideoNow.dat": "HVN",
        "Hasbro VideoNow Color.dat": "HVNC",
        "Hasbro VideoNow Jr..dat": "HVNJR",
        "Hasbro VideoNow XP.dat": "HVNXP",
        "HD DVD-Video.dat": "HDDVD-VIDEO",
        "IBM PC compatible.dat": "PC",
        "Incredible Technologies Eagle.dat": "ITE",
        "Konami e-Amusement.dat": "KEA",
        "Konami FireBeat.dat": "KFB",
        "Konami M2.dat": "KM2",
        "Konami Python 2.dat": "KP2",
        "Konami System 573.dat": "KS573",
        "Konami System GV.dat": "KSGV",
        "Mattel Fisher-Price iXL.dat": "IXL",
        "Mattel HyperScan.dat": "HS",
        "Memorex Visual Information System.dat": "VIS",
        "Merit Industries Megatouch ION.dat": "MION",
        "Microsoft Pocket PC.dat": "PPC",
        "Microsoft Xbox.dat": "XBOX",
        "Microsoft Xbox 360.dat": "XBOX360",
        "Microsoft Xbox One.dat": "XBOXONE",
        "Microsoft Xbox Series X.dat": "XBOXSX",
        "MP3 Audio Disc.dat": "MP3",
        "Namco Purikura.dat": "NPURI",
        "Namco System 22.dat": "NS22",
        "Namco System 246.dat": "NS246",
        "Namco System 256.dat": "NS256",
        "Namco · Sega · Nintendo Triforce.dat": "TRF",
        "Navisoft Naviken.dat": "NAVI",
        "NEC PC Engine CD & TurboGrafx CD.dat": "PCE",
        "NEC PC-88 series.dat": "PC-88",
        "NEC PC-98 series.dat": "PC-98",
        "NEC PC-FX & PC-FXGA.dat": "PC-FX",
        "Neo Geo CD.dat": "NGCD",
        "New Jatre CD-i based Arcade.dat": "NEWJATRE",
        "Nintendo GameCube.dat": "GC",
        "Nintendo Wii.dat": "WII",
        "Nintendo Wii U.dat": "WIIU",
        "Palm OS.dat": "PALM",
        "Panasonic M2.dat": "M2",
        "PC-based Arcade.dat": "PCARCADE",
        "Philips CD-i.dat": "CDI",
        "Photo CD.dat": "PHOTO-CD",
        "Playmaji Polymega.dat": "POLYMEGA",
        "Psion.dat": "PSION",
        "Sega ALLS.dat": "ALLS",
        "Sega Chihiro.dat": "CHIHIRO",
        "Sega Chihiro Satellite Terminal PC.dat": "CHIHIROPC",
        "Sega Dreamcast.dat": "DC",
        "Sega Lindbergh.dat": "LINDBERGH",
        "Sega Lindbergh Satellite Terminal PC.dat": "LINDPC",
        "Sega Mega CD & Sega CD.dat": "MCD",
        "Sega Naomi.dat": "NAOMI",
        "Sega Naomi 2.dat": "NAOMI2",
        "Sega Naomi Satellite Terminal PC.dat": "NAOMIPC",
        "Sega Nu.dat": "NU",
        "Sega Nu 1.1.dat": "NU11",
        "Sega Nu 2.dat": "NU2",
        "Sega Nu SX.dat": "NUSX",
        "Sega Prologue 21 Multimedia Karaoke System.dat": "SP21",
        "Sega RingEdge.dat": "SRE",
        "Sega RingEdge 2.dat": "SRE2",
        "Sega RingWide.dat": "SRW",
        "Sega Saturn.dat": "SS",
        "Seibu CATS E-Touch.dat": "CATS",
        "SGI Indigo series.dat": "INDIGO",
        "Sharp X68000.dat": "X68K",
        "Sharp Zaurus.dat": "ZAURUS",
        "SNK Neo Geo CD.dat": "NGCD",
        "Sony Electronic Book.dat": "SEB",
        "Sony PlayStation.dat": "PSX",
        "Sony PlayStation 2.dat": "PS2",
        "Sony PlayStation 3.dat": "PS3",
        "Sony PlayStation 4.dat": "PS4",
        "Sony PlayStation 5.dat": "PS5",
        "Sony PlayStation Portable.dat": "PSP",
        "Sun Microsystems Ultra.dat": "ULTRA",
        "Symbian.dat": "SYMBIAN",
        "TAB-Austria Quizard.dat": "QUIZARD",
        "Texas Instruments TI series.dat": "TI",
        "Tomy Kiss-Site.dat": "KSITE",
        "Video CD.dat": "VCD",
        "VM Labs Nuon.dat": "NUON",
        "VTech V.Flash & V.Smile Pro.dat": "VFLASH",
        "ZAPiT Games Game Wave Family Entertainment System.dat": "GAMEWAVE",
    }

    # LaunchBox names are not identical to Redump's official names. Keep
    # explicit aliases here for systems where vendor prefixes or naming differ.
    # Keys and values are normalized through PublicDatCatalogProvider._normalize.
    LAUNCHBOX_ALIASES: dict[str, str] = {
        "sony psp": "sony playstation portable",
        "psp": "sony playstation portable",
        "playstation portable": "sony playstation portable",
        "ps portable": "sony playstation portable",
        "commodore amiga cdtv": "commodore amiga cdtv",
        "amiga cdtv": "commodore amiga cdtv",
        "cdtv": "commodore amiga cdtv",
        "nec pc engine cd": "nec pc engine cd and turbografx cd",
        "pc engine cd": "nec pc engine cd and turbografx cd",
        "turbo grafx cd": "nec pc engine cd and turbografx cd",
        "turbografx cd": "nec pc engine cd and turbografx cd",
        "nec turbografx cd": "nec pc engine cd and turbografx cd",
        "sega mega cd": "sega mega cd and sega cd",
        "sega cd": "sega mega cd and sega cd",
        "mega cd": "sega mega cd and sega cd",
        "pc fx": "nec pc fx and pc fxga",
        "nec pc fx": "nec pc fx and pc fxga",
        "pc fxga": "nec pc fx and pc fxga",
        "atari jaguar cd": "atari jaguar cd interactive multimedia system",
        "jaguar cd": "atari jaguar cd interactive multimedia system",
    }

    def __init__(self, *, root: Path | None = None, timeout: int = 60) -> None:
        """Initialize the provider and its local DAT directory."""
        default_root = Path(__file__).resolve().parents[3] / "data" / "sources" / "redump" / "dats"
        self.catalog = PublicDatCatalogProvider(root=root or default_root, timeout=timeout)

    @classmethod
    def direct_url_for_name(cls, name: str) -> str | None:
        """Build the official redump.info DAT endpoint for a catalog filename."""
        code = cls.SYSTEM_CODES.get(name)
        if code is None:
            return None
        return f"{cls.REDUMP_DAT_BASE_URL}/{code}"

    @classmethod
    def _direct_entries(cls) -> tuple[RedumpEntry, ...]:
        """Build entries for every DAT published on the official Downloads page."""
        return tuple(
            RedumpEntry(name, f"{cls.REDUMP_DAT_BASE_URL}/{code}", 0, 0, "Redump")
            for name, code in cls.SYSTEM_CODES.items()
        )

    def fetch_catalog(self) -> tuple[RedumpEntry, ...]:
        """Merge third-party metadata with the complete official Redump list."""
        try:
            catalog_entries = self.catalog.fetch_catalog("Redump")
        except DatCatalogError as exc:
            logger.warning("[REDUMP][CATALOG] catálogo auxiliar indisponível: %s", exc)
            catalog_entries = ()

        by_name = {entry.name: entry for entry in catalog_entries}
        merged: list[RedumpEntry] = []
        for direct_entry in self._direct_entries():
            metadata = by_name.get(direct_entry.name)
            if metadata is None:
                merged.append(direct_entry)
                continue
            merged.append(
                RedumpEntry(
                    metadata.name,
                    direct_entry.url,
                    metadata.crc32,
                    metadata.size,
                    "Redump",
                )
            )

        logger.info(
            "[REDUMP][CATALOG] sistemas oficiais=%d | com metadados auxiliares=%d",
            len(merged),
            sum(1 for entry in merged if entry.crc32 or entry.size),
        )
        return tuple(merged)

    def match(
        self,
        systems: tuple[str, ...],
        entries: tuple[RedumpEntry, ...] | None = None,
    ) -> tuple[RedumpEntry, ...]:
        """Match LaunchBox platforms against the complete Redump catalog."""
        source = entries if entries is not None else self.fetch_catalog()

        # First use the generic catalog matcher for established aliases.
        catalog_entries = tuple(entry.as_catalog_entry() for entry in source)
        generic_matches = self.catalog.match(systems, catalog_entries)
        matched_names = {entry.name for entry in generic_matches}

        # Then apply explicit LaunchBox -> Redump mappings for names that differ
        # structurally, such as "Sony PSP" versus "Sony PlayStation Portable".
        normalized_targets = {
            self.catalog._normalize(target) for target in self.LAUNCHBOX_ALIASES.values()
        }
        requested_targets: set[str] = set()
        for system in systems:
            normalized = self.catalog._normalize(system)
            target = self.LAUNCHBOX_ALIASES.get(normalized)
            if target is not None:
                requested_targets.add(self.catalog._normalize(target))

        for entry in source:
            normalized_name = self.catalog._normalize(Path(entry.name).stem)
            if normalized_name in requested_targets and normalized_name in normalized_targets:
                matched_names.add(entry.name)

        result = tuple(entry for entry in source if entry.name in matched_names)
        logger.info(
            "[REDUMP][MATCH] LaunchBox=%d | DATs=%d | matches=%d",
            len(systems),
            len(source),
            len(result),
        )
        return result

    def status(self, entry: RedumpEntry) -> DatStatus:
        """Return the validated local state of one Redump DAT."""
        return self.catalog.status(entry.as_catalog_entry())

    def destination(self, entry: RedumpEntry) -> Path:
        """Return the stable local path for one Redump DAT."""
        return self.catalog.destination(entry.as_catalog_entry())

    def download(self, entry: RedumpEntry) -> DatStatus:
        """Download the DAT from redump.info and store it locally."""
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
