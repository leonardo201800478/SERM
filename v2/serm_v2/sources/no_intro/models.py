"""No-Intro-specific source records."""
from __future__ import annotations

from dataclasses import dataclass

from ..contracts.models import SourceArtifact, SourceProvenance


@dataclass(frozen=True, slots=True)
class NoIntroDatInfo:
    """Metadata describing the DAT consumed by the adapter."""

    name: str | None
    version: str | None
    date: str | None


@dataclass(frozen=True, slots=True)
class NoIntroRomRecord(SourceArtifact):
    """ROM record retaining the source filename and hash evidence."""

    serial: str | None = None


@dataclass(frozen=True, slots=True)
class NoIntroSetRecord:
    """No-Intro set with its original source identity preserved."""

    name: str
    description: str | None
    platform: str | None
    region: str | None
    clone_of: str | None
    roms: tuple[NoIntroRomRecord, ...]
    provenance: SourceProvenance
