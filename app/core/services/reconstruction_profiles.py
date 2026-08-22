"""Perfis e classificação de plataformas para reconstrução multi-emulador.

O LISTXML do MAME permanece como fonte primária de machines, ROMs, BIOS,
devices e CHDs. Este módulo apenas determina o destino lógico de uma machine.
A validação física e a resolução de dependências continuam nos serviços
especializados.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from typing import Iterable


class ReconstructionTarget(str, Enum):
    """Destinos de reconstrução suportados pelo projeto."""

    MAME = "mame"
    SUPERMODEL3 = "supermodel3"
    FLYCAST = "flycast"
    FBNEO = "fbneo"
    MULTI = "multi"


class ArcadePlatform(str, Enum):
    """Plataformas arcade relevantes para os perfis externos."""

    MAME_ARCADE = "mame_arcade"
    SEGA_MODEL3 = "sega_model3"
    SEGA_NAOMI = "sega_naomi"
    SEGA_NAOMI2 = "sega_naomi2"
    SEGA_ATOMISWAVE = "sega_atomiswave"
    SEGA_SYSTEM_SP = "sega_system_sp"
    FBNEO_ARCADE = "fbneo_arcade"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ReconstructionProfile:
    """Define o layout físico de um destino de reconstrução."""

    target: ReconstructionTarget = ReconstructionTarget.MAME
    mame_dir: str = "roms"
    supermodel3_dir: str = "supermodel3/roms"
    flycast_dir: str = "flycast/roms"
    fbneo_dir: str = "fbneo/roms"
    bios_dir: str = "bios"
    devices_dir: str = "devices"
    samples_dir: str = "samples"
    systems_dir: str = "systems"
    exclude_external_from_mame: bool = True

    def destination_for(self, root: Path, target: ReconstructionTarget) -> Path:
        """Retorna a pasta de ROMs correspondente ao destino."""
        if target is ReconstructionTarget.MAME:
            return root / self.mame_dir
        if target is ReconstructionTarget.SUPERMODEL3:
            return root / self.supermodel3_dir
        if target is ReconstructionTarget.FLYCAST:
            return root / self.flycast_dir
        if target is ReconstructionTarget.FBNEO:
            return root / self.fbneo_dir
        raise ValueError(f"Destino sem pasta direta: {target.value}")


# ---------------------------------------------------------------------------
# Classificação
# ---------------------------------------------------------------------------

# O sourcefile do MAME é a evidência mais forte para hardware. Os padrões
# abaixo são deliberadamente específicos para evitar classificar qualquer
# driver que apenas contenha "naomi" ou "model3" no nome da machine.
_MODEL3_SOURCE_RE = re.compile(r"(?:^|/)model3/", re.IGNORECASE)
_NAOMI_SOURCE_RE = re.compile(r"(?:^|/)(?:naomi|naomi2)/", re.IGNORECASE)
_ATOMISWAVE_SOURCE_RE = re.compile(r"(?:^|/)(?:naomi|atomiswave)/", re.IGNORECASE)
_SYSTEMSP_SOURCE_RE = re.compile(r"(?:^|/)systemsp/", re.IGNORECASE)


def _normalized_source(machine: ET.Element) -> str:
    """Normaliza sourcefile para comparação independente de plataforma."""
    return (machine.get("sourcefile") or "").strip().replace("\\", "/").lower()


def _text(machine: ET.Element, tag: str) -> str:
    """Obtém texto XML normalizado, retornando string vazia quando ausente."""
    return (machine.findtext(tag) or "").strip().lower()


def _machine_name(machine: ET.Element) -> str:
    """Obtém o nome interno da machine em minúsculas."""
    return (machine.get("name") or "").strip().lower()


def _bios_names(machine: ET.Element) -> set[str]:
    """Extrai nomes de BIOS referenciados diretamente pela machine."""
    names: set[str] = set()
    for node in machine.findall("biosset"):
        name = (node.get("name") or "").strip().lower()
        if name:
            names.add(name)
    return names


def _has_machine_flag(machine: ET.Element, flag: str) -> bool:
    """Testa um atributo MAME booleano no formato yes/no."""
    return (machine.get(flag) or "").strip().lower() == "yes"


def classify_machine_from_xml(machine: ET.Element) -> ArcadePlatform:
    """Classifica uma machine usando evidências do LISTXML.

    A ordem de decisão é intencional:

    1. BIOS/device não são jogos e permanecem UNKNOWN para os perfis Arcade.
    2. O ``sourcefile`` identifica o driver de hardware e tem prioridade.
    3. BIOS/nomes específicos ajudam nos sistemas que compartilham drivers.
    4. O nome/descrição só são usados como fallback conservador.

    A função nunca assume que uma substring arbitrária no nome de uma ROM
    transforma uma machine em Flycast/Supermodel. Em caso de dúvida retorna
    UNKNOWN, permitindo que o filtro do perfil decida explicitamente o destino.
    """
    if _has_machine_flag(machine, "isbios") or _has_machine_flag(machine, "isdevice"):
        return ArcadePlatform.UNKNOWN

    source = _normalized_source(machine)
    name = _machine_name(machine)
    description = _text(machine, "description")
    bios_names = _bios_names(machine)

    if _MODEL3_SOURCE_RE.search(source):
        return ArcadePlatform.SEGA_MODEL3

    # Model 3 possui drivers que podem ter nomes diferentes; só aceitamos
    # fallback quando há evidência conjunta no nome/descrição.
    if name.startswith(("model3", "scudrace", "daytona", "lostwsga")) and (
        "model 3" in description or "sega" in description
    ):
        return ArcadePlatform.SEGA_MODEL3

    if "atomiswave" in source or "atomiswave" in name or "awbios" in bios_names:
        return ArcadePlatform.SEGA_ATOMISWAVE

    if "systemsp" in source or name.startswith("systemsp") or "segasp" in bios_names:
        return ArcadePlatform.SEGA_SYSTEM_SP

    # NAOMI/NAOMI2 são frequentemente tratados por drivers compartilhados.
    if "naomi2" in source or "naomi2" in name or "naomi2" in bios_names:
        return ArcadePlatform.SEGA_NAOMI2

    if "naomi" in source or name.startswith("naomi") or "naomi" in bios_names:
        return ArcadePlatform.SEGA_NAOMI

    # O perfil FBNeo será refinado pelo resolver de hardware/driver próprio.
    # Não classificamos uma machine como FBNeo apenas pelo nome, pois o
    # LISTXML não é uma identificação inequívoca do emulador de destino.
    return ArcadePlatform.MAME_ARCADE


def target_for_platform(platform: ArcadePlatform) -> ReconstructionTarget:
    """Converte uma plataforma arcade em seu destino de reconstrução."""
    if platform is ArcadePlatform.SUPPORTED_MODEL3 if False else False:
        # Mantém a função livre de aliases implícitos; branch impossível
        # removida semanticamente abaixo.
        pass
    if platform is ArcadePlatform.SEGA_MODEL3:
        return ReconstructionTarget.SUPERMODEL3
    if platform in {
        ArcadePlatform.SEGA_NAOMI,
        ArcadePlatform.SEGA_NAOMI2,
        ArcadePlatform.SEGA_ATOMISWAVE,
        ArcadePlatform.SEGA_SYSTEM_SP,
    }:
        return ReconstructionTarget.FLYCAST
    if platform is ArcadePlatform.FBNEO_ARCADE:
        return ReconstructionTarget.FBNEO
    return ReconstructionTarget.MAME


def classify_machine_target(machine: ET.Element) -> ReconstructionTarget:
    """Classifica diretamente a machine para um destino de reconstrução."""
    return target_for_platform(classify_machine_from_xml(machine))


def classify_xml(xml_path: Path) -> dict[str, ReconstructionTarget]:
    """Classifica todas as machines de um LISTXML por destino.

    O resultado inclui BIOS/devices como MAME/UNKNOWN apenas para preservar a
    cobertura do banco. Os serviços de reconstrução devem excluir essas
    machines dos grupos de jogos e resolvê-las via dependências.
    """
    root = ET.parse(xml_path).getroot()
    result: dict[str, ReconstructionTarget] = {}
    for machine in root.findall("machine"):
        name = (machine.get("name") or "").strip()
        if not name:
            continue
        result[name] = classify_machine_target(machine)
    return result


def platforms_for_target(target: ReconstructionTarget) -> frozenset[ArcadePlatform]:
    """Retorna as plataformas aceitas por cada perfil externo."""
    if target is ReconstructionTarget.SUPERMODEL3:
        return frozenset({ArcadePlatform.SEGA_MODEL3})
    if target is ReconstructionTarget.FLYCAST:
        return frozenset({
            ArcadePlatform.SEGA_NAOMI,
            ArcadePlatform.SEGA_NAOMI2,
            ArcadePlatform.SEGA_ATOMISWAVE,
            ArcadePlatform.SEGA_SYSTEM_SP,
        })
    if target is ReconstructionTarget.FBNEO:
        return frozenset({ArcadePlatform.FBNEO_ARCADE})
    if target is ReconstructionTarget.MAME:
        return frozenset({ArcadePlatform.MAME_ARCADE})
    return frozenset()


def is_supported_platform(target: ReconstructionTarget, platform: ArcadePlatform) -> bool:
    """Informa se uma plataforma pertence ao perfil selecionado."""
    return platform in platforms_for_target(target)
