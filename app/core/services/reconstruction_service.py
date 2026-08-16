"""Reconstrói sets ROM (Split/Non-merged/Merged) sem alterar as fontes."""
from __future__ import annotations

import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.core.models.scan_result import RomScanResult, ScanResult


@dataclass(frozen=True)
class ReconstructionOptions:
    destination: Path
    layout: str = "single"  # single | split
    mode: str = "split"     # merged | non-merged | split
    overwrite: bool = False
    buffer_size: int = 4 * 1024 * 1024


class ReconstructionService:
    """Copia, a partir de um ``ScanResult`` já validado, apenas os
    arquivos confirmados como corretos, para um destino separado. O
    FULLSET de origem nunca é modificado (SOURCE -> DESTINATION,
    nunca SOURCE -> SOURCE)."""

    VALID_LAYOUTS = {"single", "split"}
    VALID_MODES = {"merged", "non-merged", "split"}

    def __init__(self, options: ReconstructionOptions):
        if options.layout not in self.VALID_LAYOUTS:
            raise ValueError("layout deve ser 'single' ou 'split'")
        if options.mode not in self.VALID_MODES:
            raise ValueError("mode deve ser 'merged', 'non-merged' ou 'split'")
        self.options = options

    def reconstruct(
        self,
        result: ScanResult,
        *,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> Path:
        self.options.destination.mkdir(parents=True, exist_ok=True)

        groups: dict[Path, list[tuple[str, RomScanResult]]] = {}
        for machine in result.machines:
            archive_name = machine.machine_name
            if self.options.mode == "merged":
                archive_name = machine.cloneof or machine.machine_name

            entries: list[tuple[str, RomScanResult]] = []
            for rom in machine.roms:
                if rom.item_type.value != "rom" or not rom.valid:
                    continue
                if self.options.mode == "split" and rom.merge:
                    continue  # ROM compartilhada com o parent: fica só no parent
                entries.append((rom.rom_name, rom))

            if entries:
                target = self._target_path(Path(archive_name + ".zip"), "Roms")
                groups.setdefault(target, []).extend(entries)

        manifest: list[dict] = []
        total = sum(len(items) for items in groups.values())
        completed = 0

        for target, entries in groups.items():
            if target.exists() and not self.options.overwrite:
                manifest.append({"destination": str(target), "status": "already_exists", "entries": len(entries)})
                completed += len(entries)
                continue

            partial = target.with_name(target.name + ".partial")
            partial.parent.mkdir(parents=True, exist_ok=True)
            written: set[str] = set()
            try:
                with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as out:
                    for member_name, rom in entries:
                        if member_name in written:
                            continue
                        self._write_rom(out, member_name, rom)
                        written.add(member_name)
                        completed += 1
                        if progress_callback:
                            progress_callback(completed, total, f"{target.name}:{member_name}")
                os.replace(partial, target)
                manifest.append({
                    "destination": str(target), "status": "copied",
                    "entries": len(written), "mode": self.options.mode,
                })
            except Exception:
                partial.unlink(missing_ok=True)
                raise

        manifest_path = self.options.destination / "reconstruction-manifest.json"
        partial = manifest_path.with_suffix(".json.partial")
        partial.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        with partial.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(partial, manifest_path)
        return manifest_path

    def missing_report(self, result: ScanResult) -> list[dict]:
        """Relatório por máquina dos itens não reconstruídos (ausentes,
        inválidos ou com erro) — insumo para ``missing_roms.json`` /
        ``build_report.json``."""
        report = []
        for machine in result.problem_machines():
            report.append({
                "machine": machine.machine_name,
                "status": machine.status.value,
                "items": [
                    {
                        "name": rom.rom_name,
                        "type": rom.item_type.value,
                        "status": rom.status.value,
                        "expected_size": rom.expected_size,
                        "expected_crc": rom.expected_crc,
                        "expected_sha1": rom.expected_sha1,
                        "message": rom.message,
                    }
                    for rom in machine.roms if not rom.valid
                ],
            })
        return report

    def _target_path(self, source: Path, category: str) -> Path:
        root = self.options.destination / category if self.options.layout == "split" else self.options.destination
        return root / source.name

    def _write_rom(self, out: zipfile.ZipFile, member_name: str, rom: RomScanResult) -> None:
        if rom.archive_path is not None:
            with zipfile.ZipFile(rom.archive_path, "r") as archive:
                with archive.open(rom.source_member, "r") as src, out.open(member_name, "w", force_zip64=True) as dst:
                    shutil.copyfileobj(src, dst, length=self.options.buffer_size)
        elif rom.path is not None and rom.path.is_file():
            with rom.path.open("rb") as src, out.open(member_name, "w", force_zip64=True) as dst:
                shutil.copyfileobj(src, dst, length=self.options.buffer_size)
        else:
            raise FileNotFoundError(f"Origem física não encontrada para {rom.rom_name}")