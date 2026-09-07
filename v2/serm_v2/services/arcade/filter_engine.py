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
    """Resultado da avaliação de um título."""

    INCLUDED = "included"
    EXCLUDED = "excluded"


class FilterStage(StrEnum):
    """Camadas aplicadas pelo motor, na ordem do pipeline."""

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
    """Regras declarativas para uma execução do motor.

    O estágio de emulação/playabilidade não é binário. Um título pode estar
    plenamente jogável, funcional com limitações, parcialmente jogável,
    em desenvolvimento, jogável em outro alvo, não jogável ou sem avaliação.
    Quando ``included_playability`` está vazio, todos os estados permanecem.
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
    """Resultado completo, mantendo incluídos e excluídos para auditoria."""

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


Matcher = Callable[[ArcadeClassification, frozenset], bool]


class ArcadeFilterEngine:
    """Aplica o pipeline unificado sem alterar o catálogo de origem."""

    def __init__(self, classifier: ArcadeClassificationService | None = None) -> None:
        self._classifier = classifier or ArcadeClassificationService()

    def apply(
        self,
        games: Iterable[ArcadeGame],
        rules: FilterRules | None = None,
    ) -> FilterResult:
        active_rules = rules or FilterRules()
        items = [
            FilteredGame(
                game,
                self._classifier.classify(game),
                FilterTrace(FilterDecision.INCLUDED),
            )
            for game in games
        ]
        total_input = len(items)
        counts: dict[FilterStage, int] = {}
        excluded: list[FilteredGame] = []

        items, removed = self._apply_content(items, active_rules)
        excluded.extend(removed)
        counts[FilterStage.CONTENT] = len(items)

        items, removed = self._apply_refinement(
            items,
            active_rules,
            FilterStage.PLAYABILITY,
            self._match_playability,
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
    def _apply_content(
        items: list[FilteredGame], rules: FilterRules
    ) -> tuple[list[FilteredGame], list[FilteredGame]]:
        result: list[FilteredGame] = []
        excluded: list[FilteredGame] = []
        for item in items:
            content = item.classification.content_type
            if content in rules.excluded_content_types:
                excluded.append(
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
            elif rules.included_content_types and content not in rules.included_content_types:
                excluded.append(
                    FilteredGame(
                        item.game,
                        item.classification,
                        FilterTrace(
                            FilterDecision.EXCLUDED,
                            FilterStage.CONTENT,
                            "include_content",
                            f"CONTENT_TYPE = {content.value} não está entre os tipos incluídos",
                        ),
                    )
                )
            else:
                result.append(item)
        return result, excluded

    @staticmethod
    def _apply_refinement(
        items: list[FilteredGame],
        rules: FilterRules,
        stage: FilterStage,
        matcher: Matcher,
    ) -> tuple[list[FilteredGame], list[FilteredGame]]:
        selected = ArcadeFilterEngine._selection_for_stage(rules, stage)
        if not selected:
            return items, []
        result: list[FilteredGame] = []
        excluded: list[FilteredGame] = []
        for item in items:
            if matcher(item.classification, selected):
                result.append(item)
            else:
                excluded.append(
                    FilteredGame(
                        item.game,
                        item.classification,
                        FilterTrace(
                            FilterDecision.EXCLUDED,
                            stage,
                            f"include_{stage.value}",
                            f"não atende ao filtro {stage.value}",
                        ),
                    )
                )
        return result, excluded

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
    def _match_playability(
        classification: ArcadeClassification,
        selected: frozenset[PlayabilityStatus],
    ) -> bool:
        status = classification.evidence.get("playability")
        if isinstance(status, PlayabilityStatus):
            return status in selected
        if status is not None:
            try:
                return PlayabilityStatus(str(status)) in selected
            except ValueError:
                pass
        return False

    @staticmethod
    def _match_genre(classification: ArcadeClassification, selected: frozenset[ArcadeGenre]) -> bool:
        return bool(set(classification.genres) & set(selected))

    @staticmethod
    def _match_hardware(classification: ArcadeClassification, selected: frozenset[ArcadeHardwareFamily]) -> bool:
        return bool(set(classification.hardware) & set(selected))

    @staticmethod
    def _match_manufacturer(classification: ArcadeClassification, selected: frozenset[str]) -> bool:
        values = {value.casefold() for value in selected}
        return classification.manufacturer is not None and classification.manufacturer.casefold() in values

    @staticmethod
    def _match_series(classification: ArcadeClassification, selected: frozenset[str]) -> bool:
        values = {value.casefold() for value in selected}
        return classification.series is not None and classification.series.casefold() in values

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
