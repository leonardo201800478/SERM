"""Integração da resolução de dependências com o resultado do scanner.

Este módulo é a ponte entre o ``ScanResult`` físico e o plano MAME-aware.
Ele não recalcula CRC/SHA-1 e não toca nas fontes. Apenas expande, quando o
modo exige, ROMs herdadas de parent/merge e registra dependências externas
(BIOS/devices/samples) que precisam estar disponíveis para execução.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

from app.core.models.scan_result import MachineScanResult, RomScanResult, ScanResult
from app.core.services.mame_dependency_resolver import (
    DependencyOptions,
    DependencyPlan,
    MameDependencyResolver,
)


@dataclass(frozen=True, slots=True)
class PreparedReconstruction:
    """Resultado da preparação de um scan para a etapa de construção."""

    scan: ScanResult
    plan: DependencyPlan


class DependencyAwareReconstruction:
    """Prepara o scan segundo a árvore real de dependências do MAME."""

    def __init__(self, xml_path: str | Path, options: DependencyOptions | None = None):
        self.resolver = MameDependencyResolver(xml_path, options)
        self.options = options or DependencyOptions()

    def prepare(self, result: ScanResult, mode: str = "split") -> PreparedReconstruction:
        """Resolve dependências e devolve um scan expandido, sem alterar o original.

        Regras:
        - Split: cada clone mantém somente suas ROMs próprias; o parent é um
          artefato separado e precisa estar presente no set final.
        - Non-Merged: ROMs herdadas do parent/merge são materializadas no clone.
        - Merged: ROMs herdadas são materializadas no arquivo lógico do clone,
          enquanto o provider continua registrado como dependência.
        - BIOS/devices não são copiados para dentro do ZIP do jogo; são sets
          externos e precisam estar disponíveis como dependências.
        """
        machine_names = [machine.machine_name for machine in result.machines]
        plan = self.resolver.resolve(machine_names, mode=mode)
        source = {machine.machine_name: machine for machine in result.machines}
        prepared_machines: list[MachineScanResult] = []

        for name, machine_plan in plan.machines.items():
            original = source.get(name)
            if original is None:
                # A máquina pode ter sido descoberta como dependência, mas não
                # ter participado do scan físico. Isso é explicitamente bloqueante.
                continue

            roms = list(original.roms)
            existing = {
                self._identity(rom)
                for rom in roms
                if rom.item_type.value == "rom"
            }

            # O resolver fornece definições, mas a evidência física precisa vir
            # exclusivamente do scan. Nunca criamos uma ROM virtual marcada
            # como válida.
            if mode.lower().replace("_", "-") in {"non-merged", "merged"}:
                provider_names = [rom.machine for rom in machine_plan.inherited_roms]
                for provider_name in dict.fromkeys(provider_names):
                    provider = source.get(provider_name)
                    if provider is None:
                        machine_plan.blocking_reasons.append(
                            f"ROMs herdadas de '{provider_name}' não foram escaneadas; não é seguro materializá-las."
                        )
                        continue
                    for candidate in provider.roms:
                        if candidate.item_type.value != "rom":
                            continue
                        identity = self._identity(candidate)
                        if identity in existing:
                            continue
                        clone = replace(candidate, machine_name=name)
                        roms.append(clone)
                        existing.add(identity)

            prepared_machines.append(
                MachineScanResult(
                    machine_name=original.machine_name,
                    description=original.description,
                    cloneof=original.cloneof,
                    roms=roms,
                    started=original.started,
                    error=original.error,
                )
            )

        prepared = ScanResult(
            machines=prepared_machines,
            xml_path=result.xml_path,
            started_at=result.started_at,
            finished_at=result.finished_at,
            cancelled=result.cancelled,
            error=result.error,
        )
        return PreparedReconstruction(scan=prepared, plan=plan)

    @staticmethod
    def _identity(rom: RomScanResult) -> tuple[str, str, str, int]:
        """Cria identidade estável para evitar ROM duplicada na expansão."""
        return (
            rom.rom_name,
            (rom.expected_crc or "").lower(),
            (rom.expected_sha1 or "").lower(),
            int(rom.expected_size or 0),
        )

    @staticmethod
    def dependency_report(prepared: PreparedReconstruction) -> dict:
        """Converte o plano em relatório JSON-friendly para a GUI/log."""
        plan = prepared.plan
        return {
            "runtime_ready": plan.runtime_ready,
            "requested": list(plan.requested),
            "blocking_reasons": list(plan.blocking_reasons),
            "samples": sorted(plan.samples),
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "kind": edge.kind.value,
                    "reason": edge.reason,
                    "blocking": edge.blocking,
                }
                for edge in plan.edges
            ],
            "machines": {
                name: {
                    "parent": machine.parent,
                    "bios": list(machine.bios_machines),
                    "devices": list(machine.device_machines),
                    "samples": list(machine.samples),
                    "own_roms": [rom.name for rom in machine.own_roms],
                    "inherited_roms": [rom.name for rom in machine.inherited_roms],
                    "blocking_reasons": list(machine.blocking_reasons),
                }
                for name, machine in plan.machines.items()
            },
        }
