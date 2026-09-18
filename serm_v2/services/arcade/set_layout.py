"""Planejamento da organizacao fisica de sets do Arcade Studio.

Esta camada nao copia arquivos. Ela transforma o catalogo logico em um plano
explicito para os tres formatos suportados pelo SERM: split, non-merged e
full-merged. A materializacao sera executada posteriormente pelo mecanismo de
filesystem do proprio SERM.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ...models.arcade import ArcadeGame, ArcadeSetType


class SetFileAction(StrEnum):
    """Acao que a materializacao fisica devera executar."""

    KEEP = "keep"
    SHARE = "share"
    EMBED = "embed"
    OMIT = "omit"


@dataclass(frozen=True, slots=True)
class SetLayoutEntry:
    """Destino logico de uma maquina dentro do layout escolhido."""

    machine_name: str
    archive_name: str
    action: SetFileAction
    source_machine: str | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class SetLayoutPlan:
    """Plano deterministico e independente do filesystem."""

    set_type: ArcadeSetType
    entries: tuple[SetLayoutEntry, ...]

    @property
    def archives(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(entry.archive_name for entry in self.entries if entry.action is not SetFileAction.OMIT))


class ArcadeSetLayoutPlanner:
    """Converte jogos selecionados em um layout fisico MAME-like."""

    def plan(self, games: Iterable[ArcadeGame], set_type: ArcadeSetType) -> SetLayoutPlan:
        catalog = {game.machine_name: game for game in games}
        entries: list[SetLayoutEntry] = []

        if set_type is ArcadeSetType.SPLIT:
            for game in catalog.values():
                entries.append(
                    SetLayoutEntry(
                        game.machine_name,
                        game.machine_name,
                        SetFileAction.KEEP,
                        reason="arquivo proprio do jogo; dependencias compartilhadas permanecem no parent",
                    )
                )
            return SetLayoutPlan(set_type, tuple(entries))

        if set_type is ArcadeSetType.NON_MERGED:
            for game in catalog.values():
                entries.append(
                    SetLayoutEntry(
                        game.machine_name,
                        game.machine_name,
                        SetFileAction.EMBED,
                        reason="cada archive recebe seus componentes, inclusive os compartilhados",
                    )
                )
            return SetLayoutPlan(set_type, tuple(entries))

        # FULL_MERGED: a familia e materializada no archive do parent/root.
        roots = {game.machine_name: self._root_name(game, catalog) for game in catalog.values()}
        for game in catalog.values():
            root = roots[game.machine_name]
            if game.machine_name == root:
                entries.append(
                    SetLayoutEntry(
                        game.machine_name,
                        root,
                        SetFileAction.KEEP,
                        reason="archive raiz da familia full-merged",
                    )
                )
            else:
                entries.append(
                    SetLayoutEntry(
                        game.machine_name,
                        root,
                        SetFileAction.SHARE,
                        source_machine=game.machine_name,
                        reason="clone incorporado ao archive do parent raiz",
                    )
                )
        return SetLayoutPlan(set_type, tuple(entries))

    @staticmethod
    def _root_name(game: ArcadeGame, catalog: dict[str, ArcadeGame]) -> str:
        current = game
        seen: set[str] = set()
        while current.parent_name and current.parent_name in catalog:
            if current.machine_name in seen:
                raise ValueError(f"Ciclo parent/clone detectado em {current.machine_name}")
            seen.add(current.machine_name)
            current = catalog[current.parent_name]
        return current.machine_name


__all__ = [
    "ArcadeSetLayoutPlanner",
    "SetFileAction",
    "SetLayoutEntry",
    "SetLayoutPlan",
]
