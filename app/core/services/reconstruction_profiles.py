"""Perfis de destino para reconstrução multi-emulador.

O perfil decide somente a organização física do conjunto reconstruído. A
validação das ROMs/CHDs continua sendo responsabilidade do scan e dos motores
MAME-aware existentes.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ReconstructionTarget(str, Enum):
    """Destinos de emulação suportados pelo construtor."""

    MAME = "mame"
    SUPERMODEL3 = "supermodel3"
    FLYCAST = "flycast"
    MULTI = "multi"


@dataclass(frozen=True, slots=True)
class ReconstructionProfile:
    """Define o layout físico de uma reconstrução."""

    target: ReconstructionTarget = ReconstructionTarget.MAME
    mame_dir: str = "roms"
    supermodel3_dir: str = "supermodel3/roms"
    flycast_dir: str = "flycast/roms"
    bios_dir: str = "bios"
    devices_dir: str = "devices"
    samples_dir: str = "samples"
    systems_dir: str = "systems"
    exclude_external_from_mame: bool = True

    def destination_for(self, root: Path, target: ReconstructionTarget) -> Path:
        """Retorna a pasta de ROMs correspondente ao destino selecionado."""
        if target is ReconstructionTarget.MAME:
            return root / self.mame_dir
        if target is ReconstructionTarget.SUPERMODEL3:
            return root / self.supermodel3_dir
        if target is ReconstructionTarget.FLYCAST:
            return root / self.flycast_dir
        raise ValueError(f"Destino sem pasta direta: {target.value}")


def classify_machine_from_xml(machine: ET.Element) -> ReconstructionTarget:
    """Classifica uma machine pelo driver MAME.

    O sourcefile é preferido porque é estável dentro do LISTXML e identifica o
    driver de hardware. O fallback usa tags/atributos disponíveis no XML.
    """
    source = (machine.get("sourcefile") or "").lower().replace("\\", "/")
    name = (machine.get("name") or "").lower()
    description = (machine.findtext("description") or "").lower()

    if "model3" in source or "model3" in name or "model 3" in description:
        return ReconstructionTarget.SUPERMODEL3

    if "naomi" in source or "naomi" in name or "naomi" in description:
        return ReconstructionTarget.FLYCAST

    return ReconstructionTarget.MAME


def classify_xml(xml_path: Path) -> dict[str, ReconstructionTarget]:
    """Classifica todas as machines de um LISTXML."""
    root = ET.parse(xml_path).getroot()
    return {
        machine.get("name", ""): classify_machine_from_xml(machine)
        for machine in root.findall("machine")
        if machine.get("name")
    }
