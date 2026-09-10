"""Download/cache/extraction primitives for external Arcade Studio resources."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import urllib.request
import zipfile
from enum import StrEnum
from pathlib import Path, PurePosixPath

from ...models.external_resource import ExternalResource, ExtractionMode


class DestinationAction(StrEnum):
    """Decision for an existing destination file."""

    CREATE = "create"
    REUSE = "reuse"
    REPLACE = "replace"
    BLOCK = "block"


class DownloadManager:
    """Acquires resources without blindly writing to the MAME installation.

    Acquisition lives in cache/source. Publication is an explicit second step
    so the destination can be inspected before a file is replaced.
    """

    def __init__(self, cache_dir: Path, source_dir: Path | None = None) -> None:
        self.cache_dir = Path(cache_dir)
        self.source_dir = Path(source_dir) if source_dir is not None else None

    def archive_path(self, resource: ExternalResource) -> Path:
        """Return the canonical cache path for an acquired archive/file."""
        suffix = ".zip" if resource.extraction is ExtractionMode.ARCHIVE else ""
        return self.cache_dir / resource.provider / resource.platform / resource.name / resource.version / (
            resource.name + suffix
        )

    def download(self, resource: ExternalResource) -> Path:
        """Download atomically and reuse an already validated cache entry."""
        target = self.archive_path(resource)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and self._matches(target, resource):
            return target

        with tempfile.NamedTemporaryFile(prefix=".download-", dir=target.parent, delete=False) as tmp:
            temporary = Path(tmp.name)
        try:
            with urllib.request.urlopen(resource.url, timeout=60) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
            self._validate(temporary, resource)
            os.replace(temporary, target)
            return target
        finally:
            temporary.unlink(missing_ok=True)

    def extract(self, resource: ExternalResource, archive: Path) -> Path:
        """Extract to cache with path-traversal protection."""
        if resource.extraction is not ExtractionMode.ARCHIVE:
            return archive
        destination = archive.parent / "extracted"
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as package:
            root = destination.resolve()
            for member in package.infolist():
                member_path = (destination / member.filename).resolve()
                if os.path.commonpath((str(root), str(member_path))) != str(root):
                    raise ValueError(f"arquivo ZIP fora do destino: {member.filename}")
            package.extractall(destination)
        return destination

    def acquire(self, resource: ExternalResource) -> Path:
        """Download and extract, keeping the result outside the MAME destination."""
        archive = self.download(resource)
        return self.extract(resource, archive)

    def install_members(
        self,
        resource: ExternalResource,
        extracted: Path,
        destination_root: Path,
        *,
        replace_existing: bool = False,
    ) -> tuple[tuple[str, Path, DestinationAction], ...]:
        """Install mapped archive members into exact MAME subdirectories.

        All destination conflicts are preflighted before the first write. This
        prevents a multi-file package from being partially published when a
        later member is blocked.
        """
        members = resource.metadata.get("members")
        if not isinstance(members, dict):
            raise ValueError(f"recurso sem mapa de membros: {resource.name}")

        plan: list[tuple[Path, Path, str, DestinationAction]] = []
        extraction_root = extracted.resolve()
        for archive_member, logical_destination in members.items():
            source = (extracted / PurePosixPath(str(archive_member))).resolve()
            if os.path.commonpath((str(extraction_root), str(source))) != str(extraction_root):
                raise ValueError(f"membro inseguro: {archive_member}")
            if not source.is_file():
                raise FileNotFoundError(f"membro esperado nao encontrado: {archive_member}")

            relative_dir = self._destination_dir(logical_destination)
            destination = Path(destination_root) / relative_dir / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                action = DestinationAction.CREATE
            elif self.sha256(destination) == self.sha256(source):
                action = DestinationAction.REUSE
            elif replace_existing:
                action = DestinationAction.REPLACE
            else:
                action = DestinationAction.BLOCK
            if action is DestinationAction.BLOCK:
                raise FileExistsError(
                    f"conflito no destino: {destination}; valide ou permita substituicao explicitamente"
                )
            plan.append((source, destination, str(archive_member), action))

        for source, destination, _archive_member, action in plan:
            if action is DestinationAction.REUSE:
                continue
            temporary = destination.with_name(f".{destination.name}.serm-tmp")
            shutil.copy2(source, temporary)
            os.replace(temporary, destination)

        return tuple((member, destination, action) for _source, destination, member, action in plan)

    @staticmethod
    def _destination_dir(logical_destination: object) -> Path:
        if logical_destination == "mame_dats":
            return Path("dats")
        if logical_destination == "mame_folders":
            return Path("folders")
        if logical_destination == "mame_samples":
            return Path("samples")
        if logical_destination == "serm_metadata":
            return Path("serm_metadata")
        raise ValueError(f"destino externo desconhecido: {logical_destination}")

    @staticmethod
    def sha256(path: Path) -> str:
        """Calculate SHA-256 in streaming mode."""
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _matches(self, path: Path, resource: ExternalResource) -> bool:
        if resource.expected_size is not None and path.stat().st_size != resource.expected_size:
            return False
        if resource.content_sha256 is not None:
            return self.sha256(path).casefold() == resource.content_sha256.casefold()
        return True

    def _validate(self, path: Path, resource: ExternalResource) -> None:
        if resource.expected_size is not None and path.stat().st_size != resource.expected_size:
            raise ValueError(f"tamanho inesperado para {resource.name}")
        if resource.content_sha256 is not None and self.sha256(path).casefold() != resource.content_sha256.casefold():
            raise ValueError(f"SHA-256 inesperado para {resource.name}")


__all__ = ["DestinationAction", "DownloadManager"]
