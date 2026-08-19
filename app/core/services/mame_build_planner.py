"""Plano unificado de reconstrução MAME.

Combina a árvore de dependências e o layout dos arquivos. O resultado deixa
explícito que BIOS e devices são sets externos, enquanto samples ficam em
``samples/``; eles não são misturados arbitrariamente no ZIP do jogo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from app.core.services.mame_archive_layout import ArchivePlan, MameArchiveLayoutPlanner
from app.core.services.mame_dependency_resolver import DependencyKind, DependencyOptions, DependencyPlan, MameDependencyResolver


@dataclass(slots=True)
class MameBuildPlan:
    """Plano completo que a etapa de escrita deve consumir."""

    dependencies: DependencyPlan
    archives: ArchivePlan
    external_archives: dict[str, str] = field(default_factory=dict)
    samples: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def runtime_ready(self) -> bool:
        """Indica se a topologia do set está resolvida."""
        return self.dependencies.runtime_ready and self.archives.runtime_ready and not self.blockers


class MameBuildPlanner:
    """Constrói o plano final de dependências e armazenamento."""

    def __init__(self, xml_path: str | Path, options: DependencyOptions | None = None):
        self.resolver = MameDependencyResolver(xml_path, options)
        self.options = options or DependencyOptions()
        self.layout = MameArchiveLayoutPlanner()

    def plan(self, machine_names: Iterable[str], mode: str = "split") -> MameBuildPlan:
        """Resolve dependências, layout e sets externos."""
        dependencies = self.resolver.resolve(machine_names, mode=mode)
        archives = self.layout.build(dependencies, mode)
        external: dict[str, str] = {}
        blockers = list(dependencies.blocking_reasons) + list(archives.blockers)

        # BIOS e devices são procurados em seus próprios sets. Isso corresponde
        # à forma como MAME pesquisa system ROMs e device ROMs no rompath.
        for edge in dependencies.edges:
            if edge.kind not in {DependencyKind.BIOS, DependencyKind.DEVICE}:
                continue
            target = edge.target
            target_plan = dependencies.machines.get(target)
            if target_plan is None:
                blockers.append(f"dependência externa '{target}' não possui plano")
                continue
            external[target] = f"{target}.zip"
            if not target_plan.own_roms:
                blockers.append(f"dependência externa '{target}' não possui ROMs próprias no LISTXML")

        if not self.options.include_bios:
            external = {
                name: archive
                for name, archive in external.items()
                if not any(edge.kind is DependencyKind.BIOS and edge.target == name for edge in dependencies.edges)
            }
        if not self.options.include_devices:
            external = {
                name: archive
                for name, archive in external.items()
                if not any(edge.kind is DependencyKind.DEVICE and edge.target == name for edge in dependencies.edges)
            }

        return MameBuildPlan(
            dependencies=dependencies,
            archives=archives,
            external_archives=external,
            samples=sorted(dependencies.samples) if self.options.include_samples else [],
            blockers=blockers,
        )


def plan_mame_build(
    xml_path: str | Path,
    machine_names: Iterable[str],
    *,
    mode: str = "split",
    options: DependencyOptions | None = None,
) -> MameBuildPlan:
    """Atalho para montar um plano completo de construção."""
    return MameBuildPlanner(xml_path, options).plan(machine_names, mode=mode)
