"""Reconstrução auditável de sets MAME orientada pelo plano de build."""
from __future__ import annotations

import json
import os
import shutil
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.core.models.scan_result import RomScanResult, ScanResult
from app.core.services.mame_build_planner import MameBuildPlan, MameBuildPlanner
from app.core.services.mame_dependency_resolver import DependencyKind, DependencyOptions
from app.core.services.reconstruction_policy import (
    ReconstructionAction,
    RomDecision,
    classify_rom,
)


@dataclass(frozen=True)
class ReconstructionOptions:
    """Opções da construção física do set."""
    destination: Path
    layout: str = "single"
    mode: str = "split"
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
    merge: str = ""


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
    """Escreve somente o que o scan comprovou e o BuildPlanner determinou.

    O MameBuildPlanner é a autoridade estrutural para Split, Non-Merged e
    Merged. Este serviço resolve cada item planejado contra evidência física
    do ScanResult e grava os artefatos de forma atômica.
    """
    VALID_LAYOUTS = {"single", "split"}
    VALID_MODES = {"merged", "non-merged", "split"}

    def __init__(self, options: ReconstructionOptions):
        if options.layout not in self.VALID_LAYOUTS:
            raise ValueError("layout deve ser 'single' ou 'split'")
        if options.mode not in self.VALID_MODES:
            raise ValueError("mode deve ser 'merged', 'non-merged' ou 'split'")
        self.options = options

    def reconstruct(self, result: ScanResult, *, progress_callback: Callable[[int, int, str], None] | None = None) -> Path:
        """Monta o set seguindo integralmente o MameBuildPlan.

        O XML sozinho nunca autoriza uma escrita: cada ROM planejada precisa
        existir fisicamente no ScanResult e passar pela reconstruction_policy.
        Dependências estruturais ausentes permanecem como bloqueadores.
        """
        self.options.destination.mkdir(parents=True, exist_ok=True)
        catalog = self._load_xml_catalog(result.xml_path)
        build_plan = self._build_plan(result)
        decisions: list[dict] = []
        machine_summary = {m.machine_name: self._summary() for m in result.machines}
        physical = {
            (m.machine_name, r.rom_name): r
            for m in result.machines
            for r in m.roms
            if r.item_type.value == "rom"
        }
        groups: dict[Path, list[tuple[str, RomScanResult]]] = {}
        planned_keys: set[tuple[Path, str, str]] = set()

        # A chave inclui o ZIP de destino: no Non-Merged a mesma ROM do parent
        # deve ser materializada em cada clone autocontido.
        for archive_name, archive_items in build_plan.archives.archives.items():
            target = self._target_path(Path(f"{archive_name}.zip"), "Roms")
            for item in archive_items:
                key = (target, item.provider_machine, item.rom.name)
                if key in planned_keys:
                    continue
                planned_keys.add(key)
                rom = physical.get((item.provider_machine, item.rom.name))
                if rom is None:
                    self._missing_planned(decisions, machine_summary, item.provider_machine, item.rom.name,
                        f"ROM necessária para '{archive_name}.zip', fornecida por '{item.provider_machine}', não existe no ScanResult.")
                    continue
                meta = (catalog.get(item.provider_machine, _XmlMachineMeta()).roms or {}).get(
                    item.rom.name,
                    _XmlRomMeta(item.rom.status, item.rom.optional, item.rom.bios, item.rom.merge),
                )
                decision = self._decide_rom(rom, meta)
                record = self._decision_record(item.provider_machine, rom, decision)
                record.update({"archive": archive_name, "provider_machine": item.provider_machine, "planner_reason": item.reason})
                decisions.append(record)
                if decision.action is ReconstructionAction.KEEP:
                    groups.setdefault(target, []).append((rom.rom_name, rom))
                    self._inc(machine_summary, item.provider_machine, "included")
                elif decision.blocking:
                    self._block(machine_summary, item.provider_machine)
                else:
                    self._inc(machine_summary, item.provider_machine, "ignored")

        # BIOS/devices continuam como sets próprios; nunca são inseridos
        # arbitrariamente no ZIP do jogo.
        external_targets = {
            edge.target for edge in build_plan.dependencies.edges
            if edge.kind in {DependencyKind.BIOS, DependencyKind.DEVICE}
        }
        for machine_name in sorted(external_targets):
            machine_plan = build_plan.dependencies.machines.get(machine_name)
            if machine_plan is None:
                self._structural(decisions, machine_summary, machine_name, "Dependência externa não possui MachinePlan.")
                continue
            target = self._target_path(Path(f"{machine_name}.zip"), "Roms")
            for reason in machine_plan.blocking_reasons:
                self._structural(decisions, machine_summary, machine_name, reason)
            for romdef in machine_plan.own_roms:
                key = (target, machine_name, romdef.name)
                if key in planned_keys:
                    continue
                planned_keys.add(key)
                rom = physical.get((machine_name, romdef.name))
                if rom is None:
                    self._missing_planned(decisions, machine_summary, machine_name, romdef.name,
                        f"Dependência externa '{machine_name}.zip' requer '{romdef.name}', ausente no ScanResult.")
                    continue
                meta = (catalog.get(machine_name, _XmlMachineMeta()).roms or {}).get(
                    romdef.name, _XmlRomMeta(romdef.status, romdef.optional, romdef.bios, romdef.merge)
                )
                decision = self._decide_rom(rom, meta)
                record = self._decision_record(machine_name, rom, decision)
                record.update({"archive": machine_name, "provider_machine": machine_name, "planner_reason": "dependência externa BIOS/device"})
                decisions.append(record)
                if decision.action is ReconstructionAction.KEEP:
                    groups.setdefault(target, []).append((rom.rom_name, rom))
                    self._inc(machine_summary, machine_name, "included")
                elif decision.blocking:
                    self._block(machine_summary, machine_name)
                else:
                    self._inc(machine_summary, machine_name, "ignored")

        for reason in build_plan.blockers:
            decisions.append({"item": "<dependency>", "action": "block", "blocking": True, "executable": False, "reason": reason})

        artifacts: list[dict] = []
        total = sum(len(v) for v in groups.values())
        completed = 0
        for target, entries in groups.items():
            if target.exists() and not self.options.overwrite:
                artifacts.append({"destination": str(target), "status": "already_exists", "entries": len(entries), "type": "romset", "mode": self.options.mode})
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

        artifacts.extend(self._copy_samples(decisions, build_plan))
        report = {
            "status": "completed_with_blockers" if build_plan.blockers or any(v["blocking"] for v in machine_summary.values()) else "completed",
            "runtime_ready_machines": sum(v["executable"] for v in machine_summary.values()),
            "machines_with_blockers": sum(bool(v["blocking"]) for v in machine_summary.values()),
            "machines": machine_summary,
            "dependency_plan": {
                "requested": build_plan.dependencies.requested,
                "runtime_ready": build_plan.runtime_ready,
                "edges": [{"source": e.source, "target": e.target, "kind": e.kind.value, "reason": e.reason, "blocking": e.blocking} for e in build_plan.dependencies.edges],
                "blockers": build_plan.blockers,
            },
            "decisions": decisions,
            "options": self._options_dict(),
            "artifacts": artifacts,
        }
        return self._write_manifest(report)

    def missing_report(self, result: ScanResult) -> list[dict]:
        """Gera diagnóstico físico detalhado por ROM."""
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
                decision = self._decide_rom(rom, (meta.roms or {}).get(rom.rom_name, _XmlRomMeta()))
                blocking += int(decision.blocking)
                runtime_ready = runtime_ready and decision.executable
                items.append({"name": rom.rom_name, "type": rom.item_type.value,
                              "physical_status": rom.status.value, "mame_dump_status": decision.dump_status.value,
                              "action": decision.action.value, "executable": decision.executable, "blocking": decision.blocking,
                              "expected_size": rom.expected_size, "actual_size": rom.actual_size,
                              "expected_crc": rom.expected_crc, "actual_crc": rom.actual_crc,
                              "expected_sha1": rom.expected_sha1, "actual_sha1": rom.actual_sha1,
                              "message": rom.message, "reason": decision.reason})
            report.append({"machine": machine.machine_name, "cloneof": machine.cloneof,
                           "status": machine.status.value, "runtime_ready": runtime_ready,
                           "blocking_count": blocking, "items": items})
        return report

    def _build_plan(self, result: ScanResult) -> MameBuildPlan:
        """Cria o BuildPlan usando exatamente as opções da reconstrução."""
        if result.xml_path is None:
            raise ValueError("ScanResult não possui xml_path; o BuildPlanner precisa do LISTXML")
        options = DependencyOptions(include_clones=self.options.include_clones,
                                    include_bios=self.options.include_bios,
                                    include_devices=self.options.include_devices,
                                    include_samples=self.options.include_samples,
                                    include_optional=self.options.include_optional)
        return MameBuildPlanner(result.xml_path, options).plan(
            [machine.machine_name for machine in result.machines], mode=self.options.mode)

    @staticmethod
    def _decide_rom(rom: RomScanResult, meta: _XmlRomMeta) -> RomDecision:
        return classify_rom(physical_status=rom.status.value,
                            expected_size=rom.expected_size, actual_size=rom.actual_size,
                            expected_crc=rom.expected_crc, actual_crc=rom.actual_crc,
                            expected_sha1=rom.expected_sha1, actual_sha1=rom.actual_sha1,
                            mame_status=meta.status,
                            optional=bool(rom.optional or meta.optional))

    @staticmethod
    def _decision_record(machine_name: str, rom: RomScanResult, decision: RomDecision) -> dict:
        return {"machine": machine_name, "item": rom.rom_name, "type": rom.item_type.value,
                "physical_status": rom.status.value, "mame_dump_status": decision.dump_status.value,
                "action": decision.action.value, "executable": decision.executable,
                "blocking": decision.blocking, "reason": decision.reason}

    @staticmethod
    def _load_xml_catalog(xml_path: Path | None) -> dict[str, _XmlMachineMeta]:
        """Carrega metadados MAME usados no diagnóstico e validação."""
        if xml_path is None or not Path(xml_path).is_file():
            return {}
        try:
            root = ET.parse(xml_path).getroot()
        except (OSError, ET.ParseError):
            return {}
        elements = list(root.findall("machine")) or ([root] if root.tag == "machine" else [])
        catalog: dict[str, _XmlMachineMeta] = {}
        for machine in elements:
            name = (machine.get("name") or "").strip()
            if not name:
                continue
            roms: dict[str, _XmlRomMeta] = {}
            for node in machine.findall("rom"):
                rom_name = (node.get("name") or "").strip()
                if rom_name:
                    roms[rom_name] = _XmlRomMeta(status=(node.get("status") or "good").lower(),
                                                   optional=str(node.get("optional") or "").lower() in {"yes", "true", "1"},
                                                   bios=node.get("bios") or "", merge=node.get("merge") or "")
            samples = tuple(v for v in ((machine.get("sampleof") or ""),
                                        *(n.get("name") or "" for n in machine.findall("sample"))) if v)
            catalog[name] = _XmlMachineMeta(cloneof=machine.get("cloneof") or "",
                                             romof=machine.get("romof") or "",
                                             sampleof=machine.get("sampleof") or "",
                                             is_bios=str(machine.get("isbios") or "").lower() == "yes",
                                             is_device=str(machine.get("isdevice") or "").lower() == "yes",
                                             samples=tuple(dict.fromkeys(samples)), roms=roms)
        return catalog

    def _copy_samples(self, decisions: list[dict], build_plan: MameBuildPlan) -> list[dict]:
        """Copia apenas samples requeridos pelo BuildPlan."""
        if not self.options.include_samples or not build_plan.samples:
            return []
        sources = tuple(Path(p).expanduser() for p in self.options.source_paths)
        if not sources:
            decisions.append({"item": "<samples>", "action": "search", "blocking": False,
                              "executable": True, "reason": "Samples requeridos, mas nenhuma origem foi configurada."})
            return []
        target_root = self.options.destination / "samples"
        target_root.mkdir(parents=True, exist_ok=True)
        artifacts: list[dict] = []
        for name in sorted(build_plan.samples):
            candidates = [base / "samples" / f"{name}.zip" for base in sources] + [base / f"{name}.zip" for base in sources]
            source = next((p for p in candidates if p.is_file()), None)
            target = target_root / f"{name}.zip"
            if source is None:
                decisions.append({"item": f"sample:{name}", "action": "search", "blocking": False,
                                  "executable": True, "reason": f"Sample set {name}.zip não encontrado nas origens configuradas."})
                continue
            if target.exists() and not self.options.overwrite:
                artifacts.append({"destination": str(target), "status": "already_exists", "source": str(source), "type": "sample"})
                continue
            partial = target.with_name(target.name + ".partial")
            shutil.copyfile(source, partial)
            os.replace(partial, target)
            artifacts.append({"destination": str(target), "status": "copied", "source": str(source), "type": "sample"})
            decisions.append({"item": f"sample:{name}", "action": "keep", "blocking": False,
                              "executable": True, "reason": f"Sample set encontrado em {source} e copiado para o destino."})
        return artifacts

    def _target_path(self, source: Path, category: str) -> Path:
        root = self.options.destination / category if self.options.layout == "split" else self.options.destination
        return root / source.name

    def _write_rom(self, out: zipfile.ZipFile, member_name: str, rom: RomScanResult) -> None:
        """Copia a ROM em streaming, sem carregá-la inteira na memória."""
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

    @staticmethod
    def _summary() -> dict:
        return {"included": 0, "ignored": 0, "blocking": 0, "executable": True}

    @staticmethod
    def _inc(summary: dict[str, dict], machine: str, field: str) -> None:
        summary.setdefault(machine, ReconstructionService._summary())[field] += 1

    @staticmethod
    def _block(summary: dict[str, dict], machine: str) -> None:
        value = summary.setdefault(machine, ReconstructionService._summary())
        value["blocking"] += 1
        value["executable"] = False

    @staticmethod
    def _missing_planned(decisions: list[dict], summary: dict[str, dict], machine: str, item: str, reason: str) -> None:
        decisions.append({"machine": machine, "item": item, "action": "search", "blocking": True,
                          "executable": False, "reason": reason})
        ReconstructionService._block(summary, machine)

    @staticmethod
    def _structural(decisions: list[dict], summary: dict[str, dict], machine: str, reason: str) -> None:
        decisions.append({"machine": machine, "item": "<dependency>", "action": "block", "blocking": True,
                          "executable": False, "reason": reason})
        ReconstructionService._block(summary, machine)

    def _options_dict(self) -> dict:
        return {"layout": self.options.layout, "mode": self.options.mode, "overwrite": self.options.overwrite,
                "include_clones": self.options.include_clones, "include_bios": self.options.include_bios,
                "include_devices": self.options.include_devices, "include_samples": self.options.include_samples,
                "include_optional": self.options.include_optional}

    def _write_manifest(self, report: dict) -> Path:
        manifest_path = self.options.destination / "reconstruction-manifest.json"
        partial = manifest_path.with_suffix(".json.partial")
        partial.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        with partial.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(partial, manifest_path)
        return manifest_path
