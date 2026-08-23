"""Catálogo e verificação de BIOS/firmware do RetroArch.

A fonte de metadados é o dataset RetroBIOS/Libretro, mas os arquivos de
firmware nunca são baixados por este serviço. A varredura trabalha somente
sobre o diretório ``system`` configurado no RetroArch e aplica o princípio de
verificação baseado em nome, destino e, quando disponível, hashes.
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


RETROBIOS_RAW_URL = (
    "https://raw.githubusercontent.com/Abdess/retrobios/main/platforms/retroarch.yml"
)


@dataclass(frozen=True, slots=True)
class RetroArchBiosFile:
    """Define um arquivo de BIOS/firmware requerido por um sistema."""

    name: str
    destination: str
    required: bool
    sha1: str | None = None
    md5: str | None = None
    crc32: str | None = None
    size: int | None = None


@dataclass(slots=True)
class RetroArchBiosSystem:
    """Sistema emulado por um core e seus arquivos de firmware."""

    system_id: str
    native_id: str
    core: str | None
    docs: str | None
    files: list[RetroArchBiosFile] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RetroArchBiosResult:
    """Estado encontrado para um arquivo de BIOS."""

    definition: RetroArchBiosFile
    path: Path
    status: str
    actual_size: int | None = None
    actual_sha1: str | None = None
    actual_md5: str | None = None
    message: str = ""


class RetroArchBiosService:
    """Carrega catálogo externo e verifica a pasta System do RetroArch."""

    def __init__(self, system_directory: str | Path | None = None) -> None:
        """Inicializa o serviço com o diretório System atual."""
        self.system_directory = Path(system_directory).expanduser() if system_directory else None
        self.systems: list[RetroArchBiosSystem] = []

    def load_catalog(self, url: str = RETROBIOS_RAW_URL) -> list[RetroArchBiosSystem]:
        """Baixa o YAML do RetroBIOS e o converte para o modelo interno."""
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError("PyYAML é necessário para o catálogo RetroBIOS.") from exc
        request = urllib.request.Request(url, headers={"User-Agent": "mame-set-builder RetroArch BIOS scanner"})
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
        data = yaml.safe_load(raw) or {}
        systems: list[RetroArchBiosSystem] = []
        for system_id, payload in (data.get("systems") or {}).items():
            files: list[RetroArchBiosFile] = []
            for entry in payload.get("files") or []:
                files.append(
                    RetroArchBiosFile(
                        name=str(entry.get("name", "")),
                        destination=str(entry.get("destination") or entry.get("name") or ""),
                        required=bool(entry.get("required", False)),
                        sha1=str(entry.get("sha1")) if entry.get("sha1") else None,
                        md5=str(entry.get("md5")) if entry.get("md5") else None,
                        crc32=str(entry.get("crc32")) if entry.get("crc32") else None,
                        size=int(entry["size"]) if entry.get("size") is not None else None,
                    )
                )
            systems.append(
                RetroArchBiosSystem(
                    system_id=str(system_id),
                    native_id=str(payload.get("native_id") or system_id),
                    core=str(payload.get("core")) if payload.get("core") else None,
                    docs=str(payload.get("docs")) if payload.get("docs") else None,
                    files=files,
                )
            )
        self.systems = systems
        return systems

    def systems_for_core(self, core_name: str) -> list[RetroArchBiosSystem]:
        """Retorna sistemas cobertos por um core, aceitando aliases simples."""
        key = core_name.casefold().removesuffix("_libretro")
        return [
            system
            for system in self.systems
            if system.core and system.core.casefold().removesuffix("_libretro") == key
        ]

    def scan(self) -> list[RetroArchBiosResult]:
        """Verifica todos os arquivos do catálogo sob o System Directory."""
        if self.system_directory is None:
            raise ValueError("Diretório System do RetroArch não configurado.")
        root = self.system_directory.resolve()
        results: list[RetroArchBiosResult] = []
        for system in self.systems:
            for definition in system.files:
                target = root / Path(definition.destination.replace("/", str(Path.sep)))
                results.append(self._verify(definition, target))
        return results

    def scan_systems_for_core(self, core_name: str) -> dict[str, list[RetroArchBiosResult]]:
        """Varre apenas os sistemas associados ao core informado."""
        result: dict[str, list[RetroArchBiosResult]] = {}
        for system in self.systems_for_core(core_name):
            result[system.system_id] = [self._verify(definition, self._target(definition)) for definition in system.files]
        return result

    def _target(self, definition: RetroArchBiosFile) -> Path:
        """Resolve um destino relativo ao System Directory."""
        if self.system_directory is None:
            raise ValueError("Diretório System do RetroArch não configurado.")
        return self.system_directory.resolve() / Path(definition.destination.replace("/", str(Path.sep)))

    def _verify(self, definition: RetroArchBiosFile, target: Path) -> RetroArchBiosResult:
        """Classifica um arquivo como ausente, correto, corrigível ou corrompido."""
        if not target.is_file():
            return RetroArchBiosResult(definition, target, "missing", message="Arquivo ausente")
        actual_size = target.stat().st_size
        if definition.size is not None and actual_size != definition.size:
            return RetroArchBiosResult(
                definition,
                target,
                "corrupt",
                actual_size=actual_size,
                message=f"Tamanho inválido: {actual_size} != {definition.size}",
            )
        actual_sha1 = self._hash(target, "sha1")
        actual_md5 = self._hash(target, "md5")
        if definition.sha1 and actual_sha1.casefold() == definition.sha1.casefold():
            return RetroArchBiosResult(definition, target, "ok", actual_size, actual_sha1, actual_md5)
        if definition.md5 and actual_md5.casefold() == definition.md5.casefold():
            return RetroArchBiosResult(definition, target, "ok", actual_size, actual_sha1, actual_md5)
        if definition.sha1 or definition.md5 or definition.crc32:
            return RetroArchBiosResult(
                definition,
                target,
                "corrupt",
                actual_size,
                actual_sha1,
                actual_md5,
                "Hash diferente do catálogo",
            )
        return RetroArchBiosResult(definition, target, "ok", actual_size, actual_sha1, actual_md5)

    @staticmethod
    def _hash(path: Path, algorithm: str) -> str:
        """Calcula um hash de arquivo em blocos."""
        digest = hashlib.new(algorithm)
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def serialize_scan(results: list[RetroArchBiosResult]) -> list[dict[str, Any]]:
        """Converte resultados para estruturas serializáveis pela GUI/banco."""
        return [
            {
                "name": item.definition.name,
                "destination": item.definition.destination,
                "required": item.definition.required,
                "status": item.status,
                "path": str(item.path),
                "actual_size": item.actual_size,
                "actual_sha1": item.actual_sha1,
                "actual_md5": item.actual_md5,
                "message": item.message,
            }
            for item in results
        ]
