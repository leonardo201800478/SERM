"""Motor de filtros em camadas do Arcade Studio.

O motor aplica primeiro regras de limpeza de conteúdo e somente depois
refinamentos. O catálogo original nunca é alterado.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from ...models.arcade import ArcadeGame
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
    """Resultado da avaliação de um título."""

    INCLUDED = "included"
    EXCLUDED = "excluded"


class FilterStage(StrEnum):
    """Camadas aplicadas pelo motor, na ordem do pipeline."""

    CONTENT = "content"
    GENRE = "genre"
    HARDWARE = "hardware"
    MANUFACTURER = "manufacturer"
    SERIES = "series"
    INPUT = "input"
    WHEEL = "wheel"


@dataclass(frozen=True, slots=True)
class FilterRules:
    """Regras declarativas para uma execução do motor.

    Valores vazios significam que a respectiva camada não restringe o
    resultado. Exclusões são aplicadas antes das seleções/refinamentos.
    """

    excluded_content_types: frozenset[ArcadeContentType] = frozenset()
    included_content_types: frozenset[ArcadeContentType] = frozenset()
    included_genres: frozenset[ArcadeGenre] = frozenset()
    included_hardware: frozenset[ArcadeHardwareFamily] = frozenset()
    included_manufacturers: frozenset[str] = frozenset()
    included_series: frozenset[str] = frozenset()
    included_inputs: frozenset[ArcadeInputType] = frozenset()
    included_wheel_angles: frozenset[WheelAngleClass] = frozenset()


@dataclass(frozen=True, slots=True)
class FilterTrace:
    """Explica a decisão final de um título."""

    decision: FilterDecision
    stage: FilterStage | None = None
    rule: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class FilteredGame:
    """Título acompanhado de sua classificação e explicação."""

    game: ArcadeGame
    classification: ArcadeClassification
    trace: FilterTrace


@dataclass(frozen=True, slots=True)
class FilterResult:
    """Resultado completo de uma execução, incluindo métricas por etapa."""

    games: tuple[FilteredGame, ...]
    total_input: int
    counts_after_stage: Mapping[FilterStage, int] = field(default_factory=dict)

    @property
    def included_count(self) -> int:
        return len(self.games)


class ArcadeFilterEngine:
    """Aplica o pipeline de limpeza e refinamento sem alterar o catálogo."""

    def __init__(self, classifier: ArcadeClassificationService | None = None) -> None:
        self._classifier = classifier or ArcadeClassificationService()

    def apply(
        self,
        games: Iterable[ArcadeGame],
        rules: FilterRules | None = None,
    ) -> FilterResult:
        active_rules = rules or FilterRules()
        items = [FilteredGame(game, self._classifier.classify(game), FilterTrace(FilterDecision.INCLUDED)) for game in games]
        total_input = len(items)
        counts: dict[FilterStage, int] = {}

        items = self._apply_content(items, active_rules)
        counts[FilterStage.CONTENT] = len(items)
        items = self._apply_refinement(items, active_rules, FilterStage.GENRE, self._match_genre)
        counts[FilterStage.GENRE] = len(items)
        items = self._apply_refinement(items, active_rules, FilterStage.HARDWARE, self._match_hardware)
        counts[FilterStage.HARDWARE] = len(items)
        items = self._apply_refinement(items, active_rules, FilterStage.MANUFACTURER, self._match_manufacturer)
        counts[FilterStage.MANUFACTURER] = len(items)
        items = self._apply_refinement(items, active_rules, FilterStage.SERIES, self._match_series)
        counts[FilterStage.SERIES] = len(items)
        items = self._apply_refinement(items, active_rules, FilterStage.INPUT, self._match_input)
        counts[FilterStage.INPUT] = len(items)
        items = self._apply_refinement(items, active_rules, FilterStage.WHEEL, self._match_wheel)
        counts[FilterStage.WHEEL] = len(items)
        return FilterResult(tuple(items), total_input, counts)

    @staticmethod
    def _apply_content(items: list[FilteredGame], rules: FilterRules) -> list[FilteredGame]:
        result: list[FilteredGame] = []
        for item in items:
            content = item.classification.content_type
            if content in rules.excluded_content_types:
                result.append(
                    FilteredGame(
                        item.game,
                        item.classification,
                        FilterTrace(
                            FilterDecision.EXCLUDED,
                            FilterStage.CONTENT,
                            f"exclude_content:{content.value}",
                            f"CONTENT_TYPE = {content.value}",
                        ),
                    )
                )
                continue
            if rules.included_content_types and content not in rules.included_content_types:
                continue
            result.append(item)
        return result

    @staticmethod
    def _apply_refinement(
        items: list[FilteredGame],
        rules: FilterRules,
        stage: FilterStage,
        matcher,
    ) -> list[FilteredGame]:
        selected = ArcadeFilterEngine._selection_for_stage(rules, stage)
        if not selected:
            return items
        return [item for item in items if matcher(item.classification, selected)]

    @staticmethod
    def _selection_for_stage(rules: FilterRules, stage: FilterStage):
        return {
            FilterStage.GENRE: rules.included_genres,
            FilterStage.HARDWARE: rules.included_hardware,
            FilterStage.MANUFACTURER: rules.included_manufacturers,
            FilterStage.SERIES: rules.included_series,
            FilterStage.INPUT: rules.included_inputs,
            FilterStage.WHEEL: rules.included_wheel_angles,
        }.get(stage, frozenset())

    @staticmethod
    def _match_genre(classification: ArcadeClassification, selected: frozenset[ArcadeGenre]) -> bool:
        return bool(set(classification.genres) & set(selected))

    @staticmethod
    def _match_hardware(classification: ArcadeClassification, selected: frozenset[ArcadeHardwareFamily]) -> bool:
        return bool(set(classification.hardware) & set(selected))

    @staticmethod
    def _match_manufacturer(classification: ArcadeClassification, selected: frozenset[str]) -> bool:
        return classification.manufacturer is not None and classification.manufacturer.casefold() in {value.casefold() for value in selected}

    @staticmethod
    def _match_series(classification: ArcadeClassification, selected: frozenset[str]) -> bool:
        return classification.series is not None and classification.series.casefold() in {value.casefold() for value in selected}

    @staticmethod
    def _match_input(classification: ArcadeClassification, selected: frozenset[ArcadeInputType]) -> bool:
        return bool(set(classification.inputs) & set(selected))

    @staticmethod
    def _match_wheel(classification: ArcadeClassification, selected: frozenset[WheelAngleClass]) -> bool:
        return classification.wheel_angle in selected


__all__ = [
    "ArcadeFilterEngine",
    "FilterDecision",
    "FilterResult",
    "FilterRules",
    "FilterStage",
    "FilterTrace",
    "FilteredGame",
]
