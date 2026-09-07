"""Motor unificado de filtros em camadas do Arcade Studio."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from ...models.arcade import ArcadeGame, PlayabilityStatus
from ...models.arcade_classification import ArcadeClassification, ArcadeContentType, ArcadeGenre, ArcadeHardwareFamily, ArcadeInputType, WheelAngleClass
from .classification_service import ArcadeClassificationService


class FilterDecision(StrEnum):
    INCLUDED = "included"
    EXCLUDED = "excluded"


class FilterStage(StrEnum):
    CATLIST = "catlist"
    CONTENT = "content"
    PLAYABILITY = "playability"
    STRUCTURAL = "structural"
    GENRE = "genre"
    HARDWARE = "hardware"
    MANUFACTURER = "manufacturer"
    SERIES = "series"
    INPUT = "input"
    WHEEL = "wheel"


@dataclass(frozen=True, slots=True)
class FilterRules:
    """Regras declarativas do motor.

    PlayabilityStatus representa os vários estágios de emulação e nunca é
    reduzido a um simples working/not-working. Filtros ``included_*`` são
    seleções OR dentro da própria dimensão; dimensões diferentes são AND.
    Exclusões explícitas têm precedência.
    """

    excluded_machine_names: frozenset[str] = frozenset()
    excluded_content_types: frozenset[ArcadeContentType] = frozenset()
    included_content_types: frozenset[ArcadeContentType] = frozenset()
    included_playability: frozenset[PlayabilityStatus] = frozenset()
    include_bios: bool = False
    include_devices: bool = False
    include_optional: bool = True
    working_only: bool = False
    parents_only: bool = False
    excluded_genres: frozenset[ArcadeGenre] = frozenset()
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
    """Aplica todo o pipeline sem alterar o catálogo de origem."""

    def __init__(self, classifier: ArcadeClassificationService | None = None) -> None:
        self._classifier = classifier or ArcadeClassificationService()

    def apply(self, games: Iterable[ArcadeGame], rules: FilterRules | None = None) -> FilterResult:
        active_rules = rules or FilterRules()
        items = [FilteredGame(game, self._classifier.classify(game), FilterTrace(FilterDecision.INCLUDED)) for game in games]
        total_input = len(items)
        counts: dict[FilterStage, int] = {}
        excluded: list[FilteredGame] = []

        for stage, function in (
            (FilterStage.CATLIST, self._apply_catlist),
            (FilterStage.CONTENT, self._apply_content),
            (FilterStage.PLAYABILITY, self._apply_playability),
            (FilterStage.STRUCTURAL, self._apply_structural),
            (FilterStage.GENRE, self._apply_genre),
        ):
            items, removed = function(items, active_rules)
            excluded.extend(removed)
            counts[stage] = len(items)

        for stage, matcher in (
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
    def _excluded(item: FilteredGame, stage: FilterStage, rule: str, reason: str) -> FilteredGame:
        return FilteredGame(item.game, item.classification, FilterTrace(FilterDecision.EXCLUDED, stage, rule, reason))

    @staticmethod
    def _apply_catlist(items, rules):
        if not rules.excluded_machine_names:
            return items, []
        keep, removed = [], []
        for item in items:
            if item.game.machine_name in rules.excluded_machine_names:
                removed.append(ArcadeFilterEngine._excluded(item, FilterStage.CATLIST, "exclude_catlist", f"machine = {item.game.machine_name} foi explicitamente excluída pelo CATLIST"))
            else:
                keep.append(item)
        return keep, removed

    @staticmethod
    def _apply_content(items, rules):
        keep, removed = [], []
        for item in items:
            content = item.classification.content_type
            if content in rules.excluded_content_types:
                removed.append(ArcadeFilterEngine._excluded(item, FilterStage.CONTENT, f"exclude_content:{content.value}", f"CONTENT_TYPE = {content.value}"))
            elif rules.included_content_types and content not in rules.included_content_types:
                removed.append(ArcadeFilterEngine._excluded(item, FilterStage.CONTENT, "include_content", f"CONTENT_TYPE = {content.value} não está entre os tipos incluídos"))
            else:
                keep.append(item)
        return keep, removed

    @staticmethod
    def _apply_playability(items, rules):
        if not rules.included_playability:
            return items, []
        keep, removed = [], []
        for item in items:
            if item.game.playability in rules.included_playability:
                keep.append(item)
            else:
                removed.append(ArcadeFilterEngine._excluded(item, FilterStage.PLAYABILITY, "include_playability", f"playability = {item.game.playability.value} não está entre os estados incluídos"))
        return keep, removed

    @staticmethod
    def _apply_structural(items, rules):
        keep, removed = [], []
        for item in items:
            game = item.game
            if not rules.include_bios and game.is_bios:
                removed.append(ArcadeFilterEngine._excluded(item, FilterStage.STRUCTURAL, "exclude_bios", "BIOS não incluído")); continue
            if not rules.include_devices and game.is_device:
                removed.append(ArcadeFilterEngine._excluded(item, FilterStage.STRUCTURAL, "exclude_devices", "device não incluído")); continue
            if not rules.include_optional and ArcadeFilterEngine._truthy(game.metadata.get("optional")):
                removed.append(ArcadeFilterEngine._excluded(item, FilterStage.STRUCTURAL, "exclude_optional", "item opcional não incluído")); continue
            if rules.working_only and game.working is not True:
                removed.append(ArcadeFilterEngine._excluded(item, FilterStage.STRUCTURAL, "working_only", "item marcado como não funcional pelo catálogo")); continue
            if rules.parents_only and game.is_clone:
                removed.append(ArcadeFilterEngine._excluded(item, FilterStage.STRUCTURAL, "parents_only", "clone excluído pela política de pais")); continue
            keep.append(item)
        return keep, removed

    @staticmethod
    def _apply_genre(items, rules):
        keep, removed = [], []
        for item in items:
            genres = set(item.classification.genres)
            if genres & set(rules.excluded_genres):
                genre = next(iter(genres & set(rules.excluded_genres))
                removed.append(ArcadeFilterEngine._excluded(item, FilterStage.GENRE, f"exclude_genre:{genre.value}", f"GENRE = {genre.value}")); continue
            if rules.included_genres and not genres & set(rules.included_genres):
                removed.append(ArcadeFilterEngine._excluded(item, FilterStage.GENRE, "include_genre", "não atende ao filtro genre")); continue
            keep.append(item)
        return keep, removed

    @staticmethod
    def _apply_refinement(items, rules, stage, matcher):
        selected = {FilterStage.HARDWARE: rules.included_hardware, FilterStage.MANUFACTURER: rules.included_manufacturers, FilterStage.SERIES: rules.included_series, FilterStage.INPUT: rules.included_inputs, FilterStage.WHEEL: rules.included_wheel_angles}.get(stage, frozenset())
        if not selected:
            return items, []
        keep, removed = [], []
        for item in items:
            if matcher(item, selected):
                keep.append(item)
            else:
                removed.append(ArcadeFilterEngine._excluded(item, stage, f"include_{stage.value}", f"não atende ao filtro {stage.value}"))
        return keep, removed

    @staticmethod
    def _match_hardware(item, selected): return bool(set(item.classification.hardware) & set(selected))
    @staticmethod
    def _match_manufacturer(item, selected): return item.classification.manufacturer is not None and item.classification.manufacturer.casefold() in {value.casefold() for value in selected}
    @staticmethod
    def _match_series(item, selected): return item.classification.series is not None and item.classification.series.casefold() in {value.casefold() for value in selected}
    @staticmethod
    def _match_input(item, selected): return bool(set(item.classification.inputs) & set(selected))
    @staticmethod
    def _match_wheel(item, selected): return item.classification.wheel_angle in selected
    @staticmethod
    def _truthy(value): return str(value).casefold() in {"yes", "true", "1"}


__all__ = ["ArcadeFilterEngine", "FilterDecision", "FilterResult", "FilterRules", "FilterStage", "FilterTrace", "FilteredGame"]
