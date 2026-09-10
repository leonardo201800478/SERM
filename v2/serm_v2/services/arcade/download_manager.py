"""Primitivas de download, cache, extracao e publicacao de recursos externos."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from enum import StrEnum
from pathlib import Path, PurePosixPath

from ...models.external_resource import ExternalResource, ExtractionMode
from .latest_resource_resolver import LatestResourceResolver


class DestinationAction(StrEnum):
    """Decisao tomada para um arquivo no destino."""

    CREATE = "create"
    REUSE = "reuse"
    REPLACE = "replace"
    BLOCK = "block"


class DownloadManager:
    """Adquire recursos fora da instalacao e publica somente em etapa explicita."""

    def __init__(self, cache_dir: Path, source_dir: Path | None = None) -> None:
        self.cache_dir = Path(cache_dir)
        self.source_dir = Path(source_dir) if source_dir is not None else None
        self._latest_resolver = LatestResourceResolver()

    def archive_path(self, resource: ExternalResource) -> Path:
        """Retorna o caminho canonico do pacote no cache."""
        suffix = ".zip" if resource.extraction is ExtractionMode.ARCHIVE else ""
        return self.cache_dir / resource.provider / resource.platform / resource.name / resource.version / (
            resource.name + suffix
        )

    def download(self, resource: ExternalResource) -> Path:
        """Baixa atomicamente e reutiliza um pacote ja validado.

        Recursos externos podem declarar URLs alternativas em
        ``metadata[\"fallback_urls\"]``. A URL principal e sempre tentada
        primeiro; os fallbacks so entram em acao quando a transferencia falha.
        A validacao do arquivo continua obrigatoria antes de publicar o cache.
        A descoberta de versao acontece antes de definir o caminho do cache,
        portanto uma versao nova nunca sobrescreve silenciosamente a anterior.
        """
        resource = self._latest_resolver.resolve(resource)
        target = self.archive_path(resource)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and self._matches(target, resource):
            return target

        urls = self._download_urls(resource)
        last_error: Exception | None = None
        temporary: Path | None = None
        try:
            for url in urls:
                with tempfile.NamedTemporaryFile(prefix=".download-", dir=target.parent, delete=False) as tmp:
                    temporary = Path(tmp.name)
                try:
                    request = urllib.request.Request(
                        url,
                        headers=self._request_headers(resource, url),
                    )
                    with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
                        shutil.copyfileobj(response, output, length=1024 * 1024)
                    self._validate(temporary, resource)
                    os.replace(temporary, target)
                    temporary = None
                    return target
                except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                    last_error = exc
                finally:
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
                        temporary = None

            if last_error is not None:
                raise last_error
            raise RuntimeError(f"nenhuma URL disponivel para {resource.name}")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _download_urls(resource: ExternalResource) -> tuple[str, ...]:
        """Retorna URL principal seguida das alternativas declaradas."""
        fallback_urls = resource.metadata.get("fallback_urls", ())
        if isinstance(fallback_urls, str):
            fallback_urls = (fallback_urls,)
        if not isinstance(fallback_urls, (tuple, list)):
            raise ValueError(f"fallback_urls invalido para {resource.name}")

        urls: list[str] = [resource.url]
        for url in fallback_urls:
            if not isinstance(url, str) or not url:
                raise ValueError(f"URL de fallback invalida para {resource.name}")
            if url not in urls:
                urls.append(url)
        return tuple(urls)

    @staticmethod
    def _request_headers(resource: ExternalResource, url: str) -> dict[str, str]:
        """Monta cabecalhos conservadores para servidores que exigem contexto HTTP."""
        headers = {
            "User-Agent": "SERM/2.x (+https://github.com/leonardo201800478/SERM)",
            "Accept": "*/*",
        }
        support_root = resource.metadata.get("support_root")
        original_source = resource.metadata.get("original_source")
        if isinstance(support_root, str) and support_root:
            headers["Referer"] = support_root
        elif isinstance(original_source, str) and original_source:
            headers["Referer"] = original_source
        return headers

    def extract(self, resource: ExternalResource, archive: Path) -> Path:
        """Extrai ZIP com protecao contra path traversal."""
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
        """Baixa e extrai mantendo o resultado fora da instalacao MAME."""
        resolved = self._latest_resolver.resolve(resource)
        return self.extract(resolved, self.download(resolved))

    def install_members(
        self,
        resource: ExternalResource,
        extracted: Path,
        destination_root: Path,
        *,
        replace_existing: bool = False,
    ) -> tuple[tuple[str, Path, DestinationAction], ...]:
        """Publica membros mapeados em dats/folders/samples/metadata.

        Alguns pacotes externos usam uma pasta-raiz ou diferem apenas em
        capitalizacao nos nomes internos do ZIP. O mapa do recurso continua
        canonico, mas a resolucao aceita esses dois formatos sem relaxar
        a validacao de seguranca nem aceitar nomes ambiguos.
        """
        members = resource.metadata.get("members")
        if not isinstance(members, dict):
            raise ValueError(f"recurso sem mapa de membros: {resource.name}")

        plan: list[tuple[Path, Path, str, DestinationAction]] = []
        extraction_root = extracted.resolve()
        files = tuple(path for path in extraction_root.rglob("*") if path.is_file())
        for archive_member, logical_destination in members.items():
            source = self._resolve_member(extraction_root, str(archive_member), files)
            relative_dir = self._destination_dir(logical_destination)
            destination = Path(destination_root) / relative_dir / source.name
            action = self._plan_action(source, destination, replace_existing)
            if action is DestinationAction.BLOCK:
                raise FileExistsError(f"conflito no destino: {destination}")
            plan.append((source, destination, str(archive_member), action))

        return self._publish_plan(plan)

    @staticmethod
    def _resolve_member(
        extraction_root: Path,
        archive_member: str,
        files: tuple[Path, ...],
    ) -> Path:
        """Resolve um membro esperado, tolerando raiz/capitalizacao do ZIP."""
        relative_member = PurePosixPath(archive_member)
        if relative_member.is_absolute() or ".." in relative_member.parts:
            raise ValueError(f"membro inseguro: {archive_member}")

        exact = (extraction_root / relative_member).resolve()
        if os.path.commonpath((str(extraction_root), str(exact))) != str(extraction_root):
            raise ValueError(f"membro inseguro: {archive_member}")
        if exact.is_file():
            return exact

        expected_path = PurePosixPath(str(relative_member)).as_posix().casefold()
        path_matches = [
            path for path in files
            if path.relative_to(extraction_root).as_posix().casefold() == expected_path
        ]
        if len(path_matches) == 1:
            return path_matches[0]
        if len(path_matches) > 1:
            raise FileExistsError(f"membro ambiguo no ZIP: {archive_member}")

        expected_name = relative_member.name.casefold()
        name_matches = [path for path in files if path.name.casefold() == expected_name]
        if len(name_matches) == 1:
            return name_matches[0]
        if len(name_matches) > 1:
            raise FileExistsError(f"membro ambiguo no ZIP: {archive_member}")
        raise FileNotFoundError(f"membro esperado nao encontrado: {archive_member}")

    def install_tree(
        self,
        extracted: Path,
        destination: Path,
        *,
        replace_existing: bool = False,
        flatten: bool = False,
    ) -> tuple[tuple[str, Path, DestinationAction], ...]:
        """Publica todos os arquivos extraidos, util para o MAME Samples FullPack.

        Quando ``flatten`` e verdadeiro, somente o nome do arquivo e mantido
        no destino. Isso e apropriado para os ZIPs de samples, que pertencem
        diretamente a MAME/samples/.
        """
        root = Path(extracted).resolve()
        destination = Path(destination)
        plan: list[tuple[Path, Path, str, DestinationAction]] = []
        for source in sorted(path for path in root.rglob("*") if path.is_file()):
            relative = source.relative_to(root)
            target = destination / (Path(relative).name if flatten else relative)
            action = self._plan_action(source, target, replace_existing)
            if action is DestinationAction.BLOCK:
                raise FileExistsError(f"conflito no destino: {target}")
            plan.append((source, target, relative.as_posix(), action))
        return self._publish_plan(plan)

    @staticmethod
    def _plan_action(source: Path, destination: Path, replace_existing: bool) -> DestinationAction:
        if not destination.exists():
            return DestinationAction.CREATE
        if DownloadManager.sha256(destination) == DownloadManager.sha256(source):
            return DestinationAction.REUSE
        return DestinationAction.REPLACE if replace_existing else DestinationAction.BLOCK

    @staticmethod
    def _publish_plan(
        plan: list[tuple[Path, Path, str, DestinationAction]],
    ) -> tuple[tuple[str, Path, DestinationAction], ...]:
        for _source, destination, _member, _action in plan:
            destination.parent.mkdir(parents=True, exist_ok=True)
        for source, destination, _member, action in plan:
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


__all__ = ["DestinationAction", "DownloadManager"]
