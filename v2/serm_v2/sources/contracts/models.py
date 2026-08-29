"""Generic immutable records exchanged by source adapters."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    """Identify the external source and the exact input consumed."""

    source: str
    source_version: str | None = None
    source_file: str | None = None
    source_identifier: str | None = None


@dataclass(frozen=True, slots=True)
class SourceHash:
    """Hash evidence supplied by an external source."""

    algorithm: str
    value: str


@dataclass(frozen=True, slots=True)
class SourceArtifact:
    """A file or ROM described by an external preservation source."""

    filename: str
    size: int | None = None
    hashes: tuple[SourceHash, ...] = ()
    status: str | None = None
    region: str | None = None
    language: str | None = None


@dataclass(frozen=True, slots=True)
class SourceRelease:
    """A source-defined release/set and its contained artifacts."""

    name: str
    description: str | None = None
    platform: str | None = None
    artifacts: tuple[SourceArtifact, ...] = ()
    provenance: SourceProvenance | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
