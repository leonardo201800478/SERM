"""Modelos de recursos externos adquiridos pelo SERM.

Um recurso externo representa um pacote publicado por um provider, e nao um
arquivo arbitrario copiado para o destino. O modelo separa identidade,
conteudo, politica de extracao e destino para que download, scan e
reconstrucao possam permanecer desacoplados.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath


class ExternalResourceType(StrEnum):
    """Tipos funcionais de recursos externos conhecidos pelo Arcade Studio."""

    METADATA = "metadata"
    SAMPLE = "sample"
    ROM = "rom"
    CHD = "chd"
    BIOS = "bios"
    DEVICE = "device"
    SOFTWARE_LIST = "software_list"
    SNAPSHOT = "snapshot"
    ARTWORK = "artwork"
    TOOL = "tool"
    UNKNOWN = "unknown"


class ResourceStorage(StrEnum):
    """Destino lógico do conteúdo depois da aquisição."""

    SERM_METADATA = "serm_metadata"
    MAME_SOURCE = "mame_source"
    MAME_DESTINATION = "mame_destination"
    CACHE_ONLY = "cache_only"


class ExtractionMode(StrEnum):
    """Como um pacote adquirido deve ser tratado."""

    ARCHIVE = "archive"
    FILE = "file"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ExternalResource:
    """Contrato persistente para um recurso externo.

    ``resource_id`` e estavel entre atualizacoes. A versao do provider faz
    parte da identidade do recurso, enquanto ``content_sha256`` permite
    detectar que duas versoes diferentes carregam o mesmo conteudo.
    """

    resource_id: str
    provider: str
    platform: str
    name: str
    version: str
    resource_type: ExternalResourceType
    url: str
    storage: ResourceStorage
    extraction: ExtractionMode = ExtractionMode.ARCHIVE
    archive_member: str | None = None
    content_sha256: str | None = None
    expected_size: int | None = None
    required: bool = False
    notes: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def normalized_id(self) -> str:
        """Retorna uma chave estavel para cache e deduplicacao."""
        return ":".join(
            part.strip().casefold()
            for part in (self.provider, self.platform, self.name, self.version)
        )

    def safe_member(self) -> PurePosixPath | None:
        """Normaliza um membro de arquivo e rejeita path traversal."""
        if not self.archive_member:
            return None
        path = PurePosixPath(self.archive_member)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"archive member inseguro: {self.archive_member}")
        return path


__all__ = [
    "ExternalResource",
    "ExternalResourceType",
    "ResourceStorage",
    "ExtractionMode",
]
