"""Reconstrução auditável de sets MAME sem alterar as fontes."""
from __future__ import annotations

import json
import os
import shutil
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.core.models.scan_result import RomScanResult, ScanResult
from app.core.services.reconstruction_policy import (
    ReconstructionAction,
    RomDecision,
    classify_rom,
)


@dataclass(frozen=True)
class ReconstructionOptions:
    """Opções de construção do set de destino."""

    destination: Path
    layout: str = "single"  # single | split
    mode: str = "split"  # merged | non-merged | split
    overwrite: bool = False
    buffer_size: int = 4 * 1024 * 1024
    include_clones: bool = True
    include_bios: bool = True
    include_devices: bool = True
    include_samples: bool = True
    include_optional: bool = True
    source_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class _XmlRomMeta:
    status: str = "good"
    optional: bool = False
    bios: str = ""


@dataclass(frozen=True)
class _XmlMachineMeta:
    cloneof: str = ""
    romof: str = ""
    sampleof: str = ""
    is_bios: bool = False
    is_device: bool = False
    samples: tuple[str, ...] = ()
    roms: dict[str, _XmlRomMeta] | None = None


class ReconstructionService:
    """Constrói o máximo possível a partir de evidências físicas válidas.

    A origem é somente leitura. Cada decisão fica registrada no manifesto,
    inclusive o motivo exato para uma ROM ser mantida, ignorada ou bloqueada.
    """

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
        """Reconstrói o máximo possível e gera manifesto detalhado.

        ``good`` e ``baddump`` corretamente identificados são mantidos.
        ``nodump`` ausente e ROM opcional ausente não bloqueiam a construção.
        ROMs obrigatórias ausentes ou incorretas são registradas como
        bloqueadores, mas não impedem a criação das partes que podem funcionar.
        """
        self.options.destination.mkdir(parents=True, exist_ok=True)
        catalog = self._load_xml_catalog(result.xml_path)
        groups: dict[Path, list[tuple[str, RomScanResult]]] = {}
        decisions: list[dict] = []
        machine_summary: dict[str, dict] = {}

        for machine in result.machines:
            meta = catalog.get(machine.machine_name, _XmlMachineMeta())

            if meta.is_device and not self.options.include_devices:
                decisions.append({"machine": machine.machine_name, "item": "<machine>", "action": "ignore", "reason": "Device desabilitado nas opções de construção."})
                continue
            if meta.is_bios and not self.options.include_bios:
                decisions.append({"machine": machine.machine_name, "item": "<machine>", "action": "ignore", "reason": "Sistema BIOS desabilitado nas opções de construção."})
                continue
            if machine.cloneof and not self.options.include_clones:
                decisions.append({"machine": machine.machine_name, "item": "<machine>", "action": "ignore", "reason": "Clone desabilitado nas opções de construção."})
                continue

            archive_name = machine.cloneof or machine.machine_name if self.options.mode == "merged" else machine.machine_name
            entries: list[tuple[str, RomScanResult]] = []
            summary = machine_summary.setdefault(machine.machine_name, {"included": 0, "ignored": 0, "blocking": 0, "executable": True})

            for rom in machine.roms:
                if rom.item_type.value != "rom":
                    continue
                rom_meta = (meta.roms or {}).get(rom.rom_name, _XmlRomMeta())
                optional = bool(rom.optional or rom_meta.optional)

                if rom_meta.bios and not self.options.include_bios:
                    decisions.append({"machine": machine.machine_name, "item": rom.rom_name, "action": "ignore", "reason": "ROM marcada como BIOS no LISTXML e a opção de incluir BIOS está desativada."})
                    summary["ignored"] += 1
                    continue
                if optional and not self.options.include_optional:
                    decisions.append({"machine": machine.machine_name, "item": rom.rom_name, "action": "ignore", "reason": "ROM opcional removida pelas opções de construção."})
                    summary["ignored"] += 1
                    continue

                decision = self._decide_rom(rom, rom_meta)
                record = self._decision_record(machine.machine_name, rom, decision)
                decisions.append(record)

                if decision.action is ReconstructionAction.KEEP:
                    if self.options.mode == "split" and rom.merge:
                        record["reason"] += " No modo split, a ROM mergeada permanece somente no conjunto que a fornece."
                        summary["ignored"] += 1
                        continue
                    entries.append((rom.rom_name, rom))
                    summary["included"] += 1
                elif decision.blocking:
                    summary["blocking"] += 1
                    summary["executable"] = False
                else:
                    summary["ignored"] += 1

            if entries:
                target = self._target_path(Path(archive_name + ".zip"), "Roms")
                groups.setdefault(target, []).extend(entries)

        artifacts: list[dict] = []
        total = sum(len(items) for items in groups.values())
        completed = 0

        for target, entries in groups.items():
            if target.exists() and not self.options.overwrite:
                artifacts.append({"destination": str(target), "status": "already_exists", "entries": len(entries), "type": "romset"})
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
                artifacts.append({"destination": str(target), "status": "copied", "entries": len(written), "mode": self.options.mode, "type": "romset"})
            except Exception:
                partial.unlink(missing_ok=True)
                raise

        artifacts.extend(self._copy_samples(result, catalog, decisions))

        build_report = {
            "status": "completed",
            "runtime_ready_machines": sum(1 for value in machine_summary.values() if value["executable"]),
            "machines_with_blockers": sum(1 for value in machine_summary.values() if value["blocking"]),
            "machines": machine_summary,
            "decisions": decisions,
            "options": {
                "layout": self.options.layout,
                "mode": self.options.mode,
                "include_clones": self.options.include_clones,
                "include_bios": self.options.include_bios,
                "include_devices": self.options.include_devices,
                "include_samples": self.options.include_samples,
                "include_optional": self.options.include_optional,
            },
            "artifacts": artifacts,
        }

        manifest_path = self.options.destination / "reconstruction-manifest.json"
        partial = manifest_path.with_suffix(".json.partial")
        partial.write_text(json.dumps(build_report, indent=2, ensure_ascii=False), encoding="utf-8")
        with partial.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(partial, manifest_path)
        return manifest_path

    def missing_report(self, result: ScanResult) -> list[dict]:
        """Gera relatório por ROM com o motivo exato da decisão."""
        catalog = self._load_xml_catalog(result.xml_path)
        report: list[dict] = []
        for machine in result.machines:
            meta = catalog.get(machine.machine_name, _XmlMachineMeta())
            items: list[dict] = []
            blocking = 0
            runtime_ready = True
            for rom in machine.roms:
                if rom.item_type.value != "rom":
                    continue
                rom_meta = (meta.roms or {}).get(rom.rom_name, _XmlRomMeta())
                decision = self._decide_rom(rom, rom_meta)
                blocking += int(decision.blocking)
                runtime_ready = runtime_ready and decision.executable
                items.append({
                    "name": rom.rom_name,
                    "type": rom.item_type.value,
                    "physical_status": rom.status.value,
                    "mame_dump_status": decision.dump_status.value,
                    "action": decision.action.value,
                    "executable": decision.executable,
                    "blocking": decision.blocking,
                    "expected_size": rom.expected_size,
                    "actual_size": rom.actual_size,
                    "expected_crc": rom.expected_crc,
                    "actual_crc": rom.actual_crc,
                    "expected_sha1": rom.expected_sha1,
                    "actual_sha1": rom.actual_sha1,
                    "message": rom.message,
                    "reason": decision.reason,
                })
            report.append({"machine": machine.machine_name, "cloneof": machine.cloneof, "status": machine.status.value, "runtime_ready": runtime_ready, "blocking_count": blocking, "items": items})
        return report

    @staticmethod
    def _decide_rom(rom: RomScanResult, meta: _XmlRomMeta) -> RomDecision:
        """Aplica a política MAME a uma evidência física."""
        return classify_rom(
            physical_status=rom.status.value,
            expected_size=rom.expected_size,
            actual_size=rom.actual_size,
            expected_crc=rom.expected_crc,
            actual_crc=rom.actual_crc,
            expected_sha1=rom.expected_sha1,
            actual_sha1=rom.actual_sha1,
            mame_status=meta.status,
            optional=bool(rom.optional or meta.optional),
        )

    @staticmethod
    def _decision_record(machine_name: str, rom: RomScanResult, decision: RomDecision) -> dict:
        """Converte decisão em registro serializável."""
        return {
            "machine": machine_name,
            "item": rom.rom_name,
            "type": rom.item_type.value,
            "physical_status": rom.status.value,
            "mame_dump_status": decision.dump_status.value,
            "action": decision.action.value,
            "executable": decision.executable,
            "blocking": decision.blocking,
            "reason": decision.reason,
        }

    @staticmethod
    def _load_xml_catalog(xml_path: Path | None) -> dict[str, _XmlMachineMeta]:
        """Lê os metadados MAME necessários à reconstrução."""
        if xml_path is None or not Path(xml_path).is_file():
            return {}
        try:
            root = ET.parse(xml_path).getroot()
        except (OSError, ET.ParseError):
            return {}

        catalog: dict[str, _XmlMachineMeta] = {}
        for machine in root.findall("machine"):
            name = machine.get("name", "").strip()
            if not name:
                continue
            roms: dict[str, _XmlRomMeta] = {}
            for rom in machine.findall("rom"):
                rom_name = rom.get("name", "").strip()
                if rom_name:
                    roms[rom_name] = _XmlRomMeta(
                        status=rom.get("status", "good"),
                        optional=str(rom.get("optional", "")).lower() in {"yes", "true", "1"},
                        bios=rom.get("bios", "") or "",
                    )
            samples = tuple(value for value in (machine.get("sampleof", ""), *(sample.get("name", "") for sample in machine.findall("sample"))) if value)
            catalog[name] = _XmlMachineMeta(
                cloneof=machine.get("cloneof", "") or "",
                romof=machine.get("romof", "") or "",
                sampleof=machine.get("sampleof", "") or "",
                is_bios=str(machine.get("isbios", "")).lower() == "yes",
                is_device=str(machine.get("isdevice", "")).lower() == "yes",
                samples=tuple(dict.fromkeys(samples)),
                roms=roms,
            )
        return catalog

    def _copy_samples(self, result: ScanResult, catalog: dict[str, _XmlMachineMeta], decisions: list[dict]) -> list[dict]:
        """Copia sample sets ZIP para ``samples/`` quando habilitado."""
        if not self.options.include_samples:
            return []
        source_paths = tuple(Path(path).expanduser() for path in self.options.source_paths)
        if not source_paths:
            decisions.append({"item": "<samples>", "action": "ignore", "reason": "Samples habilitados, mas nenhuma origem foi informada em ReconstructionOptions.source_paths."})
            return []

        names: set[str] = set()
        for machine in result.machines:
            meta = catalog.get(machine.machine_name)
            if meta:
                names.update(meta.samples)

        target_root = self.options.destination / "samples"
        target_root.mkdir(parents=True, exist_ok=True)
        artifacts: list[dict] = []
        for name in sorted(n for n in names if n):
            candidates = [base / "samples" / f"{name}.zip" for base in source_paths]
            candidates.extend(base / f"{name}.zip" for base in source_paths)
            source = next((path for path in candidates if path.is_file()), None)
            target = target_root / f"{name}.zip"
            if source is None:
                decisions.append({"item": f"sample:{name}", "action": "search", "reason": f"Sample set {name}.zip não encontrado nas origens configuradas."})
                continue
            if target.exists() and not self.options.overwrite:
                artifacts.append({"destination": str(target), "status": "already_exists", "source": str(source), "type": "sample"})
                continue
            partial = target.with_name(target.name + ".partial")
            shutil.copyfile(source, partial)
            os.replace(partial, target)
            artifacts.append({"destination": str(target), "status": "copied", "source": str(source), "type": "sample"})
            decisions.append({"item": f"sample:{name}", "action": "keep", "reason": f"Sample set encontrado em {source} e copiado para o destino."})
        return artifacts

    def _target_path(self, source: Path, category: str) -> Path:
        root = self.options.destination / category if self.options.layout == "split" else self.options.destination
        return root / source.name

    def _write_rom(self, out: zipfile.ZipFile, member_name: str, rom: RomScanResult) -> None:
        """Copia uma ROM validada sem carregá-la inteira na memória."""
        if rom.archive_path is not None:
            with zipfile.ZipFile(rom.archive_path, "r") as archive:
                member = rom.archive_member
                if not member:
                    raise FileNotFoundError(f"Membro ZIP não informado para {rom.rom_name}")
                with archive.open(member, "r") as src, out.open(member_name, "w", force_zip64=True) as dst:
                    shutil.copyfileobj(src, dst, length=self.options.buffer_size)
        elif rom.path is not None and rom.path.is_file():
            with rom.path.open("rb") as src, out.open(member_name, "w", force_zip64=True) as dst:
                shutil.copyfileobj(src, dst, length=self.options.buffer_size)
        else:
            raise FileNotFoundError(f"Origem física não encontrada para {rom.rom_name}")
