"""Resolução de plataformas para perfis de emuladores.

Este módulo fica entre o LISTXML e o FilterService. Ele não decide quais ROMs
são válidas e não resolve BIOS/devices/CHDs; apenas responde se uma machine
pode pertencer ao perfil de um emulador.

FBNeo recebe tratamento especial: o LISTXML do MAME não identifica quais
machines são implementadas pelo FBNeo. Por isso o resolver aceita um manifesto
externo de nomes de machines. Sem esse manifesto, nenhuma machine é afirmada
como FBNeo, evitando falsos positivos.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping
import xml.etree.ElementTree as ET

from app.core.services.reconstruction_profiles import (
    ArcadePlatform,
    ReconstructionTarget,
    classify_machine_from_xml,
    target_for_platform,
)


NON_ARCADE_TERMS = frozenset({
    "casino", "gambling", "pachinko", "quiz", "mahjong", "horse racing",
    "horse-racing", "medal game", "redemption", "slot machine",
})


@dataclass(frozen=True, slots=True)
class PlatformResolution:
    """Resultado auditável da classificação de uma machine."""

    machine_name: str
    target: ReconstructionTarget
    platform: ArcadePlatform
    supported: bool
    reason: str


class EmulatorPlatformResolver:
    """Classifica machines para MAME, Flycast, Supermodel 3 e FBNeo."""

    def __init__(self, fbneo_machine_names: Iterable[str] | None = None) -> None:
        self._fbneo_names = {
            name.strip().lower()
            for name in (fbneo_machine_names or ())
            if name and name.strip()
        }

    @classmethod
    def from_manifest(cls, path: Path) -> "EmulatorPlatformResolver":
        """Carrega um manifesto simples, uma machine por linha.

        Linhas vazias e comentários iniciados por ``#`` são ignorados. O
        formato deliberadamente simples permite substituir a fonte do FBNeo
        sem alterar o restante da aplicação.
        """
        if not path.exists():
            raise FileNotFoundError(f"Manifesto FBNeo não encontrado: {path}")
        names: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if value and not value.startswith("#"):
                names.append(value)
        return cls(names)

    def resolve(self, machine: ET.Element) -> PlatformResolution:
        """Resolve uma machine e registra explicitamente o motivo."""
        name = (machine.get("name") or "").strip()
        normalized = name.lower()

        is_support = any(
            (machine.get(flag) or "").strip().lower() == "yes"
            for flag in ("isbios", "isdevice")
        )
        if is_support:
            return PlatformResolution(
                name, ReconstructionTarget.MAME, ArcadePlatform.UNKNOWN, False,
                "BIOS/device é dependência e não jogo de um perfil arcade",
            )

        if normalized in self._fbneo_names:
            return PlatformResolution(
                name, ReconstructionTarget.FBNEO, ArcadePlatform.FBNEO_ARCADE,
                True, "machine presente no manifesto oficial/gerado do FBNeo",
            )

        platform = classify_machine_from_xml(machine)
        target = target_for_platform(platform)

        description = (machine.findtext("description") or "").strip().lower()
        non_arcade = next((term for term in NON_ARCADE_TERMS if term in description), None)

        if non_arcade and target in {
            ReconstructionTarget.FLYCAST,
            ReconstructionTarget.FBNEO,
        }:
            return PlatformResolution(
                name, target, platform, False,
                f"categoria não-arcade detectada na descrição: {non_arcade}",
            )

        if target is ReconstructionTarget.SUPERMODEL3:
            reason = "driver/source Model 3 identificado"
        elif target is ReconstructionTarget.FLYCAST:
            reason = f"plataforma Sega arcade identificada: {platform.value}"
        else:
            reason = "machine arcade MAME; destino externo não comprovado"

        return PlatformResolution(name, target, platform, target is ReconstructionTarget.MAME, reason)

    def resolve_many(self, machines: Iterable[ET.Element]) -> list[PlatformResolution]:
        """Resolve uma coleção sem reabrir ou reconstruir o LISTXML."""
        return [self.resolve(machine) for machine in machines]

    def accepted_names(
        self,
        machines: Iterable[ET.Element],
        target: ReconstructionTarget,
    ) -> set[str]:
        """Retorna somente machines comprovadamente aceitas pelo destino."""
        accepted: set[str] = set()
        for machine in machines:
            result = self.resolve(machine)
            if result.supported and result.target is target:
                accepted.add(result.machine_name)
        return accepted

    def classify_mapping(
        self,
        machines: Iterable[ET.Element],
    ) -> Mapping[str, PlatformResolution]:
        """Produz um índice nome -> resolução para reutilização em filtros."""
        return {
            result.machine_name: result
            for result in self.resolve_many(machines)
            if result.machine_name
        }
