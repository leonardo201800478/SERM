"""Motor unificado de filtros em camadas do Arcade Studio."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from ...models.arcade import ArcadeGame, PlayabilityStatus
from ...models.arcade_classification import (
    ArcadeClassification,
    ArcadeContentType,
    ArcadeGenre,
    ArcadeHardwareFamily,
    ArcadeInputType,
    WheelAngleClass,
)
from .classification_service import ArcadeClassificationService


class FilterDecision(StrEnum):
    INCLUDED = "included"
    EXCLUDED = "excluded"


class FilterStage(StrEnum):
    CONTENT = "content"
    PLAYABILITY = "playability"
    GENRE = "genre"
    HARDWARE = "hardware"
    MANUFACTURER = "manufacturer"
    SERIES = "series"
    INPUT = "input"
    WHEEL = "wheel"


@dataclass(frozen=True, slots=True)
class FilterRules:
    """Regras declarativas do único motor de seleção do Arcade Studio.

    Playability é deliberadamente separado de ``rom_status``. O primeiro
    descreve o estágio de emulação/execução do título; o segundo descreve a
    integridade física dos componentes. Um não deve ser reduzido ao outro.
    """

    excluded_content_types: frozenset[ArcadeContentType] = frozenset()
    included_content_types: frozenset[ArcadeContentType] = frozenset()
    included_playability: frozenset[PlayabilityStatus] = frozenset()
    included_genres: frozenset[ArcadeGenre] = frozenset()
    included_hardware: frozenset[ArcadeHardwareFamily] = frozenset()
    included_manufacturers: frozenset[str] = frozenset()
    included_series: frozenset[str] = frozenset()
    included_inputs: frozenset[ArcadeInputType] = frozenset()
    included_wheel_angles: frozenset[WheelAngleClass] = frozenset()


@dataclass(frozen=True, slots=True)
class FilterTrace:
    decision: FilterDecision
    stage: FilterStage | None = None
    rule: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class FilteredGame:
    game: ArcadeGame
    classification: ArcadeClassification
    trace: FilterTrace


@dataclass(frozen=True, slots=True)
class FilterResult:
    games: tuple[FilteredGame, ...]
    excluded: tuple[FilteredGame, ...]
    total_input: int
    counts_after_stage: Mapping[FilterStage, int] = field(default_factory=dict)

    @property
    def included_count(self) -> int:
        return len(self.games)

    @property
    def excluded_count(self) -> int:
        return len(self.excluded)


Matcher = Callable[[FilteredGame, frozenset], bool]


class ArcadeFilterEngine:
    """Aplica todas as camadas de filtragem sem alterar o catálogo."""

    def __init__(self, classifier: ArcadeClassificationService | None = None) -> None:
        self._classifier = classifier or ArcadeClassificationService()

    def apply(self, games: Iterable[ArcadeGame], rules: FilterRules | None = None) -> FilterResult:
        active_rules = rules or FilterRules()
        items = [
            FilteredGame(game, self._classifier.classify(game), FilterTrace(FilterDecision.INCLUDED))
            for game in games
        ]
        total_input = len(items)
        counts: dict[FilterStage, int] = {}
        excluded: list[FilteredGame] = []

        items, removed = self._apply_content(items, active_rules)
        excluded.extend(removed)
        counts[FilterStage.CONTENT] = len(items)

        items, removed = self._apply_refinement(
            items, active_rules, FilterStage.PLAYABILITY, self._match_playability
        )
        excluded.extend(removed)
        counts[FilterStage.PLAYABILITY] = len(items)

        for stage, matcher in (
            (FilterStage.GENRE, self._match_genre),
            (FilterStage.HARDWARE, self._match_hardware),
            (FilterStage.MANUFACTURER, self._match_manufacturer),
            (FilterStage.SERIES, self._match_series),
            (FilterStage.INPUT, self._match_input),
            (FilterStage.WHEEL, self._match_wheel),
        ):
            items, removed = self._apply_refinement(items, active_rules, stage, matcher)
            excluded.extend(removed)
            counts[stage] = len(items)

        return FilterResult(tuple(items), tuple(excluded), total_input, counts)

    @staticmethod
    def _apply_content(items: list[FilteredGame], rules: FilterRules) -> tuple[list[FilteredGame], list[FilteredGame]]:
        result: list[FilteredGame] = []
        excluded: list[FilteredGame] = []
        for item in items:
            content = item.classification.content_type
            if content in rules.excluded_content_types:
                excluded.append(ArcadeFilterEngine._excluded(item, FilterStage.CONTENT, f"exclude_content:{content.value}", f"CONTENT_TYPE = {content.value}"))
            elif rules.included_content_types and content not in rules.included_content_types:
                excluded.append(ArcadeFilterEngine._excluded(item, FilterStage.CONTENT, "include_content", f"CONTENT_TYPE = {content.value} não está entre os tipos incluídos"))
            else:
                result.append(item)
        return result, excluded

    @staticmethod
    def _apply_refinement(items: list[FilteredGame], rules: FilterRules, stage: FilterStage, matcher: Matcher) -> tuple[list[FilteredGame], list[FilteredGame]]:
        selected = ArcadeFilterEngine._selection_for_stage(rules, stage)
        if not selected:
            return items, []
        result: list[FilteredGame] = []
        excluded: list[FilteredGame] = []
        for item in items:
            if matcher(item, selected):
                result.append(item)
            else:
                excluded.append(ArcadeFilterEngine._excluded(item, stage, f"include_{stage.value}", f"não atende ao filtro {stage.value}"))
        return result, excluded

    @staticmethod
    def _excluded(item: FilteredGame, stage: FilterStage, rule: str, reason: str) -> FilteredGame:
        return FilteredGame(item.game, item.classification, FilterTrace(FilterDecision.EXCLUDED, stage, rule, reason))

    @staticmethod
    def _selection_for_stage(rules: FilterRules, stage: FilterStage) -> frozenset:
        return {
            FilterStage.PLAYABILITY: rules.included_playability,
            FilterStage.GENRE: rules.included_genres,
            FilterStage.HARDWARE: rules.included_hardware,
            FilterStage.MANUFACTURER: rules.included_manufacturers,
            FilterStage.SERIES: rules.included_series,
            FilterStage.INPUT: rules.included_inputs,
            FilterStage.WHEEL: rules.included_wheel_angles,
        }.get(stage, frozenset())

    @staticmethod
    def _match_playability(item: FilteredGame, selected: frozenset[PlayabilityStatus]) -> bool:
        return item.game.playability in selected

    @staticmethod
    def _match_genre(item: FilteredGame, selected: frozenset[ArcadeGenre]) -> bool:
        return bool(set(item.classification.genres) & set(selected))

    @staticmethod
    def _match_hardware(item: FilteredGame, selected: frozenset[ArcadeHardwareFamily]) -> bool:
        return bool(set(item.classification.hardware) & set(selected))

    @staticmethod
    def _match_manufacturer(item: FilteredGame, selected: frozenset[str]) -> bool:
        values = {value.casefold() for value in selected}
        return item.classification.manufacturer is not None and item.classification.manufacturer.casefold() in values

    @staticmethod
    def _match_series(item: FilteredGame, selected: frozenset[str]) -> bool:
        values = {value.casefold() for value in selected}
        return item.classification.series is not None and item.classification.series.casefold() in values

    @staticmethod
    def _match_input(item: FilteredGame, selected: frozenset[ArcadeInputType]) -> bool:
        return bool(set(item.classification.inputs) & set(selected))

    @staticmethod
    def _match_wheel(item: FilteredGame, selected: frozenset[WheelAngleClass]) -> bool:
        return item.classification.wheel_angle in selected


__all__ = [
    "ArcadeFilterEngine",
    "FilterDecision",
    "FilterResult",
    "FilterRules",
    "FilterStage",
    "FilterTrace",
    "FilteredGame",
]
