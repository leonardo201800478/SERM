"""Perfis e classificação de plataformas para reconstrução multi-emulador.

O LISTXML do MAME permanece como fonte primária de machines, ROMs, BIOS,
devices e CHDs. Este módulo determina somente o destino lógico; a validação
física e a resolução de dependências continuam nos serviços especializados.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import xml.etree.ElementTree as ET


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
        mapping = {
            ReconstructionTarget.MAME: self.mame_dir,
            ReconstructionTarget.SUPERMODEL3: self.supermodel3_dir,
            ReconstructionTarget.FLYCAST: self.flycast_dir,
            ReconstructionTarget.FBNEO: self.fbneo_dir,
        }
        try:
            return root / mapping[target]
        except KeyError as exc:
            raise ValueError(f"Destino sem pasta direta: {target.value}") from exc


# ---------------------------------------------------------------------------
# Helpers de leitura do LISTXML
# ---------------------------------------------------------------------------


def _normalized_source(machine: ET.Element) -> str:
    """Normaliza sourcefile para comparação independente de separador."""
    return (machine.get("sourcefile") or "").strip().replace("\\", "/").lower()


def _text(machine: ET.Element, tag: str) -> str:
    """Obtém texto XML normalizado, retornando vazio quando ausente."""
    return (machine.findtext(tag) or "").strip().lower()


def _machine_name(machine: ET.Element) -> str:
    """Obtém o nome interno da machine em minúsculas."""
    return (machine.get("name") or "").strip().lower()


def _bios_names(machine: ET.Element) -> set[str]:
    """Extrai nomes de BIOS referenciados diretamente pela machine."""
    return {
        name
        for node in machine.findall("biosset")
        if (name := (node.get("name") or "").strip().lower())
    }


def _is_support_machine(machine: ET.Element) -> bool:
    """Identifica BIOS/devices que não devem ser tratados como jogos."""
    return any(
        (machine.get(flag) or "").strip().lower() == "yes"
        for flag in ("isbios", "isdevice")
    )


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    """Testa termos normalizados sem depender de maiúsculas/minúsculas."""
    return any(term in value for term in terms)


# ---------------------------------------------------------------------------
# Classificação de plataforma
# ---------------------------------------------------------------------------


def classify_machine_from_xml(machine: ET.Element) -> ArcadePlatform:
    """Classifica uma machine com evidências do LISTXML.

    ``sourcefile`` é a evidência principal para hardware. Nome, descrição e
    BIOS são somente fallbacks conservadores para drivers compartilhados.
    BIOS/devices retornam UNKNOWN porque são dependências, não jogos.

    Importante: FBNeo não pode ser inferido de forma confiável apenas pelo
    LISTXML do MAME. O mesmo conjunto de ROMs pode ser usado por vários
    emuladores e o MAME não marca uma machine como "FBNeo". O resolver do
    perfil FBNeo deve, portanto, fornecer a classificação Arcade específica
    quando essa etapa for implementada.
    """
    if _is_support_machine(machine):
        return ArcadePlatform.UNKNOWN

    source = _normalized_source(machine)
    name = _machine_name(machine)
    description = _text(machine, "description")
    bios_names = _bios_names(machine)
    evidence = " ".join((source, name, description, " ".join(sorted(bios_names))))

    # Model 3: fonte explícita é preferida; os fallbacks exigem mais de uma
    # indicação para não transformar qualquer machine com "model3" no nome.
    if _contains_any(source, ("model3", "/model3/")):
        return ArcadePlatform.SEGA_MODEL3
    if "model 3" in description and "sega" in description:
        return ArcadePlatform.SEGA_MODEL3

    # Atomiswave / System SP precisam ser testados antes de NAOMI, pois alguns
    # drivers Sega compartilham infraestrutura de carregamento.
    if _contains_any(evidence, ("atomiswave", "awbios")):
        return ArcadePlatform.SEGA_ATOMISWAVE
    if _contains_any(evidence, ("systemsp", "segasp")):
        return ArcadePlatform.SEGA_SYSTEM_SP

    if _contains_any(evidence, ("naomi2",)):
        return ArcadePlatform.SEGA_NAOMI2
    if _contains_any(evidence, ("naomi",)):
        return ArcadePlatform.SEGA_NAOMI

    return ArcadePlatform.MAME_ARCADE


def target_for_platform(platform: ArcadePlatform) -> ReconstructionTarget:
    """Converte uma plataforma arcade em destino de reconstrução."""
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
    """Classifica diretamente uma machine para um destino."""
    return target_for_platform(classify_machine_from_xml(machine))


def classify_xml(xml_path: Path) -> dict[str, ReconstructionTarget]:
    """Classifica todas as machines de um LISTXML por destino."""
    root = ET.parse(xml_path).getroot()
    return {
        name: classify_machine_target(machine)
        for machine in root.findall("machine")
        if (name := (machine.get("name") or "").strip())
    }


def platforms_for_target(target: ReconstructionTarget) -> frozenset[ArcadePlatform]:
    """Retorna as plataformas explicitamente aceitas por um perfil."""
    mapping = {
        ReconstructionTarget.MAME: frozenset({ArcadePlatform.MAME_ARCADE}),
        ReconstructionTarget.SUPERMODEL3: frozenset({ArcadePlatform.SEGA_MODEL3}),
        ReconstructionTarget.FLYCAST: frozenset({
            ArcadePlatform.SEGA_NAOMI,
            ArcadePlatform.SEGA_NAOMI2,
            ArcadePlatform.SEGA_ATOMISWAVE,
            ArcadePlatform.SEGA_SYSTEM_SP,
        }),
        ReconstructionTarget.FBNEO: frozenset({ArcadePlatform.FBNEO_ARCADE}),
        ReconstructionTarget.MULTI: frozenset({
            ArcadePlatform.MAME_ARCADE,
            ArcadePlatform.SEGA_MODEL3,
            ArcadePlatform.SEGA_NAOMI,
            ArcadePlatform.SEGA_NAOMI2,
            ArcadePlatform.SEGA_ATOMISWAVE,
            ArcadePlatform.SEGA_SYSTEM_SP,
            ArcadePlatform.FBNEO_ARCADE,
        }),
    }
    return mapping[target]


def is_supported_platform(target: ReconstructionTarget, platform: ArcadePlatform) -> bool:
    """Informa se uma plataforma pertence ao perfil selecionado."""
    return platform in platforms_for_target(target)


def classify_machines(
    machines: Iterable[ET.Element],
) -> dict[str, ArcadePlatform]:
    """Classifica uma coleção de elementos sem precisar reabrir o LISTXML."""
    result: dict[str, ArcadePlatform] = {}
    for machine in machines:
        name = (machine.get("name") or "").strip()
        if name:
            result[name] = classify_machine_from_xml(machine)
    return result
