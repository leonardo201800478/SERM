"""Gerenciamento local de shaders de terceiros para o RetroArch.

O projeto mantém apenas o catálogo. Os arquivos dos projetos externos são
baixados diretamente de seus repositórios upstream e ficam sob controle do
manifesto local do Arcade Manager.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config.app_config import AppConfig
from app.core.services.shader_download_service import (
    ShaderDownloadResult,
    ShaderDownloadService,
)


@dataclass(frozen=True, slots=True)
class InstalledShader:
    """Estado persistido de uma biblioteca instalada localmente."""
    shader_id: str
    repository: str
    ref: str
    installed_at: str
    files: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ShaderStatus:
    """Estado atual de uma biblioteca de shader."""
    shader_id: str
    installed: bool
    file_count: int = 0
    repository: str = ""
    ref: str = ""
    fingerprint: str = ""


class ShaderManagerService:
    """Gerencia instalação, atualização, auditoria e remoção de shaders."""

    MANIFEST_VERSION = 1

    def __init__(self, config: AppConfig, catalog_path: Path) -> None:
        """Inicializa o gerenciador com catálogo e configuração do RetroArch."""
        self.config = config
        self.catalog_path = catalog_path
        self.downloader = ShaderDownloadService(config, catalog_path)
        self.manifest_path = self._manifest_path()

    def _retroarch_root(self) -> Path:
        """Obtém a raiz da instalação do RetroArch."""
        if self.config.retroarch_dir:
            return Path(self.config.retroarch_dir)
        native = self.config.retroarch_native_paths.get("video_shader_directory")
        if native:
            return Path(native).parent
        raise RuntimeError("Configure o diretório do RetroArch antes de gerenciar shaders.")

    def _manifest_path(self) -> Path:
        """Retorna o manifesto local, separado dos arquivos de shader."""
        return self._retroarch_root() / "config" / "arcade_manager" / "shaders_manifest.json"

    def _load_manifest(self) -> dict:
        """Carrega o manifesto local ou retorna uma estrutura vazia."""
        try:
            raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {"version": self.MANIFEST_VERSION, "shaders": {}}
        if not isinstance(raw, dict) or not isinstance(raw.get("shaders", {}), dict):
            return {"version": self.MANIFEST_VERSION, "shaders": {}}
        return raw

    def _save_manifest(self, manifest: dict) -> None:
        """Persiste o manifesto usando escrita temporária e substituição atômica."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.manifest_path.with_suffix(".tmp")
        temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.manifest_path)

    @staticmethod
    def _fingerprint(paths: list[Path]) -> str:
        """Calcula uma impressão estável baseada nos arquivos instalados."""
        digest = hashlib.sha256()
        for path in sorted(paths, key=lambda item: item.as_posix().casefold()):
            digest.update(path.as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
        return digest.hexdigest()

    def _relative_to_shader_root(self, path: Path) -> str:
        """Converte caminho absoluto para caminho relativo à raiz de shaders."""
        root = self.downloader._shader_root().resolve()
        return path.resolve().relative_to(root).as_posix()

    def _tracked_paths(self, shader_id: str) -> list[Path]:
        """Retorna somente arquivos registrados no manifesto."""
        entry = self._load_manifest().get("shaders", {}).get(shader_id, {})
        if not isinstance(entry, dict):
            return []
        root = self.downloader._shader_root().resolve()
        paths: list[Path] = []
        for value in entry.get("files", []):
            try:
                path = (root / str(value)).resolve()
                if root in path.parents and path.is_file():
                    paths.append(path)
            except (OSError, ValueError):
                continue
        return paths

    def _catalog_entry(self, shader_id: str) -> dict:
        """Obtém a entrada do catálogo sem expor sua estrutura ao chamador."""
        try:
            raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Não foi possível ler o catálogo de shaders: {self.catalog_path}") from exc
        for item in raw.get("shaders", []) if isinstance(raw, dict) else []:
            if isinstance(item, dict) and str(item.get("id", "")).strip() == shader_id:
                return item
        raise KeyError(f"Shader não encontrado no catálogo: {shader_id}")

    def status(self, shader_id: str) -> ShaderStatus:
        """Audita a presença dos arquivos registrados de um shader."""
        manifest = self._load_manifest()
        entry = manifest.get("shaders", {}).get(shader_id)
        if not isinstance(entry, dict):
            return ShaderStatus(shader_id, False)
        paths = self._tracked_paths(shader_id)
        expected = len(entry.get("files", []))
        installed = bool(paths) and len(paths) == expected
        fingerprint = self._fingerprint(paths) if installed else ""
        return ShaderStatus(
            shader_id=shader_id,
            installed=installed,
            file_count=len(paths),
            repository=str(entry.get("repository", "")),
            ref=str(entry.get("ref", "")),
            fingerprint=fingerprint,
        )

    def list_installed(self) -> list[ShaderStatus]:
        """Lista os shaders gerenciados e audita seus arquivos."""
        shaders = self._load_manifest().get("shaders", {})
        if not isinstance(shaders, dict):
            return []
        return [self.status(shader_id) for shader_id in sorted(shaders)]

    def install(
        self,
        shader_id: str,
        *,
        force: bool = False,
        progress: Callable[[int, int], None] | None = None,
    ) -> ShaderStatus:
        """Instala um shader do catálogo e registra exatamente os arquivos obtidos.

        `force=True` é usado para atualização. Arquivos previamente gerenciados
        pelo mesmo shader podem ser substituídos; arquivos externos não entram
        no manifesto nem são removidos durante uma desinstalação.
        """
        entry = self._catalog_entry(shader_id)
        if "download" not in entry:
            raise ValueError(f"Shader '{shader_id}' não possui download upstream configurado.")
        current = self.status(shader_id)
        if current.installed and not force:
            return current

        old_paths = set(self._tracked_paths(shader_id))
        result: ShaderDownloadResult = self.downloader.install_from_catalog(shader_id, progress=progress)
        installed_paths = [path.resolve() for path in result.files_installed]

        # Remove do manifesto arquivos antigos que não pertencem mais ao pacote.
        for path in old_paths - set(installed_paths):
            if path.is_file():
                path.unlink()

        manifest = self._load_manifest()
        shaders = manifest.setdefault("shaders", {})
        shaders[shader_id] = {
            "repository": result.repository,
            "ref": str(entry.get("download", {}).get("ref", "main")),
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "files": sorted(self._relative_to_shader_root(path) for path in installed_paths),
            "fingerprint": self._fingerprint(installed_paths),
        }
        manifest["version"] = self.MANIFEST_VERSION
        self._save_manifest(manifest)
        return self.status(shader_id)

    def update(
        self,
        shader_id: str,
        *,
        progress: Callable[[int, int], None] | None = None,
    ) -> ShaderStatus:
        """Baixa novamente a referência upstream para atualizar a instalação."""
        return self.install(shader_id, force=True, progress=progress)

    def remove(self, shader_id: str) -> ShaderStatus:
        """Remove somente os arquivos previamente registrados pelo gerenciador."""
        manifest = self._load_manifest()
        shaders = manifest.get("shaders", {})
        entry = shaders.get(shader_id) if isinstance(shaders, dict) else None
        if not isinstance(entry, dict):
            return ShaderStatus(shader_id, False)

        root = self.downloader._shader_root().resolve()
        for value in entry.get("files", []):
            path = (root / str(value)).resolve()
            if root in path.parents and path.is_file():
                path.unlink()

        shaders.pop(shader_id, None)
        self._save_manifest(manifest)
        return ShaderStatus(shader_id, False)

    def audit(self, shader_id: str) -> dict[str, object]:
        """Retorna diagnóstico sem alterar arquivos."""
        status = self.status(shader_id)
        entry = self._catalog_entry(shader_id)
        missing = []
        manifest = self._load_manifest().get("shaders", {}).get(shader_id, {})
        root = self.downloader._shader_root().resolve()
        for value in manifest.get("files", []) if isinstance(manifest, dict) else []:
            path = (root / str(value)).resolve()
            if root in path.parents and not path.is_file():
                missing.append(str(value))
        return {
            "shader_id": shader_id,
            "name": entry.get("name", shader_id),
            "installed": status.installed,
            "files": status.file_count,
            "missing": missing,
            "repository": status.repository,
            "ref": status.ref,
            "fingerprint": status.fingerprint,
        }


__all__ = ["InstalledShader", "ShaderManagerService", "ShaderStatus"]
