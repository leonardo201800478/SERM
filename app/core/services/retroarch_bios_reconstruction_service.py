"""Reconstrução segura de BIOS/firmware para o RetroArch."""
from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.core.services.retroarch_bios_service import RetroArchBiosFile, RetroArchBiosService


@dataclass(frozen=True, slots=True)
class RetroArchBiosReconstructionResult:
    """Resultado de uma tentativa de reconstrução de BIOS."""
    definition: RetroArchBiosFile
    source: Path | None
    destination: Path
    status: str
    message: str = ""


class RetroArchBiosReconstructionService:
    """Reconstrói arquivos e diretórios de firmware para o RetroArch."""

    def __init__(self, system_directory: str | Path) -> None:
        """Inicializa a reconstrução apontando para o System Directory real."""
        self.system_directory = Path(system_directory).expanduser().resolve()
        self.scanner = RetroArchBiosService(self.system_directory)

    def load_catalog(self) -> list:
        """Carrega o mesmo catálogo utilizado pelo scanner."""
        return self.scanner.load_catalog()

    def reconstruct_missing(self, source_directory: str | Path, overwrite: bool = False) -> list[RetroArchBiosReconstructionResult]:
        """Reconstrói somente BIOS ausentes."""
        scan = self.scanner.scan()
        needed = {item.definition.destination for item in scan if item.status == "missing"}
        return self._reconstruct_destinations(source_directory, needed, overwrite)

    def reconstruct_needed(self, source_directory: str | Path) -> list[RetroArchBiosReconstructionResult]:
        """Reconstrói BIOS ausentes, corrigíveis ou corrompidas."""
        scan = self.scanner.scan()
        needed = {item.definition.destination for item in scan if item.status in {"missing", "fixable", "corrupt"}}
        return self._reconstruct_destinations(source_directory, needed, True)

    def reconstruct_one(self, source_directory: str | Path, definition: RetroArchBiosFile, overwrite: bool = True) -> RetroArchBiosReconstructionResult:
        """Repara uma única BIOS/firmware selecionada na interface."""
        source = Path(source_directory).expanduser().resolve()
        if not source.is_dir():
            raise ValueError(f"Pasta de origem não encontrada: {source}")
        return self._reconstruct_definitions(source, [definition], overwrite)[0]

    def reconstruct_from_directory(self, source_directory: str | Path, systems: Iterable[str] | None = None, overwrite: bool = False) -> list[RetroArchBiosReconstructionResult]:
        """Reconstrói arquivos e diretórios compatíveis de uma fonte."""
        source = Path(source_directory).expanduser().resolve()
        if not source.is_dir():
            raise ValueError(f"Pasta de origem não encontrada: {source}")
        self.system_directory.mkdir(parents=True, exist_ok=True)
        allowed = set(systems or ())
        definitions = [d for system in self.scanner.systems if not allowed or system.system_id in allowed for d in system.files]
        return self._reconstruct_definitions(source, definitions, overwrite)

    def _reconstruct_destinations(self, source_directory: str | Path, destinations: set[str], overwrite: bool) -> list[RetroArchBiosReconstructionResult]:
        """Reconstrói um subconjunto de destinos identificado pelo scanner."""
        source = Path(source_directory).expanduser().resolve()
        if not source.is_dir():
            raise ValueError(f"Pasta de origem não encontrada: {source}")
        definitions = [d for system in self.scanner.systems for d in system.files if d.destination in destinations]
        return self._reconstruct_definitions(source, definitions, overwrite)

    def _reconstruct_definitions(self, source: Path, definitions: list[RetroArchBiosFile], overwrite: bool) -> list[RetroArchBiosReconstructionResult]:
        """Reconstrói cada definição preservando a distinção entre arquivo e diretório."""
        results: list[RetroArchBiosReconstructionResult] = []
        for definition in definitions:
            destination = self._target(definition)
            try:
                if definition.is_directory:
                    result = self._reconstruct_directory(source, definition, destination, overwrite)
                else:
                    result = self._reconstruct_file(source, definition, destination, overwrite)
                results.append(result)
            except (OSError, shutil.Error, ValueError) as exc:
                results.append(RetroArchBiosReconstructionResult(definition, None, destination, "error", str(exc)))
        return results

    def _reconstruct_directory(self, source: Path, definition: RetroArchBiosFile, destination: Path, overwrite: bool) -> RetroArchBiosReconstructionResult:
        """Reconstrói uma entrada declarada como pasta, copiando seu conteúdo."""
        candidate = self._find_source_directory(source, definition)
        if candidate is None:
            return RetroArchBiosReconstructionResult(definition, None, destination, "missing", "Diretório de firmware não encontrado na origem")
        if destination.exists() and destination.is_file():
            return RetroArchBiosReconstructionResult(definition, candidate, destination, "error", "O destino esperado é um diretório, mas existe um arquivo com o mesmo nome")
        if destination.exists() and not overwrite:
            return RetroArchBiosReconstructionResult(definition, candidate, destination, "skipped", "Diretório já existe")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and overwrite:
            shutil.rmtree(destination)
        shutil.copytree(candidate, destination, dirs_exist_ok=True)
        return RetroArchBiosReconstructionResult(definition, candidate, destination, "reconstructed", "Diretório reconstruído")

    def _reconstruct_file(self, source: Path, definition: RetroArchBiosFile, destination: Path, overwrite: bool) -> RetroArchBiosReconstructionResult:
        """Reconstrói uma entrada declarada como arquivo."""
        candidate = self._find_source_file(source, definition)
        if candidate is None:
            return RetroArchBiosReconstructionResult(definition, None, destination, "missing", "Arquivo de firmware não encontrado na origem")
        if destination.exists() and destination.is_dir():
            return RetroArchBiosReconstructionResult(definition, candidate, destination, "error", "O destino esperado é um arquivo, mas existe uma pasta com o mesmo nome")
        if destination.exists() and not overwrite:
            return RetroArchBiosReconstructionResult(definition, candidate, destination, "skipped", "Destino já existe")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate, destination)
        return RetroArchBiosReconstructionResult(definition, candidate, destination, "reconstructed", "Arquivo reconstruído e validado")

    def _find_source_directory(self, source: Path, definition: RetroArchBiosFile) -> Path | None:
        """Localiza a pasta pelo caminho relativo ou pelo nome final."""
        relative = self._relative(definition.destination)
        direct = source / relative
        if direct.is_dir():
            return direct
        expected_name = relative.name.casefold()
        for candidate in source.rglob("*"):
            if candidate.is_dir() and candidate.name.casefold() == expected_name:
                return candidate
        return None

    def _find_source_file(self, source: Path, definition: RetroArchBiosFile) -> Path | None:
        """Localiza arquivo por nome quando não há hash ou por hash quando existe."""
        relative = self._relative(definition.destination)
        direct = source / relative
        if direct.is_file() and self._matches(definition, direct):
            return direct
        candidates = [p for p in source.rglob("*") if p.is_file() and p.name.casefold() == Path(definition.name).name.casefold()]
        if any((definition.sha1, definition.md5, definition.crc32)):
            candidates.extend(p for p in source.rglob("*") if p.is_file() and p not in candidates)
        return next((p for p in candidates if self._matches(definition, p)), None)

    def _matches(self, definition: RetroArchBiosFile, candidate: Path) -> bool:
        """Aplica hash quando existe; caso contrário exige nome + extensão."""
        if definition.size is not None and candidate.stat().st_size != definition.size:
            return False
        if not any((definition.sha1, definition.md5, definition.crc32)):
            return candidate.name.casefold() == Path(definition.name).name.casefold()
        hashes = self._hashes(candidate)
        return bool(
            (definition.sha1 and hashes["sha1"].casefold() == definition.sha1.casefold())
            or (definition.md5 and hashes["md5"].casefold() == definition.md5.casefold())
            or (definition.crc32 and hashes["crc32"].casefold() == str(definition.crc32).casefold().zfill(8))
        )

    def _target(self, definition: RetroArchBiosFile) -> Path:
        """Resolve o destino relativo ao System Directory sem permitir traversal."""
        return self.system_directory / self._relative(definition.destination)

    @staticmethod
    def _relative(value: str) -> Path:
        """Normaliza caminho Libretro e rejeita caminhos absolutos ou traversal."""
        normalized = value.replace("/", os.sep).replace("\\", os.sep).rstrip(os.sep)
        path = Path(normalized)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Destino de BIOS inválido no catálogo: {value}")
        return path

    @staticmethod
    def _hashes(path: Path) -> dict[str, str]:
        """Calcula SHA1, MD5 e CRC32 em uma única leitura."""
        import zlib
        sha1, md5, crc = hashlib.sha1(), hashlib.md5(), 0
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                sha1.update(chunk)
                md5.update(chunk)
                crc = zlib.crc32(chunk, crc)
        return {"sha1": sha1.hexdigest(), "md5": md5.hexdigest(), "crc32": f"{crc & 0xffffffff:08x}"}


__all__ = ["RetroArchBiosReconstructionService", "RetroArchBiosReconstructionResult"]
