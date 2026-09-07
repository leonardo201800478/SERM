"""Servico de classificacao do Arcade Studio.

A ordem deste servico e intencional:
1. identificar o tipo de conteudo e eliminar ruido;
2. identificar genero;
3. identificar hardware/familia;
4. identificar controles e requisitos especiais.

Somente metadados disponiveis no catalogo sao usados. Quando a fonte nao
possui evidencia suficiente, o resultado permanece UNKNOWN em vez de inferir
uma classificacao potencialmente errada.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import re

from ...models.arcade import ArcadeGame
from ...models.arcade_classification import (
    ArcadeClassification,
    ArcadeContentType,
    ArcadeGenre,
    ArcadeHardwareFamily,
    ArcadeInputType,
)


class ArcadeClassificationService:
    """Normaliza metadados de um :class:`ArcadeGame` em facetas filtraveis."""

    _CONTENT_ALIASES: dict[ArcadeContentType, frozenset[str]] = {
        ArcadeContentType.MECHANICAL: frozenset({"mechanical", "mechanical game"}),
        ArcadeContentType.ELECTROMECHANICAL: frozenset({"electromechanical", "electromechanical game"}),
        ArcadeContentType.PACHINKO: frozenset({"pachinko"}),
        ArcadeContentType.PACHISLOT: frozenset({"pachislot", "pachi-slot"}),
        ArcadeContentType.QUIZ: frozenset({"quiz"}),
        ArcadeContentType.GAMBLING: frozenset({"gambling", "betting"}),
        ArcadeContentType.FRUIT_MACHINE: frozenset({"fruit machine", "fruit machines", "fruit_machine"}),
        ArcadeContentType.CASINO: frozenset({"casino", "casino game"}),
        ArcadeContentType.TABLETOP: frozenset({"tabletop", "table top"}),
        ArcadeContentType.HANDHELD: frozenset({"handheld", "portable"}),
        ArcadeContentType.CONSOLE: frozenset({"console", "home console"}),
        ArcadeContentType.COMPUTER: frozenset({"computer", "home computer"}),
        ArcadeContentType.ELECTRONIC_GAME: frozenset({"electronic game"}),
        ArcadeContentType.REDEMPTION: frozenset({"redemption"}),
        ArcadeContentType.MEDAL: frozenset({"medal", "medal game"}),
        ArcadeContentType.MAHJONG: frozenset({"mahjong", "mahjong game"}),
        ArcadeContentType.ARCADE: frozenset({"arcade", "arcade game"}),
    }

    _GENRE_ALIASES: dict[ArcadeGenre, frozenset[str]] = {
        ArcadeGenre.FIGHTING: frozenset({"fighting", "fighter"}),
        ArcadeGenre.SHOOTER: frozenset({"shooter", "shooters"}),
        ArcadeGenre.DANCE: frozenset({"dance", "dancing"}),
        ArcadeGenre.RACING: frozenset({"racing"}),
        ArcadeGenre.DRIVING: frozenset({"driving"}),
        ArcadeGenre.PLATFORM: frozenset({"platform", "platformer"}),
        ArcadeGenre.BEAT_EM_UP: frozenset({"beat'em up", "beat em up", "beat-em-up"}),
        ArcadeGenre.SPORTS: frozenset({"sports", "sport"}),
        ArcadeGenre.ACTION: frozenset({"action"}),
        ArcadeGenre.PUZZLE: frozenset({"puzzle"}),
        ArcadeGenre.RHYTHM: frozenset({"rhythm"}),
        ArcadeGenre.SHOOTING: frozenset({"shooting", "light gun", "lightgun"}),
    }

    _HARDWARE_ALIASES: dict[ArcadeHardwareFamily, frozenset[str]] = {
        ArcadeHardwareFamily.CPS1: frozenset({"cps1", "cps-1"}),
        ArcadeHardwareFamily.CPS2: frozenset({"cps2", "cps-2"}),
        ArcadeHardwareFamily.CPS3: frozenset({"cps3", "cps-3"}),
        ArcadeHardwareFamily.NEO_GEO: frozenset({"neo geo", "neogeo", "neo-geo"}),
        ArcadeHardwareFamily.NEO_GEO_64: frozenset({"neo geo 64", "neogeo 64", "neo-geo 64"}),
        ArcadeHardwareFamily.NAOMI: frozenset({"naomi"}),
        ArcadeHardwareFamily.NAOMI_2: frozenset({"naomi 2", "naomi2"}),
        ArcadeHardwareFamily.MODEL_1: frozenset({"model 1", "model1"}),
        ArcadeHardwareFamily.MODEL_2: frozenset({"model 2", "model2"}),
        ArcadeHardwareFamily.MODEL_3: frozenset({"model 3", "model3"}),
    }

    def classify(self, game: ArcadeGame) -> ArcadeClassification:
        """Classifica um titulo sem alterar o objeto de catalogo."""
        metadata = self._flatten_metadata(game)
        categories = self._normalized_values(metadata.get("categories"))
        tokens = set(categories)

        content_type = self._first_match(self._CONTENT_ALIASES, tokens)
        if content_type is None and bool(game.metadata.get("ismechanical")):
            content_type = ArcadeContentType.MECHANICAL

        genres = self._all_matches(self._GENRE_ALIASES, tokens)
        hardware = self._all_matches(self._HARDWARE_ALIASES, tokens)
        inputs = self._detect_inputs(tokens, metadata)

        manufacturer = self._optional_text(metadata.get("manufacturer"))
        series = self._optional_text(metadata.get("series"))
        tags = tuple(sorted(tokens))

        return ArcadeClassification(
            content_type=content_type or ArcadeContentType.UNKNOWN,
            genres=genres,
            hardware=hardware,
            inputs=inputs,
            manufacturer=manufacturer,
            series=series,
            tags=tags,
            evidence={
                "categories": tuple(categories),
                "machine_name": game.machine_name,
                "platform": game.platform.value,
                "ismechanical": bool(game.metadata.get("ismechanical")),
            },
        )

    @staticmethod
    def _flatten_metadata(game: ArcadeGame) -> dict[str, object]:
        metadata = dict(game.metadata)
        if game.category:
            existing = metadata.get("categories")
            values = list(existing) if isinstance(existing, (list, tuple)) else []
            values.insert(0, game.category)
            if game.subcategory:
                values.append(game.subcategory)
            metadata["categories"] = values
        return metadata

    @classmethod
    def _normalized_values(cls, value: object) -> list[str]:
        if isinstance(value, (list, tuple, set, frozenset)):
            values: Iterable[object] = value
        elif value is None:
            values = ()
        else:
            values = (value,)
        return [cls._normalize(str(item)) for item in values if str(item).strip()]

    @staticmethod
    def _normalize(value: str) -> str:
        value = value.casefold().replace("_", " ").replace("-", "-")
        value = re.sub(r"\s+", " ", value).strip()
        return value

    @staticmethod
    def _first_match(
        aliases: Mapping[object, frozenset[str]], values: set[str]
    ) -> object | None:
        for classification, aliases_for_class in aliases.items():
            if values.intersection(aliases_for_class):
                return classification
        return None

    @staticmethod
    def _all_matches(
        aliases: Mapping[object, frozenset[str]], values: set[str]
    ) -> tuple:
        return tuple(
            classification
            for classification, aliases_for_class in aliases.items()
            if values.intersection(aliases_for_class)
        )

    @staticmethod
    def _detect_inputs(tokens: set[str], metadata: Mapping[str, object]) -> tuple[ArcadeInputType, ...]:
        inputs: list[ArcadeInputType] = []
        input_values = ArcadeClassificationService._normalized_values(metadata.get("inputs"))
        input_tokens = tokens.union(input_values)
        aliases = {
            ArcadeInputType.STEERING_WHEEL: {"steering wheel", "wheel", "steering"},
            ArcadeInputType.LIGHTGUN: {"light gun", "lightgun"},
            ArcadeInputType.TRACKBALL: {"trackball"},
            ArcadeInputType.DIAL: {"dial", "spinner"},
            ArcadeInputType.PEDALS: {"pedals", "pedal"},
            ArcadeInputType.FLIGHT_STICK: {"flight stick", "flightstick"},
            ArcadeInputType.DANCE_PAD: {"dance pad", "dance"},
            ArcadeInputType.ANALOG: {"analog", "analogue"},
        }
        for input_type, names in aliases.items():
            if input_tokens.intersection(names):
                inputs.append(input_type)
        return tuple(inputs)

    @staticmethod
    def _optional_text(value: object) -> str | None:
        text = str(value).strip() if value is not None else ""
        return text or None


__all__ = ["ArcadeClassificationService"]
