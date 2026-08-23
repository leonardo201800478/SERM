"""Reconstrução segura de BIOS/firmware para o RetroArch."""
from __future__ import annotations

import hashlib
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
    """Reconstrói arquivos de BIOS a partir de uma pasta de origem."""

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
        """Reconstrói BIOS ausentes, corrigíveis ou corrompidas, preservando as OK."""
        scan = self.scanner.scan()
        needed = {item.definition.destination for item in scan if item.status in {"missing", "fixable", "corrupt"}}
        return self._reconstruct_destinations(source_directory, needed, True)

    def reconstruct_from_directory(self, source_directory: str | Path, systems: Iterable[str] | None = None, overwrite: bool = False) -> list[RetroArchBiosReconstructionResult]:
        """Reconstrói arquivos compatíveis de uma fonte usando destinos do catálogo."""
        source = Path(source_directory).expanduser().resolve()
        if not source.is_dir():
            raise ValueError(f"Pasta de origem não encontrada: {source}")
        self.system_directory.mkdir(parents=True, exist_ok=True)
        allowed = set(systems or ())
        definitions = [d for system in self.scanner.systems if not allowed or system.system_id in allowed for d in system.files]
        files = [path for path in source.rglob("*") if path.is_file()]
        by_name: dict[str, list[Path]] = {}
        for path in files: by_name.setdefault(path.name.casefold(), []).append(path)
        return self._copy_definitions(definitions, by_name, files, overwrite)

    def _reconstruct_destinations(self, source_directory: str | Path, destinations: set[str], overwrite: bool) -> list[RetroArchBiosReconstructionResult]:
        """Reconstrói um subconjunto de destinos identificado pelo scanner."""
        source = Path(source_directory).expanduser().resolve()
        if not source.is_dir(): raise ValueError(f"Pasta de origem não encontrada: {source}")
        files = [path for path in source.rglob("*") if path.is_file()]
        by_name: dict[str, list[Path]] = {}
        for path in files: by_name.setdefault(path.name.casefold(), []).append(path)
        definitions = [d for system in self.scanner.systems for d in system.files if d.destination in destinations]
        return self._copy_definitions(definitions, by_name, files, overwrite)

    def _copy_definitions(self, definitions: list[RetroArchBiosFile], by_name: dict[str, list[Path]], files: list[Path], overwrite: bool) -> list[RetroArchBiosReconstructionResult]:
        """Localiza, valida e materializa definições no destino do catálogo."""
        results: list[RetroArchBiosReconstructionResult] = []
        for definition in definitions:
            destination = self.system_directory / Path(definition.destination.replace("/", str(Path.sep)))
            candidate = self._find_candidate(definition, by_name.get(Path(definition.name).name.casefold(), []), files)
            if candidate is None:
                results.append(RetroArchBiosReconstructionResult(definition, None, destination, "missing", "Nenhum arquivo compatível encontrado")); continue
            if destination.exists() and not overwrite:
                results.append(RetroArchBiosReconstructionResult(definition, candidate, destination, "skipped", "Destino já existe")); continue
            destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(candidate, destination)
            results.append(RetroArchBiosReconstructionResult(definition, candidate, destination, "reconstructed", "Arquivo reconstruído e validado"))
        return results

    @staticmethod
    def _find_candidate(definition: RetroArchBiosFile, named_candidates: list[Path], all_files: list[Path]) -> Path | None:
        """Encontra candidato válido, priorizando o nome esperado."""
        for candidate in named_candidates or all_files:
            if definition.size is not None and candidate.stat().st_size != definition.size: continue
            hashes = RetroArchBiosReconstructionService._hashes(candidate)
            if definition.sha1 and hashes["sha1"].casefold() == definition.sha1.casefold(): return candidate
            if definition.md5 and hashes["md5"].casefold() == definition.md5.casefold(): return candidate
            if definition.crc32 and hashes["crc32"].casefold() == str(definition.crc32).casefold().zfill(8): return candidate
            if not any((definition.sha1, definition.md5, definition.crc32)): return candidate
        return None

    @staticmethod
    def _hashes(path: Path) -> dict[str, str]:
        """Calcula SHA1, MD5 e CRC32 em uma única leitura."""
        import zlib
        sha1, md5, crc = hashlib.sha1(), hashlib.md5(), 0
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024): sha1.update(chunk); md5.update(chunk); crc = zlib.crc32(chunk, crc)
        return {"sha1": sha1.hexdigest(), "md5": md5.hexdigest(), "crc32": f"{crc & 0xffffffff:08x}"}


__all__ = ["RetroArchBiosReconstructionService", "RetroArchBiosReconstructionResult"]
