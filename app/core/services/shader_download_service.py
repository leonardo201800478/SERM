"""Download e instalação de bibliotecas de shaders de terceiros.

Os shaders de terceiros NÃO são versionados neste projeto. O catálogo contém
somente metadados e instruções de origem; os arquivos são baixados diretamente
do repositório GitHub do projeto de origem para a instalação local do RetroArch.
"""
from __future__ import annotations

import fnmatch
import io
import json
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from app.config.app_config import AppConfig


@dataclass(frozen=True, slots=True)
class ShaderDownloadSpec:
    """Define como obter um pacote de shaders diretamente de um repositório."""
    shader_id: str
    repository: str
    ref: str = "main"
    source_subdir: str = ""
    destination_subdir: str = ""
    include: tuple[str, ...] = ("*.slang", "*.slangp", "*.glsl")


@dataclass(frozen=True, slots=True)
class ShaderDownloadResult:
    """Resultado de uma instalação de shader."""
    shader_id: str
    repository: str
    files_installed: tuple[Path, ...]
    destination: Path


class ShaderDownloadService:
    """Baixa shaders de terceiros sem armazená-los no repositório do projeto."""

    def __init__(self, config: AppConfig, catalog_path: Path) -> None:
        """Inicializa o instalador usando a configuração do RetroArch."""
        self.config = config
        self.catalog_path = catalog_path

    def _shader_root(self) -> Path:
        """Obtém a pasta global de shaders configurada no RetroArch."""
        native = self.config.retroarch_native_paths.get("video_shader_directory")
        if native:
            return Path(native)
        configured = self.config.emulator_paths.get("retroarch", {}).get("shaders")
        if configured:
            return Path(configured)
        if self.config.retroarch_dir:
            return Path(self.config.retroarch_dir) / "shaders"
        raise RuntimeError("Configure o diretório de shaders do RetroArch antes de instalar shaders.")

    @staticmethod
    def _validate_repository(repository: str) -> str:
        """Valida e normaliza uma URL de repositório GitHub."""
        value = repository.strip().rstrip("/")
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
            raise ValueError("A origem do shader deve ser um repositório HTTPS do github.com.")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 2 or any(part in {".", ".."} for part in parts):
            raise ValueError(f"Repositório GitHub inválido: {repository}")
        return f"https://github.com/{parts[0]}/{parts[1]}"

    @staticmethod
    def _safe_relative(path: str) -> Path:
        """Converte um caminho do arquivo ZIP e bloqueia path traversal."""
        normalized = str(path).replace("\\", "/").lstrip("/")
        candidate = Path(normalized)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"Caminho inseguro no pacote de shader: {path}")
        return candidate

    def _validate_destination(self, destination_subdir: str) -> Path:
        """Valida o destino antes de qualquer operação de rede."""
        shader_root = self._shader_root().resolve()
        relative = self._safe_relative(destination_subdir)
        destination = (shader_root / relative).resolve()
        if shader_root not in destination.parents and destination != shader_root:
            raise ValueError("Destino do shader está fora da pasta de shaders do RetroArch.")
        return destination

    def _download_archive(self, spec: ShaderDownloadSpec) -> bytes:
        """Baixa o ZIP do branch/tag diretamente do GitHub."""
        repository = self._validate_repository(spec.repository)
        owner, repo = repository.rstrip("/").split("/")[-2:]
        url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{spec.ref}"
        request = urllib.request.Request(url, headers={"User-Agent": "mame-set-builder-shader-installer/1.0", "Accept": "application/zip"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"GitHub retornou HTTP {exc.code} ao baixar {repository}@{spec.ref}.") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Não foi possível acessar GitHub para baixar {repository}: {exc.reason}") from exc

    @staticmethod
    def _matches(path: str, patterns: tuple[str, ...]) -> bool:
        """Verifica se um arquivo atende aos padrões do pacote."""
        return any(fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(Path(path).name, pattern) for pattern in patterns)

    def is_installed(self, shader_id: str) -> bool:
        """Indica se o preset principal do shader já está presente localmente."""
        raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        for item in raw.get("shaders", []) if isinstance(raw, dict) else []:
            if str(item.get("id", "")).strip() != shader_id:
                continue
            reference = str(item.get("reference", "")).strip().replace("\\", "/")
            if reference.startswith(":/shaders/"):
                return (self._shader_root() / reference.removeprefix(":/shaders/")).is_file()
            return False
        raise KeyError(f"Shader não encontrado no catálogo: {shader_id}")

    def install(self, spec: ShaderDownloadSpec, *, progress: Callable[[int, int], None] | None = None) -> ShaderDownloadResult:
        """Valida, baixa, filtra e instala arquivos de shader no RetroArch.

        O destino é validado antes da rede. A extração ocorre em memória e os
        arquivos são escritos em temporários antes de serem movidos atomically.
        """
        self._validate_repository(spec.repository)
        destination = self._validate_destination(spec.destination_subdir)
        archive = self._download_archive(spec)

        shader_root = self._shader_root().resolve()
        installed: list[Path] = []
        source_prefix = self._safe_relative(spec.source_subdir).as_posix().rstrip("/")
        with zipfile.ZipFile(io.BytesIO(archive)) as package:
            selected: list[tuple[zipfile.ZipInfo, Path]] = []
            for info in package.infolist():
                if info.is_dir():
                    continue
                relative = self._safe_relative(info.filename)
                parts = relative.parts[1:] if len(relative.parts) > 1 else ()
                inner = Path(*parts) if parts else Path()
                inner_text = inner.as_posix()
                if source_prefix and not (inner_text == source_prefix or inner_text.startswith(source_prefix + "/")):
                    continue
                candidate = inner_text[len(source_prefix):].lstrip("/") if source_prefix else inner_text
                if not candidate or not self._matches(candidate, spec.include):
                    continue
                target = (destination / self._safe_relative(candidate)).resolve()
                if shader_root not in target.parents and target != shader_root:
                    raise ValueError(f"Arquivo do pacote sairia da pasta de shaders: {candidate}")
                selected.append((info, target))

            if not selected:
                raise FileNotFoundError(f"Nenhum shader compatível encontrado em {spec.repository}@{spec.ref}" + (f"/{spec.source_subdir}" if spec.source_subdir else ""))

            for index, (info, target) in enumerate(selected, 1):
                target.parent.mkdir(parents=True, exist_ok=True)
                with package.open(info) as source, tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temp_file:
                    shutil.copyfileobj(source, temp_file)
                    temp_path = Path(temp_file.name)
                temp_path.replace(target)
                installed.append(target)
                if progress:
                    progress(index, len(selected))

        return ShaderDownloadResult(spec.shader_id, spec.repository, tuple(installed), destination)

    def install_from_catalog(self, shader_id: str, *, progress: Callable[[int, int], None] | None = None) -> ShaderDownloadResult:
        """Instala um shader usando a especificação de download do catálogo."""
        raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        for item in raw.get("shaders", []) if isinstance(raw, dict) else []:
            if str(item.get("id", "")).strip() != shader_id:
                continue
            download = item.get("download")
            if not isinstance(download, dict):
                raise ValueError(f"Shader '{shader_id}' não possui uma origem de download configurada.")
            spec = ShaderDownloadSpec(
                shader_id=shader_id,
                repository=str(download.get("repository", item.get("source_url", ""))),
                ref=str(download.get("ref", "main")),
                source_subdir=str(download.get("source_subdir", "")),
                destination_subdir=str(download.get("destination_subdir", "")),
                include=tuple(str(v) for v in download.get("include", ["*.slang", "*.slangp", "*.glsl"])),
            )
            return self.install(spec, progress=progress)
        raise KeyError(f"Shader não encontrado no catálogo: {shader_id}")


__all__ = ["ShaderDownloadResult", "ShaderDownloadService", "ShaderDownloadSpec"]
