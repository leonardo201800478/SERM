"""Catálogo, verificação e matching de BIOS/firmware do RetroArch."""
from __future__ import annotations

import hashlib
import os
import urllib.request
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.services.retroarch_info_service import RetroArchInfoCore

RETROBIOS_RAW_URL = "https://raw.githubusercontent.com/Abdess/retrobios/main/platforms/retroarch.yml"


@dataclass(frozen=True, slots=True)
class RetroArchBiosFile:
    """Define um arquivo ou diretório de firmware requerido por um sistema."""
    name: str
    destination: str
    required: bool
    sha1: str | None = None
    md5: str | None = None
    crc32: str | None = None
    size: int | None = None
    is_directory: bool = False


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
    """Estado encontrado para um arquivo ou diretório de BIOS."""
    definition: RetroArchBiosFile
    path: Path
    status: str
    actual_size: int | None = None
    actual_sha1: str | None = None
    actual_md5: str | None = None
    actual_crc32: str | None = None
    message: str = ""


class RetroArchBiosService:
    """Carrega catálogo local .info e verifica BIOS/firmware no System Directory."""

    def __init__(self, system_directory: str | Path | None = None) -> None:
        self.system_directory = Path(system_directory).expanduser() if system_directory else None
        self.systems: list[RetroArchBiosSystem] = []
        self._hash_index: dict[str, Path] = {}
        self._name_index: dict[str, list[Path]] = {}
        self._hash_index_ready = False

    def load_info_catalog(self, cores: list[RetroArchInfoCore]) -> list[RetroArchBiosSystem]:
        """Constrói o catálogo de BIOS diretamente dos .info locais."""
        systems: list[RetroArchBiosSystem] = []
        for core in cores:
            if not core.system_id:
                continue
            files = [
                RetroArchBiosFile(
                    name=Path(firmware.path.rstrip("/\\")).name or firmware.path,
                    destination=firmware.path.replace("\\", "/").rstrip("/") if firmware.is_directory else firmware.path.replace("\\", "/"),
                    required=not firmware.optional,
                    md5=firmware.md5,
                    is_directory=firmware.is_directory,
                )
                for firmware in core.firmware
            ]
            systems.append(RetroArchBiosSystem(
                system_id=core.system_id,
                native_id=core.system_id,
                core=core.corename,
                docs=None,
                files=files,
            ))
        self.systems = systems
        self.reset_scan_cache()
        return systems

    def load_catalog(self, url: str = RETROBIOS_RAW_URL) -> list[RetroArchBiosSystem]:
        """Carrega RetroBIOS externo como fallback/enriquecimento."""
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError("PyYAML é necessário para o catálogo RetroBIOS.") from exc
        request = urllib.request.Request(url, headers={"User-Agent": "arcade-manager RetroArch BIOS scanner"})
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
        data = yaml.safe_load(raw) or {}
        systems: list[RetroArchBiosSystem] = []
        for system_id, payload in (data.get("systems") or {}).items():
            files = [RetroArchBiosFile(
                name=str(entry.get("name", "")), destination=str(entry.get("destination") or entry.get("name") or ""),
                required=bool(entry.get("required", False)), sha1=str(entry.get("sha1")) if entry.get("sha1") else None,
                md5=str(entry.get("md5")) if entry.get("md5") else None, crc32=str(entry.get("crc32")) if entry.get("crc32") else None,
                size=int(entry["size"]) if entry.get("size") is not None else None,
                is_directory=bool(entry.get("is_directory", False)),
            ) for entry in payload.get("files") or []]
            systems.append(RetroArchBiosSystem(system_id=str(system_id), native_id=str(payload.get("native_id") or system_id), core=str(payload.get("core")) if payload.get("core") else None, docs=str(payload.get("docs")) if payload.get("docs") else None, files=files))
        self.systems = systems
        self.reset_scan_cache()
        return systems

    def systems_for_core(self, core_name: str) -> list[RetroArchBiosSystem]:
        """Retorna os sistemas cobertos pelo core atual."""
        key = core_name.casefold().removesuffix("_libretro")
        return [s for s in self.systems if s.core and s.core.casefold().removesuffix("_libretro") == key]

    def scan(self) -> list[RetroArchBiosResult]:
        """Verifica todo o catálogo e identifica OK, corrigível, corrompido ou ausente."""
        if self.system_directory is None:
            raise ValueError("Diretório System do RetroArch não configurado.")
        self._prepare_hash_index()
        return [self._verify(d, self._target(d)) for s in self.systems for d in s.files]

    def scan_systems_for_core(self, core_name: str) -> dict[str, list[RetroArchBiosResult]]:
        """Varre somente os sistemas associados ao core informado."""
        self._prepare_hash_index()
        return {system.system_id: [self._verify(d, self._target(d)) for d in system.files] for system in self.systems_for_core(core_name)}

    def _prepare_hash_index(self) -> None:
        """Indexa nomes e hashes dos arquivos existentes uma única vez por varredura."""
        if self._hash_index_ready or self.system_directory is None:
            return
        root = self.system_directory.resolve()
        if not root.is_dir():
            self._hash_index_ready = True
            return
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                self._name_index.setdefault(path.name.casefold(), []).append(path)
                values = self._hashes(path)
            except OSError:
                continue
            for key in values.values():
                self._hash_index.setdefault(key, path)
        self._hash_index_ready = True

    def reset_scan_cache(self) -> None:
        """Invalida o índice para uma nova leitura do System Directory."""
        self._hash_index.clear()
        self._name_index.clear()
        self._hash_index_ready = False

    def _target(self, definition: RetroArchBiosFile) -> Path:
        """Resolve destino relativo ao System Directory de forma portátil."""
        if self.system_directory is None:
            raise ValueError("Diretório System do RetroArch não configurado.")
        relative = definition.destination.replace("/", os.sep).replace("\\", os.sep)
        return self.system_directory.resolve() / Path(relative)

    def _verify(self, definition: RetroArchBiosFile, target: Path) -> RetroArchBiosResult:
        """Classifica arquivo/diretório conforme a definição do catálogo."""
        if definition.is_directory:
            if target.is_dir():
                return RetroArchBiosResult(definition, target, "ok", message="Diretório de BIOS presente")
            if target.exists():
                return RetroArchBiosResult(definition, target, "corrupt", message="O destino esperado é um diretório, mas existe um arquivo com o mesmo nome")
            candidate = self._find_matching_directory(definition)
            if candidate:
                return RetroArchBiosResult(definition, target, "fixable", message=f"Diretório compatível encontrado em {candidate}")
            return RetroArchBiosResult(definition, target, "missing", message="Diretório ausente")

        if not target.is_file():
            if target.exists():
                return RetroArchBiosResult(definition, target, "corrupt", message="O destino esperado é um arquivo, mas existe um diretório com o mesmo nome")
            candidate = self._find_matching_file(definition)
            if candidate:
                return RetroArchBiosResult(definition, target, "fixable", message=f"Arquivo compatível encontrado em {candidate}")
            return RetroArchBiosResult(definition, target, "missing", message="Arquivo ausente")
        try:
            actual_size, actual_sha1, actual_md5, actual_crc32 = self._hashes(target, with_size=True)
        except OSError as exc:
            return RetroArchBiosResult(definition, target, "corrupt", message=str(exc))
        if definition.size is not None and actual_size != definition.size:
            return RetroArchBiosResult(definition, target, "corrupt", actual_size, actual_sha1, actual_md5, actual_crc32, f"Tamanho inválido: {actual_size} != {definition.size}")
        matches = [bool(definition.sha1 and actual_sha1.casefold() == definition.sha1.casefold()), bool(definition.md5 and actual_md5.casefold() == definition.md5.casefold()), bool(definition.crc32 and actual_crc32.casefold() == str(definition.crc32).casefold().zfill(8))]
        if any(matches) or not any((definition.sha1, definition.md5, definition.crc32)):
            return RetroArchBiosResult(definition, target, "ok", actual_size, actual_sha1, actual_md5, actual_crc32)
        return RetroArchBiosResult(definition, target, "corrupt", actual_size, actual_sha1, actual_md5, actual_crc32, "Hash diferente do catálogo")

    def _find_matching_directory(self, definition: RetroArchBiosFile) -> Path | None:
        """Procura diretório de firmware pelo nome, sem tratar diretório como arquivo."""
        if self.system_directory is None:
            return None
        expected = Path(definition.destination.replace("/", os.sep).replace("\\", os.sep))
        name = expected.name.casefold()
        return next((p for p in self.system_directory.resolve().rglob("*") if p.is_dir() and p.name.casefold() == name), None)

    def _find_matching_file(self, definition: RetroArchBiosFile) -> Path | None:
        """Procura uma cópia válida, respeitando a regra de identidade do catálogo."""
        has_hash = any((definition.sha1, definition.md5, definition.crc32))
        if not has_hash:
            candidates = self._name_index.get(Path(definition.name).name.casefold(), [])
            return candidates[0] if candidates else None
        keys = set()
        if definition.sha1:
            keys.add(definition.sha1.casefold())
        if definition.md5:
            keys.add(definition.md5.casefold())
        if definition.crc32:
            keys.add(str(definition.crc32).casefold().zfill(8))
        for key in keys:
            candidate = self._hash_index.get(key)
            if candidate is not None:
                return candidate
        return None

    @staticmethod
    def _hashes(path: Path, with_size: bool = False):
        """Calcula SHA1, MD5 e CRC32 em uma única leitura."""
        sha1, md5, crc, size = hashlib.sha1(), hashlib.md5(), 0, 0
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk); sha1.update(chunk); md5.update(chunk); crc = zlib.crc32(chunk, crc)
        values = (size, sha1.hexdigest(), md5.hexdigest(), f"{crc & 0xffffffff:08x}")
        return values if with_size else {"sha1": values[1], "md5": values[2], "crc32": values[3]}

    @staticmethod
    def serialize_scan(results: list[RetroArchBiosResult]) -> list[dict[str, Any]]:
        """Converte resultados para estruturas serializáveis."""
        return [{"name": r.definition.name, "destination": r.definition.destination, "required": r.definition.required, "status": r.status, "path": str(r.path), "actual_size": r.actual_size, "actual_sha1": r.actual_sha1, "actual_md5": r.actual_md5, "actual_crc32": r.actual_crc32, "message": r.message} for r in results]


__all__ = ["RetroArchBiosService", "RetroArchBiosFile", "RetroArchBiosSystem", "RetroArchBiosResult"]
