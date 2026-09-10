"""Materializacao fisica segura do Arcade Studio V2.

O materializador consome exclusivamente um ``ReconstructionManifest`` ja
validado. Ele nao interpreta parent/clone nem hashes novamente: essas decisoes
pertencem as camadas anteriores. ROMs sao escritas em ZIPs e CHDs sao mantidos
como arquivos ``.chd`` em diretorios de machine.

A escrita e atomica por arquivo de destino. Os arquivos de origem nunca sao
alterados ou removidos.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from .reconstruction_manifest import MaterializationEntry, MaterializationKind, ReconstructionManifest

ProgressCallback = Callable[[int, int, MaterializationEntry], None]


class MaterializationError(RuntimeError):
    """Falha que impede uma materializacao segura."""


class ArcadeSetMaterializer:
    """Materializa um manifesto sem depender de ferramentas externas."""

    def materialize(
        self,
        manifest: ReconstructionManifest,
        destination: Path,
        *,
        overwrite: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> tuple[Path, ...]:
        if not manifest.is_ready:
            raise MaterializationError("Manifesto nao esta pronto para materializacao.")

        destination = destination.expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        self._validate_sources(manifest.entries)
        self._validate_destinations(manifest.entries)

        archive_entries: dict[str, list[MaterializationEntry]] = defaultdict(list)
        chd_entries: list[MaterializationEntry] = []
        for entry in manifest.entries:
            if entry.kind is MaterializationKind.ROM:
                if not entry.archive or not entry.member_name:
                    raise MaterializationError(f"Entrada ROM incompleta: {entry}")
                archive_entries[entry.archive].append(entry)
            elif entry.kind is MaterializationKind.CHD:
                chd_entries.append(entry)
            else:
                raise MaterializationError(f"Tipo de materializacao desconhecido: {entry.kind}")

        outputs: list[Path] = []
        total = len(manifest.entries)
        completed = 0

        for archive_name, entries in sorted(archive_entries.items()):
            target = self._safe_path(destination, archive_name)
            if target.exists() and not overwrite:
                raise MaterializationError(f"Destino ja existe: {target}")
            self._write_archive(target, entries, overwrite=overwrite)
            outputs.append(target)
            completed += len(entries)
            self._report(progress_callback, completed, total, entries[-1])

        for entry in chd_entries:
            target = self._safe_path(destination, entry.destination)
            if target.exists() and not overwrite:
                raise MaterializationError(f"Destino ja existe: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            self._copy_atomic(Path(entry.source_path), target)
            outputs.append(target)
            completed += 1
            self._report(progress_callback, completed, total, entry)

        return tuple(outputs)

    @staticmethod
    def _validate_sources(entries: tuple[MaterializationEntry, ...]) -> None:
        for entry in entries:
            source = Path(entry.source_path).expanduser()
            if not source.is_file():
                raise MaterializationError(f"Arquivo de origem nao encontrado: {source}")

    @classmethod
    def _validate_destinations(cls, entries: tuple[MaterializationEntry, ...]) -> None:
        seen: dict[str, str] = {}
        for entry in entries:
            if entry.kind is MaterializationKind.ROM:
                if not entry.archive or not entry.member_name:
                    raise MaterializationError(f"Destino ROM incompleto: {entry}")
                archive = cls._normalise_relative(entry.archive)
                member = cls._normalise_relative(entry.member_name)
                path = f"{archive}!/{member}"
            else:
                path = cls._normalise_relative(entry.destination)
            previous = seen.get(path)
            if previous is not None and previous != entry.source_path:
                raise MaterializationError(
                    f"Conflito de destino {path}: {previous} | {entry.source_path}"
                )
            seen[path] = entry.source_path

    @staticmethod
    def _normalise_relative(value: str) -> str:
        path = PurePosixPath(value.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise MaterializationError(f"Caminho de destino inseguro: {value}")
        return path.as_posix()

    @classmethod
    def _safe_path(cls, root: Path, relative: str) -> Path:
        normalised = cls._normalise_relative(relative)
        target = (root / Path(*PurePosixPath(normalised).parts)).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise MaterializationError(f"Destino fora da raiz: {relative}") from exc
        return target

    @classmethod
    def _write_archive(
        cls,
        target: Path,
        entries: list[MaterializationEntry],
        *,
        overwrite: bool,
    ) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{target.stem}-", suffix=".tmp", dir=target.parent)
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                written: set[str] = set()
                for entry in entries:
                    member = cls._normalise_relative(entry.member_name or "")
                    if member in written:
                        continue
                    archive.write(entry.source_path, arcname=member)
                    written.add(member)
            if target.exists() and not overwrite:
                raise MaterializationError(f"Destino ja existe: {target}")
            os.replace(temporary, target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _copy_atomic(source: Path, target: Path) -> None:
        fd, temporary_name = tempfile.mkstemp(prefix=f".{target.stem}-", suffix=target.suffix, dir=target.parent)
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            shutil.copy2(source, temporary)
            os.replace(temporary, target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _report(
        callback: ProgressCallback | None,
        completed: int,
        total: int,
        entry: MaterializationEntry,
    ) -> None:
        if callback is not None:
            callback(completed, total, entry)


__all__ = ["ArcadeSetMaterializer", "MaterializationError"]
