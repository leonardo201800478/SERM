"""Resolução de dependências MAME para reconstrução de sets.

A resolução ocorre antes da escrita dos ZIPs e transforma o LISTXML em um
plano explícito de dependências:

machine -> clone/parent -> merge -> BIOS -> device -> samples.

O resolver não copia arquivos e não modifica as fontes. Ele apenas determina
quais máquinas/ROMs são necessárias e em qual conjunto cada ROM deve aparecer.
Isso permite que o motor de reconstrução trate Split, Merged e Non-Merged de
forma determinística e auditável.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable
import xml.etree.ElementTree as ET


class DependencyKind(str, Enum):
    """Tipo de dependência descoberta no LISTXML."""

    PARENT = "parent"
    MERGE = "merge"
    BIOS = "bios"
    DEVICE = "device"
    SAMPLE = "sample"


@dataclass(frozen=True, slots=True)
class DependencyOptions:
    """Opções que controlam a expansão da árvore de dependências."""

    include_clones: bool = True
    include_bios: bool = True
    include_devices: bool = True
    include_samples: bool = True
    include_optional: bool = True


@dataclass(frozen=True, slots=True)
class RomDefinition:
    """ROM descrita pelo LISTXML, sem referência a arquivo físico."""

    machine: str
    name: str
    size: int
    crc: str
    sha1: str
    status: str
    optional: bool
    bios: str
    merge: str


@dataclass(frozen=True, slots=True)
class MachineDefinition:
    """Metadados necessários para resolver uma machine MAME."""

    name: str
    description: str
    cloneof: str
    romof: str
    is_bios: bool
    is_device: bool
    roms: tuple[RomDefinition, ...]
    bios_sets: tuple[str, ...]
    device_refs: tuple[str, ...]
    samples: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    """Uma dependência explicada entre duas entidades MAME."""

    source: str
    target: str
    kind: DependencyKind
    reason: str
    blocking: bool = True


@dataclass(slots=True)
class MachinePlan:
    """Plano final de uma machine e seus itens físicos."""

    machine: str
    description: str
    parent: str | None = None
    dependencies: list[DependencyEdge] = field(default_factory=list)
    own_roms: list[RomDefinition] = field(default_factory=list)
    inherited_roms: list[RomDefinition] = field(default_factory=list)
    bios_machines: list[str] = field(default_factory=list)
    device_machines: list[str] = field(default_factory=list)
    samples: list[str] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)

    @property
    def all_roms(self) -> list[RomDefinition]:
        """Retorna ROMs próprias + herdadas, sem duplicação por identidade."""
        result: list[RomDefinition] = []
        seen: set[tuple[str, str, str, int]] = set()
        for rom in (*self.inherited_roms, *self.own_roms):
            key = (rom.name, rom.crc.lower(), rom.sha1.lower(), rom.size)
            if key in seen:
                continue
            seen.add(key)
            result.append(rom)
        return result


@dataclass(slots=True)
class DependencyPlan:
    """Plano completo para todas as machines solicitadas."""

    requested: list[str]
    machines: dict[str, MachinePlan] = field(default_factory=dict)
    edges: list[DependencyEdge] = field(default_factory=list)
    samples: set[str] = field(default_factory=set)
    blocking_reasons: list[str] = field(default_factory=list)

    @property
    def runtime_ready(self) -> bool:
        """Indica se nenhuma dependência conhecida ficou sem resolução."""
        return not self.blocking_reasons and all(not p.blocking_reasons for p in self.machines.values())


class MameDependencyResolver:
    """Resolve a árvore de dependências declarada pelo LISTXML."""

    def __init__(self, xml_path: str | Path, options: DependencyOptions | None = None):
        self.xml_path = Path(xml_path)
        self.options = options or DependencyOptions()
        self.catalog: dict[str, MachineDefinition] = {}
        self._bios_name_to_machine: dict[str, str] = {}
        self._load()

    def resolve(self, machine_names: Iterable[str], mode: str = "split") -> DependencyPlan:
        """Cria o plano de dependências para Split, Merged ou Non-Merged."""
        mode = mode.lower().replace("_", "-")
        if mode not in {"split", "merged", "non-merged"}:
            raise ValueError("mode deve ser 'split', 'merged' ou 'non-merged'")

        requested = list(dict.fromkeys(str(name) for name in machine_names if str(name)))
        plan = DependencyPlan(requested=requested)
        visiting: set[str] = set()
        visited: set[str] = set()

        for name in requested:
            self._resolve_machine(name, mode, plan, visiting, visited)

        # Samples são dependências externas a ZIPs de ROM. Elas ficam no plano
        # mesmo quando o modo de set não altera o conteúdo dos ZIPs.
        if not self.options.include_samples:
            plan.samples.clear()
        return plan

    def _resolve_machine(
        self,
        name: str,
        mode: str,
        plan: DependencyPlan,
        visiting: set[str],
        visited: set[str],
    ) -> MachinePlan | None:
        if name in visiting:
            reason = f"ciclo de dependência detectado envolvendo '{name}'"
            plan.blocking_reasons.append(reason)
            return None
        if name in visited:
            return plan.machines.get(name)

        definition = self.catalog.get(name)
        if definition is None:
            reason = f"machine '{name}' não existe no LISTXML"
            plan.blocking_reasons.append(reason)
            return None

        if definition.is_device and not self.options.include_devices:
            plan.machines[name] = MachinePlan(
                machine=name,
                description=definition.description,
                blocking_reasons=["device desabilitado nas opções de construção"],
            )
            visited.add(name)
            return plan.machines[name]

        if definition.is_bios and not self.options.include_bios:
            plan.machines[name] = MachinePlan(
                machine=name,
                description=definition.description,
                blocking_reasons=["BIOS desabilitada nas opções de construção"],
            )
            visited.add(name)
            return plan.machines[name]

        visiting.add(name)
        machine_plan = MachinePlan(
            machine=name,
            description=definition.description,
            parent=definition.cloneof or definition.romof or None,
            own_roms=list(self._eligible_roms(definition)),
            samples=list(definition.samples) if self.options.include_samples else [],
        )
        plan.machines[name] = machine_plan
        plan.samples.update(machine_plan.samples)

        # Parent/romof é a dependência estrutural principal do clone.
        parent_name = definition.cloneof or definition.romof
        if parent_name:
            if not self.options.include_clones:
                machine_plan.blocking_reasons.append(
                    f"clone '{name}' depende de parent '{parent_name}', mas clones estão desabilitados"
                )
            else:
                edge = DependencyEdge(
                    name,
                    parent_name,
                    DependencyKind.PARENT,
                    f"'{name}' declara parent/romof='{parent_name}' no LISTXML",
                )
                self._add_edge(plan, machine_plan, edge)
                parent_plan = self._resolve_machine(parent_name, mode, plan, visiting, visited)
                if parent_plan is None:
                    machine_plan.blocking_reasons.append(f"parent '{parent_name}' não pôde ser resolvido")
                elif mode == "non-merged":
                    machine_plan.inherited_roms.extend(parent_plan.all_roms)

        # merge pode apontar diretamente para um set que fornece o arquivo.
        # Em Split a ROM mergeada fica no fornecedor; em Non-Merged ela precisa
        # ser materializada no clone; em Merged ela é herdada para o ZIP do clone.
        for rom in machine_plan.own_roms:
            if not rom.merge:
                continue
            provider = rom.merge
            if provider not in self.catalog:
                machine_plan.blocking_reasons.append(
                    f"ROM '{rom.name}' declara merge='{provider}', mas o set fornecedor não existe no LISTXML"
                )
                continue
            edge = DependencyEdge(
                name,
                provider,
                DependencyKind.MERGE,
                f"ROM '{rom.name}' declara merge='{provider}'",
            )
            self._add_edge(plan, machine_plan, edge)
            provider_plan = self._resolve_machine(provider, mode, plan, visiting, visited)
            if provider_plan is None:
                machine_plan.blocking_reasons.append(f"fornecedor merge '{provider}' não pôde ser resolvido")
            elif mode in {"non-merged", "merged"}:
                machine_plan.inherited_roms.extend(provider_plan.all_roms)

        # BIOS é resolvida pelo nome do biosset, não assumindo que o valor do
        # atributo bios seja necessariamente o nome da machine.
        if self.options.include_bios:
            for rom in machine_plan.own_roms:
                if not rom.bios:
                    continue
                bios_machine = self._bios_name_to_machine.get(rom.bios) or (
                    rom.bios if rom.bios in self.catalog else None
                )
                if bios_machine is None:
                    machine_plan.blocking_reasons.append(
                        f"ROM '{rom.name}' requer BIOS '{rom.bios}', mas nenhum biosset/machine correspondente foi encontrado"
                    )
                    continue
                edge = DependencyEdge(
                    name,
                    bios_machine,
                    DependencyKind.BIOS,
                    f"ROM '{rom.name}' seleciona BIOS '{rom.bios}'",
                )
                self._add_edge(plan, machine_plan, edge)
                self._resolve_machine(bios_machine, mode, plan, visiting, visited)
                if bios_machine not in machine_plan.bios_machines:
                    machine_plan.bios_machines.append(bios_machine)

        # device_ref é uma dependência explícita da machine.
        if self.options.include_devices:
            for device_name in definition.device_refs:
                edge = DependencyEdge(
                    name,
                    device_name,
                    DependencyKind.DEVICE,
                    f"device_ref='{device_name}' declarado pela machine",
                )
                self._add_edge(plan, machine_plan, edge)
                if device_name not in self.catalog:
                    machine_plan.blocking_reasons.append(
                        f"device '{device_name}' referenciado por '{name}' não existe no LISTXML"
                    )
                    continue
                self._resolve_machine(device_name, mode, plan, visiting, visited)
                if device_name not in machine_plan.device_machines:
                    machine_plan.device_machines.append(device_name)

        visiting.remove(name)
        visited.add(name)
        return machine_plan

    def _eligible_roms(self, definition: MachineDefinition) -> tuple[RomDefinition, ...]:
        """Remove somente ROMs opcionais quando a opção estiver desligada."""
        if self.options.include_optional:
            return definition.roms
        return tuple(rom for rom in definition.roms if not rom.optional)

    @staticmethod
    def _add_edge(plan: DependencyPlan, machine_plan: MachinePlan, edge: DependencyEdge) -> None:
        """Adiciona uma aresta apenas uma vez ao plano global e local."""
        if edge not in plan.edges:
            plan.edges.append(edge)
        if edge not in machine_plan.dependencies:
            machine_plan.dependencies.append(edge)

    def _load(self) -> None:
        """Carrega machines, BIOS sets, devices, clones e samples do LISTXML."""
        if not self.xml_path.is_file():
            raise FileNotFoundError(f"LISTXML não encontrado: {self.xml_path}")
        try:
            root = ET.parse(self.xml_path).getroot()
        except (OSError, ET.ParseError) as exc:
            raise ValueError(f"LISTXML inválido: {self.xml_path}") from exc

        raw_machines: list[ET.Element] = list(root.findall("machine"))
        if not raw_machines:
            # Compatibilidade com XMLs cujo elemento raiz já seja <machine>.
            raw_machines = [root] if root.tag == "machine" else []

        for element in raw_machines:
            name = (element.get("name") or "").strip()
            if not name:
                continue
            roms: list[RomDefinition] = []
            for rom in element.findall("rom"):
                rom_name = (rom.get("name") or "").strip()
                if not rom_name:
                    continue
                roms.append(
                    RomDefinition(
                        machine=name,
                        name=rom_name,
                        size=int(rom.get("size") or 0),
                        crc=(rom.get("crc") or "").lower(),
                        sha1=(rom.get("sha1") or "").lower(),
                        status=(rom.get("status") or "good").lower(),
                        optional=str(rom.get("optional") or "").lower() in {"yes", "true", "1"},
                        bios=rom.get("bios") or "",
                        merge=rom.get("merge") or "",
                    )
                )

            bios_sets = tuple(
                (node.get("name") or "").strip()
                for node in element.findall("biosset")
                if (node.get("name") or "").strip()
            )
            device_refs = tuple(
                (node.get("name") or "").strip()
                for node in element.findall("device_ref")
                if (node.get("name") or "").strip()
            )
            samples = tuple(
                value
                for value in (
                    element.get("sampleof") or "",
                    *(node.get("name") or "" for node in element.findall("sample")),
                )
                if value
            )

            self.catalog[name] = MachineDefinition(
                name=name,
                description=(element.findtext("description") or "").strip(),
                cloneof=element.get("cloneof") or "",
                romof=element.get("romof") or "",
                is_bios=str(element.get("isbios") or "").lower() == "yes",
                is_device=str(element.get("isdevice") or "").lower() == "yes",
                roms=tuple(roms),
                bios_sets=bios_sets,
                device_refs=device_refs,
                samples=tuple(dict.fromkeys(samples)),
            )

        for definition in self.catalog.values():
            for bios_name in definition.bios_sets:
                self._bios_name_to_machine.setdefault(bios_name, definition.name)


def resolve_mame_dependencies(
    xml_path: str | Path,
    machine_names: Iterable[str],
    *,
    mode: str = "split",
    options: DependencyOptions | None = None,
) -> DependencyPlan:
    """Função de conveniência para resolver um conjunto de machines."""
    return MameDependencyResolver(xml_path, options).resolve(machine_names, mode=mode)
