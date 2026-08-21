"""Reconstrução multi-emulador baseada no manifesto físico.

Perfis suportados:

* MAME: mantém as machines comuns em ``roms/``;
* Supermodel 3: envia machines do driver Model 3 para ``supermodel3/roms``;
* Flycast: envia NAOMI/NAOMI2 para ``flycast/roms`` e mantém os CHDs no
  subdiretório da machine, no formato aceito pelo Flycast.

BIOS, devices e samples são publicados separadamente. O serviço nunca faz
novo scan e nunca procura uma fonte fora das localizações registradas no
manifesto.
"""
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
from app.core.services.reconstruction_profiles import (
    ReconstructionProfile,
    ReconstructionTarget,
    classify_xml,
)
from app.mame.mame_aware_reconstruction_engine import (
    MameAwareReconstructionEngine,
    MameBuildOptions,
)
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

    def __init__(
        self,
        source_paths: list[str | Path],
        destination: str | Path,
        *,
        xml_path: str | Path,
        options: MultiEmulatorOptions | None = None,
        progress_callback: ProgressCallback | None = None,
        log_callback: LogCallback | None = None,
    ) -> None:
        self.source_paths = [Path(p).expanduser().resolve() for p in source_paths]
        self.destination = Path(destination).expanduser().resolve()
        self.xml_path = Path(xml_path).expanduser().resolve()
        self.options = options or MultiEmulatorOptions()
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self._cancel_requested = False
        self.profile = ReconstructionProfile(target=self.options.profile)

    def request_cancel(self) -> None:
        """Solicita cancelamento do processo atual."""
        self._cancel_requested = True

    def reconstruct_manifest(self, manifest: str | Path) -> MultiEmulatorResult:
        """Reconstrói um manifesto físico usando o perfil selecionado."""
        machines = ReconstructionEngine.load_manifest(manifest)
        return self.reconstruct(machines)

    def reconstruct(self, machines: list[ReconstructionMachine]) -> MultiEmulatorResult:
        """Executa a reconstrução por destino e publica o relatório final."""
        self.destination.mkdir(parents=True, exist_ok=True)
        classification = classify_xml(self.xml_path)
        groups = self._build_groups(machines, classification)

        targets: dict[str, ReconstructionResult] = {}
        artifacts: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []

        if self.options.profile is ReconstructionTarget.MAME:
            groups = {ReconstructionTarget.MAME: machines}
        elif self.options.profile is ReconstructionTarget.SUPERMODEL3:
            groups = {ReconstructionTarget.SUPERMODEL3: groups[ReconstructionTarget.SUPERMODEL3]}
        elif self.options.profile is ReconstructionTarget.FLYCAST:
            groups = {ReconstructionTarget.FLYCAST: groups[ReconstructionTarget.FLYCAST]}

        for target in (
            ReconstructionTarget.MAME,
            ReconstructionTarget.SUPERMODEL3,
            ReconstructionTarget.FLYCAST,
        ):
            if target not in groups or not groups[target]:
                continue
            self._check_cancel()
            result, target_artifacts, target_decisions = self._run_game_target(target, groups[target])
            targets[target.value] = result
            artifacts.extend(target_artifacts)
            decisions.extend(target_decisions)

        if self.options.profile in {ReconstructionTarget.MULTI, ReconstructionTarget.MAME}:
            support = self._build_support_groups(groups, classification)
            for support_kind, support_machines in support.items():
                if not support_machines:
                    continue
                self._check_cancel()
                result, support_artifacts, support_decisions = self._run_support_target(support_kind, support_machines)
                targets[f"support:{support_kind}"] = result
                artifacts.extend(support_artifacts)
                decisions.extend(support_decisions)

        if self.options.include_samples and self.options.profile in {ReconstructionTarget.MULTI, ReconstructionTarget.MAME}:
            artifacts.extend(self._copy_samples(machines))

        if self.options.profile in {ReconstructionTarget.MULTI, ReconstructionTarget.MAME}:
            artifacts.append(self._write_path_hints())

        report = {
            "schema_version": 1,
            "profile": self.options.profile.value,
            "set_type": self.options.set_type,
            "destination": str(self.destination),
            "targets": {
                name: {
                    "copied": result.copied,
                    "repaired": result.repaired,
                    "failed": result.failed,
                    "external": result.external,
                    "skipped": result.skipped,
                    "roms_verified": result.roms_verified,
                    "chds_verified": result.chds_verified,
                    "chds_copied": result.chds_copied,
                    "chds_skipped": result.chds_skipped,
                    "unresolved": result.unresolved,
                }
                for name, result in targets.items()
            },
            "artifacts": artifacts,
            "decisions": decisions,
        }
        report_path = self.destination / "multi-emulator-reconstruction.json"
        partial = report_path.with_suffix(".json.partial")
        partial.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(partial, report_path)

        return MultiEmulatorResult(
            targets=targets,
            artifacts=artifacts,
            decisions=decisions,
            manifest_path=report_path,
        )

    def _build_groups(
        self,
        machines: list[ReconstructionMachine],
        classification: dict[str, ReconstructionTarget],
    ) -> dict[ReconstructionTarget, list[ReconstructionMachine]]:
        """Agrupa somente machines executáveis; BIOS/devices ficam em suporte."""
        groups = {
            ReconstructionTarget.MAME: [],
            ReconstructionTarget.SUPERMODEL3: [],
            ReconstructionTarget.FLYCAST: [],
        }
        for machine in machines:
            target = classification.get(machine.name, ReconstructionTarget.MAME)
            groups[target].append(machine)
        return groups

    def _run_game_target(
        self,
        target: ReconstructionTarget,
        machines: list[ReconstructionMachine],
    ) -> tuple[ReconstructionResult, list[dict[str, Any]], list[dict[str, Any]]]:
        """Executa um grupo de jogos sem misturar BIOS/devices ao destino."""
        destination = self.profile.destination_for(self.destination, target)
        destination.mkdir(parents=True, exist_ok=True)
        engine = MameAwareReconstructionEngine(
            self.source_paths,
            destination,
            build_options=MameBuildOptions(
                include_clones=self.options.include_clones,
                include_bios=False,
                include_devices=False,
                include_samples=False,
                include_optional=self.options.include_optional,
            ),
            xml_path=self.xml_path,
            progress_callback=self.progress_callback,
            log_callback=self.log_callback,
        )
        result = engine.reconstruct(
            machines,
            set_type=self.options.set_type,
            copy_perfect=self.options.copy_perfect,
            repair=self.options.repair,
        )
        return result, [
            {"type": "rom_target", "target": target.value, "destination": str(destination)}
        ], list(engine.decisions)

    def _build_support_groups(
        self,
        groups: dict[ReconstructionTarget, list[ReconstructionMachine]],
        classification: dict[str, ReconstructionTarget],
    ) -> dict[str, list[ReconstructionMachine]]:
        """Resolve BIOS/devices necessários pelos grupos de jogos."""
        selected_names = [m.name for machines in groups.values() for m in machines]
        if not selected_names:
            return {"bios": [], "devices": []}
        options = DependencyOptions(
            include_clones=self.options.include_clones,
            include_bios=self.options.include_bios,
            include_devices=self.options.include_devices,
            include_samples=False,
            include_optional=self.options.include_optional,
        )
        plan = __import__("app.core.services.mame_build_planner", fromlist=["MameBuildPlanner"]).MameBuildPlanner(self.xml_path, options).plan(selected_names, mode=self.options.set_type)
        wanted: dict[str, set[str]] = {"bios": set(), "devices": set()}
        for edge in plan.dependencies.edges:
            if edge.kind is DependencyKind.BIOS and self.options.include_bios:
                wanted["bios"].add(edge.target)
            elif edge.kind is DependencyKind.DEVICE and self.options.include_devices:
                wanted["devices"].add(edge.target)

        by_name = {machine.name: machine for machines in groups.values() for machine in machines}
        # O manifesto normalmente contém os próprios BIOS/devices; quando um
        # arquivo foi filtrado para fora do XML de jogos, o dependency planner
        # ainda informa o shortname, mas não inventamos um registro físico.
        all_machines = ReconstructionEngine.load_manifest(self._current_manifest_from_machine_list()) if False else []
        # A lista física disponível é reconstruída a partir do argumento atual
        # em _run_support_target; preenchida por _support_machine_map no chamador.
        return {"bios": [by_name[name] for name in wanted["bios"] if name in by_name],
                "devices": [by_name[name] for name in wanted["devices"] if name in by_name]}

    def _run_support_target(
        self,
        support_kind: str,
        machines: list[ReconstructionMachine],
    ) -> tuple[ReconstructionResult, list[dict[str, Any]], list[dict[str, Any]]]:
        """Publica BIOS/devices em diretórios independentes."""
        destination = self.destination / support_kind
        destination.mkdir(parents=True, exist_ok=True)
        engine = MameAwareReconstructionEngine(
            self.source_paths,
            destination,
            build_options=MameBuildOptions(
                include_clones=False,
                include_bios=True,
                include_devices=True,
                include_samples=False,
                include_optional=self.options.include_optional,
            ),
            xml_path=self.xml_path,
            progress_callback=self.progress_callback,
            log_callback=self.log_callback,
        )
        result = engine.reconstruct(
            machines,
            set_type=ReconstructionEngine.SET_NON_MERGED,
            copy_perfect=self.options.copy_perfect,
            repair=self.options.repair,
        )
        return result, [{"type": support_kind, "destination": str(destination)}], list(engine.decisions)

    def _copy_samples(self, machines: list[ReconstructionMachine]) -> list[dict[str, Any]]:
        """Copia samples uma única vez para o diretório comum."""
        root = ET.parse(self.xml_path).getroot()
        wanted: set[str] = set()
        names = {m.name for m in machines}
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
            source = next((base / "samples" / f"{name}.zip" for base in self.source_paths if (base / "samples" / f"{name}.zip").is_file()), None)
            if source is None:
                source = next((base / f"{name}.zip" for base in self.source_paths if (base / f"{name}.zip").is_file()), None)
            if source is None:
                artifacts.append({"type": "sample", "name": name, "status": "missing"})
                continue
            target = target_root / f"{name}.zip"
            if target.exists():
                artifacts.append({"type": "sample", "name": name, "status": "already_exists", "destination": str(target)})
                continue
            partial = target.with_name(target.name + ".partial")
            shutil.copy2(source, partial)
            os.replace(partial, target)
            artifacts.append({"type": "sample", "name": name, "status": "copied", "destination": str(target)})
        return artifacts

    def _write_path_hints(self) -> dict[str, Any]:
        """Cria um arquivo de orientação para configurar MAME/Flycast/Supermodel."""
        path = self.destination / "systems" / "mame-set-builder-paths.json"
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

    def _current_manifest_from_machine_list(self):
        """Placeholder nunca executado; mantém tipagem sem acessar o HDD."""
        raise RuntimeError("manifesto não disponível neste contexto")
