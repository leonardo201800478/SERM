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

    def reconstruct_one(self, source_directory: str | Path, definition: RetroArchBiosFile, overwrite: bool = True) -> RetroArchBiosReconstructionResult:
        """Repara uma única BIOS/firmware selecionada na interface."""
        source = Path(source_directory).expanduser().resolve()
        if not source.is_dir():
            raise ValueError(f"Pasta de origem não encontrada: {source}")
        files = [path for path in source.rglob("*") if path.is_file()]
        by_name: dict[str, list[Path]] = {}
        for path in files:
            by_name.setdefault(path.name.casefold(), []).append(path)
        results = self._copy_definitions([definition], by_name, files, overwrite)
        return results[0]

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
        for path in files:
            by_name.setdefault(path.name.casefold(), []).append(path)
        return self._copy_definitions(definitions, by_name, files, overwrite)

    def _reconstruct_destinations(self, source_directory: str | Path, destinations: set[str], overwrite: bool) -> list[RetroArchBiosReconstructionResult]:
        """Reconstrói um subconjunto de destinos identificado pelo scanner."""
        source = Path(source_directory).expanduser().resolve()
        if not source.is_dir():
            raise ValueError(f"Pasta de origem não encontrada: {source}")
        files = [path for path in source.rglob("*") if path.is_file()]
        by_name: dict[str, list[Path]] = {}
        for path in files:
            by_name.setdefault(path.name.casefold(), []).append(path)
        definitions = [d for system in self.scanner.systems for d in system.files if d.destination in destinations]
        return self._copy_definitions(definitions, by_name, files, overwrite)

    def _copy_definitions(self, definitions: list[RetroArchBiosFile], by_name: dict[str, list[Path]], files: list[Path], overwrite: bool) -> list[RetroArchBiosReconstructionResult]:
        """Localiza, valida e materializa definições no destino do catálogo."""
        results: list[RetroArchBiosReconstructionResult] = []
        for definition in definitions:
            destination = self._target(definition)
            candidates = list(by_name.get(Path(definition.name).name.casefold(), []))
            # Sem hash, o nome/extensão são a identidade. Não procurar em todos
            # os arquivos por tamanho, pois isso poderia associar uma BIOS errada.
            if any((definition.sha1, definition.md5, definition.crc32)):
                candidates.extend(path for path in files if path not in candidates)
            candidate = self._find_candidate(definition, candidates)
            if candidate is None:
                results.append(RetroArchBiosReconstructionResult(definition, None, destination, "missing", "Nenhum arquivo compatível encontrado"))
                continue
            try:
                self._ensure_destination_parent(destination)
                if destination.exists() and destination.is_dir():
                    results.append(RetroArchBiosReconstructionResult(definition, candidate, destination, "error", "O destino esperado é um arquivo, mas existe uma pasta com o mesmo nome"))
                    continue
                if destination.exists() and not overwrite:
                    results.append(RetroArchBiosReconstructionResult(definition, candidate, destination, "skipped", "Destino já existe"))
                    continue
                shutil.copy2(candidate, destination)
                results.append(RetroArchBiosReconstructionResult(definition, candidate, destination, "reconstructed", "Arquivo reconstruído e validado"))
            except (OSError, shutil.Error) as exc:
                results.append(RetroArchBiosReconstructionResult(definition, candidate, destination, "error", str(exc)))
        return results

    def _ensure_destination_parent(self, destination: Path) -> None:
        """Garante que somente o diretório pai seja criado, sem tentar criar o arquivo."""
        parent = destination.parent
        if parent.exists():
            if not parent.is_dir():
                raise OSError(f"Diretório pai inválido: {parent}")
            return
        parent.mkdir(parents=True, exist_ok=True)

    def _target(self, definition: RetroArchBiosFile) -> Path:
        """Resolve o destino relativo ao System Directory de forma portátil."""
        relative = definition.destination.replace("/", os.sep).replace("\\", os.sep)
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"Destino de BIOS inválido no catálogo: {definition.destination}")
        return self.system_directory / relative_path

    @staticmethod
    def _find_candidate(definition: RetroArchBiosFile, candidates: list[Path]) -> Path | None:
        """Encontra candidato pela regra de identidade da BIOS.

        Com hash, o hash é a autoridade e permite corrigir nome/local.
        Sem hash, somente o nome exato, incluindo extensão, é aceito.
        """
        has_hash = any((definition.sha1, definition.md5, definition.crc32))
        for candidate in candidates:
            try:
                if not has_hash:
                    return candidate
                if definition.size is not None and candidate.stat().st_size != definition.size:
                    continue
                hashes = RetroArchBiosReconstructionService._hashes(candidate)
            except OSError:
                continue
            if definition.sha1 and hashes["sha1"].casefold() == definition.sha1.casefold():
                return candidate
            if definition.md5 and hashes["md5"].casefold() == definition.md5.casefold():
                return candidate
            if definition.crc32 and hashes["crc32"].casefold() == str(definition.crc32).casefold().zfill(8):
                return candidate
        return None

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
