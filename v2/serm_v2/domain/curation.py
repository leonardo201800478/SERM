"""Regras puras de curadoria do catálogo Arcade da V2.

As funções deste módulo não conhecem GUI, SQLite, filesystem ou o projeto
MAME Smart ROM Sorter. Elas recebem objetos do domínio e uma política de
curadoria e retornam decisões determinísticas e auditáveis.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .arcade import ArcadeGame


@dataclass(frozen=True, slots=True)
class CurationPolicy:
    """Política configurável para seleção de um conjunto Arcade."""

    preferred_regions: tuple[str, ...] = ()
    preferred_languages: tuple[str, ...] = ()
    max_players: int | None = None
    max_buttons: int | None = None
    required_controls: tuple[str, ...] = ()
    required_directions: tuple[str, ...] = ()
    strict_controls: bool = False
    orientation: str = "both"
    include_clones: bool = True
    include_bootlegs: bool = True
    include_prototypes: bool = True
    one_game_one_rom: bool = False
    min_quality_score: float | None = None


@dataclass(frozen=True, slots=True)
class CurationDecision:
    """Decisão auditável sobre uma machine."""

    machine_name: str
    selected: bool
    rule: str
    reason: str


@dataclass(frozen=True, slots=True)
class CurationResult:
    """Resultado de uma etapa de curadoria."""

    selected: tuple[ArcadeGame, ...]
    decisions: tuple[CurationDecision, ...] = field(default_factory=tuple)


def _metadata_strings(game: ArcadeGame, key: str) -> set[str]:
    """Obtém um conjunto normalizado de strings da metadata da máquina."""
    value = game.metadata.get(key)
    if isinstance(value, (list, tuple, set, frozenset)):
        return {str(item).strip().casefold() for item in value if str(item).strip()}
    if value is None:
        return set()
    text = str(value).strip()
    return {text.casefold()} if text else set()


def _rank(tags: set[str], preferences: tuple[str, ...]) -> int:
    """Retorna a melhor posição de uma tag na preferência configurada."""
    ranks = {value.casefold(): index for index, value in enumerate(preferences)}
    return min((ranks[tag] for tag in tags if tag in ranks), default=10_000)


def _root(game: ArcadeGame, games_by_name: dict[str, ArcadeGame]) -> str:
    """Resolve a raiz parent da família sem depender de profundidade arbitrária."""
    current = game
    visited: set[str] = set()
    while current.parent_name and current.name not in visited:
        visited.add(current.name)
        parent = games_by_name.get(current.parent_name)
        if parent is None:
            return current.parent_name
        current = parent
    return current.name


def _basic_filter(game: ArcadeGame, policy: CurationPolicy) -> CurationDecision | None:
    """Aplica filtros independentes da escolha 1G1R."""
    metadata = game.metadata

    if not policy.include_clones and game.parent_name:
        return CurationDecision(game.name, False, "clone", "clone desabilitado pela política")

    if not policy.include_bootlegs and bool(metadata.get("is_bootleg")):
        return CurationDecision(game.name, False, "bootleg", "bootleg desabilitado pela política")

    if not policy.include_prototypes and bool(metadata.get("is_prototype")):
        return CurationDecision(game.name, False, "prototype", "prototype desabilitado pela política")

    if policy.max_players is not None:
        players = metadata.get("players")
        if isinstance(players, int) and players > policy.max_players:
            return CurationDecision(game.name, False, "players", f"{players} jogadores > limite")

    if policy.max_buttons is not None:
        buttons = metadata.get("buttons")
        if isinstance(buttons, int) and buttons > policy.max_buttons:
            return CurationDecision(game.name, False, "buttons", f"{buttons} botões > limite")

    if policy.required_controls:
        controls = _metadata_strings(game, "controls")
        required = {value.casefold() for value in policy.required_controls}
        known_conflict = bool(controls) and (
            not required.issubset(controls) if policy.strict_controls else not controls.intersection(required)
        )
        if known_conflict:
            return CurationDecision(game.name, False, "controls", "controles incompatíveis")

    if policy.required_directions:
        directions = _metadata_strings(game, "directions")
        required = {value.casefold() for value in policy.required_directions}
        if directions and not directions.intersection(required):
            return CurationDecision(game.name, False, "directions", "vias/direções incompatíveis")

    if policy.orientation.casefold() != "both":
        orientation = str(metadata.get("orientation") or "").casefold()
        if orientation and orientation != policy.orientation.casefold():
            return CurationDecision(game.name, False, "orientation", "orientação incompatível")

    if policy.min_quality_score is not None:
        score = metadata.get("quality_score")
        if isinstance(score, (int, float)) and score < policy.min_quality_score:
            return CurationDecision(game.name, False, "quality", "pontuação abaixo do mínimo")

    return None


def _one_game_one_rom(games: list[ArcadeGame], policy: CurationPolicy) -> tuple[list[ArcadeGame], list[CurationDecision]]:
    """Seleciona deterministicamente um representante por família parent/clone."""
    if not policy.one_game_one_rom:
        return games, []

    by_name = {game.name: game for game in games}
    families: dict[str, list[ArcadeGame]] = defaultdict(list)
    for game in games:
        families[_root(game, by_name)].append(game)

    selected: list[ArcadeGame] = []
    decisions: list[CurationDecision] = []
    for root_name, members in sorted(families.items()):
        def key(game: ArcadeGame) -> tuple[object, ...]:
            regions = _metadata_strings(game, "regions")
            languages = _metadata_strings(game, "languages")
            return (
                _rank(regions, policy.preferred_regions),
                _rank(languages, policy.preferred_languages),
                0 if game.name == root_name else 1,
                1 if bool(game.metadata.get("is_bootleg")) else 0,
                game.name.casefold(),
            )

        winner = min(members, key=key)
        selected.append(winner)
        for candidate in members:
            if candidate.name != winner.name:
                decisions.append(
                    CurationDecision(
                        candidate.name,
                        False,
                        "1G1R",
                        f"representante selecionado: {winner.name}",
                    )
                )

    return selected, decisions


def curate_games(games: list[ArcadeGame], policy: CurationPolicy) -> CurationResult:
    """Aplica filtros básicos e, opcionalmente, 1G1R em ordem determinística."""
    candidates: list[ArcadeGame] = []
    decisions: list[CurationDecision] = []

    for game in games:
        decision = _basic_filter(game, policy)
        if decision is not None:
            decisions.append(decision)
            continue
        candidates.append(game)

    selected, one_g_decisions = _one_game_one_rom(candidates, policy)
    decisions.extend(one_g_decisions)
    selected.sort(key=lambda game: game.name.casefold())
    return CurationResult(tuple(selected), tuple(decisions))


__all__ = ["CurationDecision", "CurationPolicy", "CurationResult", "curate_games"]
