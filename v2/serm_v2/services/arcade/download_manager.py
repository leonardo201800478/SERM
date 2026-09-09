"""Download/cache/extraction primitives for external Arcade Studio resources."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from ...models.external_resource import ExternalResource, ExtractionMode


class DownloadManager:
    """Adquire recursos em cache sem escrever diretamente no destino MAME.

    O manager valida tamanho/hash quando disponiveis, extrai ZIPs com protecao
    contra path traversal e devolve somente caminhos dentro do cache/source.
    A publicacao no destino continua sendo responsabilidade da materializacao.
    """

    def __init__(self, cache_dir: Path, source_dir: Path | None = None) -> None:
        self.cache_dir = Path(cache_dir)
        self.source_dir = Path(source_dir) if source_dir is not None else None

    def archive_path(self, resource: ExternalResource) -> Path:
        """Retorna o caminho canonico do arquivo adquirido no cache."""
        suffix = ".zip" if resource.extraction is ExtractionMode.ARCHIVE else ""
        return self.cache_dir / resource.provider / resource.platform / resource.name / resource.version / (
            resource.name + suffix
        )

    def download(self, resource: ExternalResource) -> Path:
        """Baixa atomicamente um recurso e retorna seu caminho de cache."""
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
        """Extrai um arquivo para cache de origem com path traversal bloqueado."""
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
        """Executa download e extracao, mantendo tudo fora do destino MAME."""
        archive = self.download(resource)
        return self.extract(resource, archive)

    @staticmethod
    def sha256(path: Path) -> str:
        """Calcula SHA-256 em streaming."""
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


__all__ = ["DownloadManager"]
