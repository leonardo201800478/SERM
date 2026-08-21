"""Reconstrução multi-emulador baseada no manifesto físico."""
from __future__ import annotations

import json
import os
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.core.services.mame_build_planner import MameBuildPlanner
from app.core.services.mame_dependency_resolver import DependencyKind, DependencyOptions
from app.core.services.reconstruction_profiles import ReconstructionProfile, ReconstructionTarget, classify_xml
from app.mame.mame_aware_reconstruction_engine import MameAwareReconstructionEngine, MameBuildOptions
from app.mame.reconstruction_engine import ReconstructionEngine, ReconstructionMachine, ReconstructionResult

ProgressCallback = Callable[[int, int, str], None]
LogCallback = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class MultiEmulatorOptions:
    """Opções do construtor multi-emulador."""
    profile: ReconstructionTarget = ReconstructionTarget.MAME
    set_type: str = ReconstructionEngine.SET_SPLIT
    copy_perfect: bool = True
    repair: bool = True
    include_clones: bool = True
    include_bios: bool = True
    include_devices: bool = True
    include_samples: bool = True
    include_optional: bool = True


@dataclass(slots=True)
class MultiEmulatorResult:
    """Resultado agregado por destino."""
    targets: dict[str, ReconstructionResult]
    artifacts: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    manifest_path: Path


class MultiEmulatorReconstructionService:
    """Orquestra a reconstrução sem alterar o motor físico existente."""

    def __init__(self, source_paths: list[str | Path], destination: str | Path, *, xml_path: str | Path,
                 options: MultiEmulatorOptions | None = None,
                 progress_callback: ProgressCallback | None = None,
                 log_callback: LogCallback | None = None) -> None:
        self.source_paths = [Path(p).expanduser().resolve() for p in source_paths]
        self.destination = Path(destination).expanduser().resolve()
        self.xml_path = Path(xml_path).expanduser().resolve()
        self.options = options or MultiEmulatorOptions()
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self._cancel_requested = False
        self.profile = ReconstructionProfile(target=self.options.profile)

    def request_cancel(self) -> None:
        """Solicita cancelamento cooperativo."""
        self._cancel_requested = True

    def reconstruct_manifest(self, manifest: str | Path) -> MultiEmulatorResult:
        """Carrega o manifesto atual e inicia a reconstrução sem novo scan."""
        return self.reconstruct(ReconstructionEngine.load_manifest(manifest))

    def reconstruct(self, machines: list[ReconstructionMachine]) -> MultiEmulatorResult:
        """Reconstrói o perfil selecionado e publica um relatório agregado."""
        self.destination.mkdir(parents=True, exist_ok=True)
        xml_root = ET.parse(self.xml_path).getroot()
        classification = classify_xml(self.xml_path)
        support_names = {
            m.get("name", "") for m in xml_root.findall("machine")
            if m.get("name") and (m.get("isbios") == "yes" or m.get("isdevice") == "yes")
        }
        support_pool = {m.name: m for m in machines if m.name in support_names}
        game_groups = self._build_game_groups(machines, classification, support_names)

        if self.options.profile is ReconstructionTarget.MAME:
            selected = {ReconstructionTarget.MAME: game_groups[ReconstructionTarget.MAME]}
        elif self.options.profile is ReconstructionTarget.SUPERMODEL3:
            selected = {ReconstructionTarget.SUPERMODEL3: game_groups[ReconstructionTarget.SUPERMODEL3]}
        elif self.options.profile is ReconstructionTarget.FLYCAST:
            selected = {ReconstructionTarget.FLYCAST: game_groups[ReconstructionTarget.FLYCAST]}
        else:
            selected = game_groups

        targets: dict[str, ReconstructionResult] = {}
        artifacts: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []

        for target in (ReconstructionTarget.MAME, ReconstructionTarget.SUPERMODEL3, ReconstructionTarget.FLYCAST):
            group = selected.get(target, [])
            if not group:
                continue
            self._check_cancel()
            result, group_artifacts, group_decisions = self._run_game_target(target, group)
            targets[target.value] = result
            artifacts.extend(group_artifacts)
            decisions.extend(group_decisions)

        if self.options.profile in {ReconstructionTarget.MULTI, ReconstructionTarget.MAME}:
            support = self._build_support_groups(selected, support_pool)
            for kind, support_machines in support.items():
                if not support_machines:
                    continue
                self._check_cancel()
                result, group_artifacts, group_decisions = self._run_support_target(kind, support_machines)
                targets[f"support:{kind}"] = result
                artifacts.extend(group_artifacts)
                decisions.extend(group_decisions)

            if self.options.include_samples:
                artifacts.extend(self._copy_samples(machines))
            artifacts.append(self._write_path_hints())

        report = {
            "schema_version": 1,
            "profile": self.options.profile.value,
            "set_type": self.options.set_type,
            "destination": str(self.destination),
            "targets": {
                name: {
                    "copied": r.copied, "repaired": r.repaired, "failed": r.failed,
                    "external": r.external, "skipped": r.skipped,
                    "roms_verified": r.roms_verified, "chds_verified": r.chds_verified,
                    "chds_copied": r.chds_copied, "chds_skipped": r.chds_skipped,
                    "unresolved": r.unresolved,
                } for name, r in targets.items()
            },
            "artifacts": artifacts,
            "decisions": decisions,
        }
        report_path = self.destination / "multi-emulator-reconstruction.json"
        partial = report_path.with_suffix(".json.partial")
        partial.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(partial, report_path)
        return MultiEmulatorResult(targets, artifacts, decisions, report_path)

    @staticmethod
    def _build_game_groups(machines: list[ReconstructionMachine], classification: dict[str, ReconstructionTarget],
                           support_names: set[str]) -> dict[ReconstructionTarget, list[ReconstructionMachine]]:
        """Agrupa somente machines executáveis; BIOS/devices nunca viram jogos."""
        groups = {ReconstructionTarget.MAME: [], ReconstructionTarget.SUPERMODEL3: [], ReconstructionTarget.FLYCAST: []}
        for machine in machines:
            if machine.name in support_names:
                continue
            groups[classification.get(machine.name, ReconstructionTarget.MAME)].append(machine)
        return groups

    def _run_game_target(self, target: ReconstructionTarget, machines: list[ReconstructionMachine]):
        """Reconstrói ROMs/CHDs do destino sem misturar BIOS/devices."""
        destination = self.profile.destination_for(self.destination, target)
        destination.mkdir(parents=True, exist_ok=True)
        engine = MameAwareReconstructionEngine(
            self.source_paths, destination,
            build_options=MameBuildOptions(
                include_clones=self.options.include_clones,
                include_bios=False, include_devices=False, include_samples=False,
                include_optional=self.options.include_optional,
            ),
            xml_path=self.xml_path, progress_callback=self.progress_callback, log_callback=self.log_callback,
        )
        result = engine.reconstruct(machines, set_type=self.options.set_type,
                                    copy_perfect=self.options.copy_perfect, repair=self.options.repair)
        return result, [{"type": "rom_target", "target": target.value, "destination": str(destination)}], list(engine.decisions)

    def _build_support_groups(self, selected: dict[ReconstructionTarget, list[ReconstructionMachine]], support_pool: dict[str, ReconstructionMachine]):
        """Usa o BuildPlanner para descobrir exatamente BIOS/devices requeridos."""
        selected_names = [m.name for group in selected.values() for m in group]
        if not selected_names:
            return {"bios": [], "devices": []}
        options = DependencyOptions(
            include_clones=self.options.include_clones,
            include_bios=self.options.include_bios,
            include_devices=self.options.include_devices,
            include_samples=False,
            include_optional=self.options.include_optional,
        )
        plan = MameBuildPlanner(self.xml_path, options).plan(selected_names, mode=self.options.set_type)
        wanted = {"bios": set(), "devices": set()}
        for edge in plan.dependencies.edges:
            if edge.kind is DependencyKind.BIOS and self.options.include_bios:
                wanted["bios"].add(edge.target)
            elif edge.kind is DependencyKind.DEVICE and self.options.include_devices:
                wanted["devices"].add(edge.target)
        return {kind: [support_pool[name] for name in sorted(names) if name in support_pool]
                for kind, names in wanted.items()}

    def _run_support_target(self, kind: str, machines: list[ReconstructionMachine]):
        """Publica BIOS/devices em ZIPs independentes."""
        destination = self.destination / kind
        destination.mkdir(parents=True, exist_ok=True)
        engine = MameAwareReconstructionEngine(
            self.source_paths, destination,
            build_options=MameBuildOptions(
                include_clones=False, include_bios=True, include_devices=True,
                include_samples=False, include_optional=self.options.include_optional,
            ),
            xml_path=self.xml_path, progress_callback=self.progress_callback, log_callback=self.log_callback,
        )
        result = engine.reconstruct(machines, set_type=ReconstructionEngine.SET_NON_MERGED,
                                    copy_perfect=self.options.copy_perfect, repair=self.options.repair)
        return result, [{"type": kind, "destination": str(destination)}], list(engine.decisions)

    def _copy_samples(self, machines: list[ReconstructionMachine]) -> list[dict[str, Any]]:
        """Copia uma única instância de cada sample set requerido."""
        root = ET.parse(self.xml_path).getroot()
        names = {m.name for m in machines}
        wanted: set[str] = set()
        for machine in root.findall("machine"):
            if machine.get("name") not in names:
                continue
            if machine.get("sampleof"):
                wanted.add(machine.get("sampleof", ""))
            wanted.update(n.get("name", "") for n in machine.findall("sample") if n.get("name"))
        target_root = self.destination / self.profile.samples_dir
        target_root.mkdir(parents=True, exist_ok=True)
        artifacts: list[dict[str, Any]] = []
        for name in sorted(wanted):
            candidates = [base / "samples" / f"{name}.zip" for base in self.source_paths]
            candidates += [base / f"{name}.zip" for base in self.source_paths]
            source = next((p for p in candidates if p.is_file()), None)
            target = target_root / f"{name}.zip"
            if source is None:
                artifacts.append({"type": "sample", "name": name, "status": "missing"})
                continue
            if target.exists():
                artifacts.append({"type": "sample", "name": name, "status": "already_exists", "destination": str(target)})
                continue
            partial = target.with_name(target.name + ".partial")
            shutil.copy2(source, partial)
            os.replace(partial, target)
            artifacts.append({"type": "sample", "name": name, "status": "copied", "destination": str(target)})
        return artifacts

    def _write_path_hints(self) -> dict[str, Any]:
        """Registra os paths que devem ser configurados nos emuladores/frontends."""
        path = self.destination / self.profile.systems_dir / "mame-set-builder-paths.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "mame_rompath": [str(self.destination / self.profile.mame_dir), str(self.destination / self.profile.bios_dir), str(self.destination / self.profile.devices_dir)],
            "mame_samplepath": [str(self.destination / self.profile.samples_dir)],
            "flycast_contentpath": str(self.destination / "flycast" / "roms"),
            "flycast_biospath": str(self.destination / self.profile.systems_dir / "flycast"),
            "supermodel_rompath": str(self.destination / self.profile.supermodel3_dir),
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"type": "path_hints", "destination": str(path)}

    def _check_cancel(self) -> None:
        if self._cancel_requested:
            raise InterruptedError("Reconstrução multi-emulador cancelada pelo usuário.")
