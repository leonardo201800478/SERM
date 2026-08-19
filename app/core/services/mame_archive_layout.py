"""Converte um DependencyPlan em arquivos ZIP lógicos de MAME.

A regra de armazenamento é separada da resolução de dependências:

* split: ROMs próprias ficam no próprio set; parent/BIOS/device são externos;
* non-merged: cada set recebe tudo que precisa para ser autocontido;
* merged: o arquivo do parent (raiz da cadeia) recebe parent + clones
  selecionados e dependências de merge. BIOS e devices continuam externos.

Nenhum arquivo é copiado aqui. O resultado é somente um plano de escrita.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.core.services.mame_dependency_resolver import (
    DependencyKind,
    DependencyPlan,
    MachinePlan,
    RomDefinition,
)


@dataclass(frozen=True, slots=True)
class ArchiveRom:
    """ROM que deve aparecer em um ZIP lógico."""

    archive: str
    rom: RomDefinition
    provider_machine: str
    reason: str


@dataclass(slots=True)
class ArchivePlan:
    """Plano de ZIPs e conflitos detectados."""

    mode: str
    archives: dict[str, list[ArchiveRom]] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)

    @property
    def runtime_ready(self) -> bool:
        """Indica se não há conflito estrutural de escrita."""
        return not self.blockers


class MameArchiveLayoutPlanner:
    """Calcula a localização lógica das ROMs sem acessar o filesystem."""

    def build(self, plan: DependencyPlan, mode: str) -> ArchivePlan:
        """Gera o layout correto para Split, Non-Merged ou Merged."""
        normalized = mode.lower().replace("_", "-")
        if normalized not in {"split", "non-merged", "merged"}:
            raise ValueError("mode deve ser 'split', 'non-merged' ou 'merged'")

        result = ArchivePlan(mode=normalized)
        for machine_name in plan.requested:
            machine = plan.machines.get(machine_name)
            if machine is None:
                result.blockers.append(f"machine solicitada '{machine_name}' não possui plano de dependências")
                continue
            if normalized == "split":
                self._add_split(machine, result)
            elif normalized == "non-merged":
                self._add_nonmerged(machine, plan, result)
            else:
                self._add_merged(machine, plan, result)

        self._deduplicate_and_detect_conflicts(result)
        return result

    def _add_split(self, machine: MachinePlan, result: ArchivePlan) -> None:
        """Split contém somente os ROMs próprios do set."""
        for rom in machine.own_roms:
            if rom.merge:
                # O provider é o lugar físico da ROM no split set.
                continue
            self._append(result, machine.machine, rom, machine.machine, "ROM própria do set")

    def _add_nonmerged(self, machine: MachinePlan, plan: DependencyPlan, result: ArchivePlan) -> None:
        """Non-Merged materializa toda a cadeia necessária no próprio ZIP."""
        roms = self._machine_closure_roms(machine, plan)
        for provider, rom in roms:
            self._append(result, machine.machine, rom, provider, "ROM necessária para set autocontido")

    def _add_merged(self, machine: MachinePlan, plan: DependencyPlan, result: ArchivePlan) -> None:
        """Merged coloca parent + clones selecionados no ZIP da raiz parent."""
        owner = self._root_parent(machine, plan)
        for provider, rom in self._machine_closure_roms(machine, plan):
            self._append(
                result,
                owner,
                rom,
                provider,
                f"ROM de '{provider}' armazenada no merged set raiz '{owner}'",
            )

    def _machine_closure_roms(
        self,
        machine: MachinePlan,
        plan: DependencyPlan,
    ) -> list[tuple[str, RomDefinition]]:
        """Coleta ROMs próprias e dos providers de parent/merge necessários."""
        result: list[tuple[str, RomDefinition]] = []
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            current = plan.machines.get(name)
            if current is None:
                return
            for rom in current.own_roms:
                if rom.merge:
                    provider = rom.merge
                    visit(provider)
                    # A ROM mergeada já é fornecida pelo provider; não deve ser
                    # duplicada como uma ROM própria do clone.
                    continue
                result.append((current.machine, rom))
            if current.parent:
                visit(current.parent)

        visit(machine.machine)
        return result

    @staticmethod
    def _root_parent(machine: MachinePlan, plan: DependencyPlan) -> str:
        """Obtém a raiz da cadeia parent/clone."""
        current = machine.machine
        visited: set[str] = set()
        while current not in visited:
            visited.add(current)
            definition = plan.machines.get(current)
            if definition is None or not definition.parent:
                return current
            current = definition.parent
        return current

    @staticmethod
    def _append(
        result: ArchivePlan,
        archive: str,
        rom: RomDefinition,
        provider: str,
        reason: str,
    ) -> None:
        result.archives.setdefault(archive, []).append(
            ArchiveRom(archive=archive, rom=rom, provider_machine=provider, reason=reason)
        )

    @staticmethod
    def _deduplicate_and_detect_conflicts(result: ArchivePlan) -> None:
        """Remove duplicatas e rejeita dois conteúdos diferentes para o mesmo nome."""
        for archive, entries in list(result.archives.items()):
            unique: dict[str, ArchiveRom] = {}
            for entry in entries:
                previous = unique.get(entry.rom.name)
                if previous is None:
                    unique[entry.rom.name] = entry
                    continue
                old_key = (
                    previous.rom.size,
                    previous.rom.crc.lower(),
                    previous.rom.sha1.lower(),
                )
                new_key = (entry.rom.size, entry.rom.crc.lower(), entry.rom.sha1.lower())
                if old_key != new_key:
                    result.blockers.append(
                        f"conflito no archive '{archive}': ROM '{entry.rom.name}' possui definições físicas diferentes "
                        f"({previous.provider_machine} vs {entry.provider_machine})"
                    )
            result.archives[archive] = list(unique.values())
