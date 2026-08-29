"""Redump DAT acquisition through the public DAT Catalog mirror."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .dat_catalog import DatCatalogEntry, DatCatalogError, DatStatus, PublicDatCatalogProvider


class RedumpError(DatCatalogError):
    """Raised when the Redump public catalog cannot be consumed."""


@dataclass(frozen=True, slots=True)
class RedumpEntry:
    """Describe one Redump DAT exposed by the public catalog."""

    name: str
    url: str
    crc32: int
    size: int
    category: str = "Redump"

    @classmethod
    def from_catalog(cls, entry: DatCatalogEntry) -> "RedumpEntry":
        """Convert a generic public-catalog entry into a Redump entry."""
        return cls(entry.name, entry.url, entry.crc32, entry.size, entry.category)

    def as_catalog_entry(self) -> DatCatalogEntry:
        """Convert this Redump entry back to the generic acquisition model."""
        return DatCatalogEntry(self.name, self.url, self.crc32, self.size, self.category)


class RedumpProvider:
    """Acquire current Redump DATs from a public machine-readable mirror.

    The Public DAT Catalog publishes direct raw DAT links plus validation
    metadata. SERM therefore does not need DAT-o-MATIC, Selenium, CAPTCHA,
    account sessions or Redump website download pages.
    """

    CATALOG_CATEGORY = "Redump"

    def __init__(self, *, root: Path | None = None, timeout: int = 60) -> None:
        """Initialize the Redump provider."""
        default_root = Path(__file__).resolve().parents[3] / "data" / "sources" / "redump" / "dats"
        self.catalog = PublicDatCatalogProvider(root=root or default_root, timeout=timeout)

    def fetch_catalog(self) -> tuple[RedumpEntry, ...]:
        """Fetch every Redump DAT currently exposed by the public catalog."""
        try:
            entries = self.catalog.fetch_catalog(self.CATALOG_CATEGORY)
        except DatCatalogError as exc:
            raise RedumpError(str(exc)) from exc
        return tuple(RedumpEntry.from_catalog(entry) for entry in entries)

    def match(
        self,
        systems: tuple[str, ...],
        entries: tuple[RedumpEntry, ...] | None = None,
    ) -> tuple[RedumpEntry, ...]:
        """Match LaunchBox platforms against the complete Redump catalog."""
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
        """Download and validate one Redump DAT using catalog CRC and size."""
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
