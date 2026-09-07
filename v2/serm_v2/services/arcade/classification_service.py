"""Servico de classificacao semantica do Arcade Studio.

A classificacao usa primeiro evidencias estruturadas do catalogo e depois
aliases controlados. Ela nao tenta adivinhar dados que a fonte nao fornece.

Para MAME, a fonte primaria recomendada e o ``-listxml``: a documentacao do
MAME descreve ``input``/``control`` e seus atributos, incluindo tipo, botoes,
ways, limites, sensibilidade, keydelta e reverse. O servico aceita tanto essa
estrutura quanto os formatos normalizados usados pelos providers do SERM.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import re

from ...models.arcade import ArcadeGame, ArcadePlatform
from ...models.arcade_classification import (
    ArcadeClassification,
    ArcadeContentType,
    ArcadeGenre,
    ArcadeHardwareFamily,
    ArcadeInputType,
    WheelAngleClass,
)


class ArcadeClassificationService:
    """Normaliza metadados de :class:`ArcadeGame` em facetas filtraveis."""

    _CONTENT_ALIASES: dict[ArcadeContentType, frozenset[str]] = {
        ArcadeContentType.MECHANICAL: frozenset({"mechanical", "mechanical game"}),
        ArcadeContentType.ELECTROMECHANICAL: frozenset({"electromechanical", "electromechanical game"}),
        ArcadeContentType.PACHINKO: frozenset({"pachinko"}),
        ArcadeContentType.PACHISLOT: frozenset({"pachislot", "pachi slot", "pachi-slot"}),
        ArcadeContentType.QUIZ: frozenset({"quiz", "quiz game"}),
        ArcadeContentType.GAMBLING: frozenset({"gambling", "betting"}),
        ArcadeContentType.FRUIT_MACHINE: frozenset({"fruit machine", "fruit machines", "fruit_machine", "slot machine", "slots"}),
        ArcadeContentType.CASINO: frozenset({"casino", "casino game"}),
        ArcadeContentType.TABLETOP: frozenset({"tabletop", "table top"}),
        ArcadeContentType.HANDHELD: frozenset({"handheld", "portable", "portable game"}),
        ArcadeContentType.CONSOLE: frozenset({"console", "home console"}),
        ArcadeContentType.COMPUTER: frozenset({"computer", "home computer", "personal computer"}),
        ArcadeContentType.ELECTRONIC_GAME: frozenset({"electronic game", "electronic games"}),
        ArcadeContentType.REDEMPTION: frozenset({"redemption", "redemption game"}),
        ArcadeContentType.MEDAL: frozenset({"medal", "medal game", "medal games"}),
        ArcadeContentType.MAHJONG: frozenset({"mahjong", "mahjong game"}),
        ArcadeContentType.ARCADE: frozenset({"arcade", "arcade game"}),
    }

    _GENRE_ALIASES: dict[ArcadeGenre, frozenset[str]] = {
        ArcadeGenre.FIGHTING: frozenset({"fighting", "fighter", "fighting game"}),
        ArcadeGenre.SHOOTER: frozenset({"shooter", "shooters", "shoot em up", "shoot'em up", "shmup"}),
        ArcadeGenre.DANCE: frozenset({"dance", "dancing", "dance game"}),
        ArcadeGenre.RACING: frozenset({"racing", "race"}),
        ArcadeGenre.DRIVING: frozenset({"driving", "driving game"}),
        ArcadeGenre.PLATFORM: frozenset({"platform", "platformer"}),
        ArcadeGenre.BEAT_EM_UP: frozenset({"beat'em up", "beat em up", "beat-em-up", "beat them up"}),
        ArcadeGenre.SPORTS: frozenset({"sports", "sport", "sport game"}),
        ArcadeGenre.ACTION: frozenset({"action", "action game"}),
        ArcadeGenre.PUZZLE: frozenset({"puzzle", "puzzle game"}),
        ArcadeGenre.RHYTHM: frozenset({"rhythm", "rhythm game"}),
        ArcadeGenre.SHOOTING: frozenset({"shooting", "light gun", "lightgun", "gun game"}),
        ArcadeGenre.MISC: frozenset({"misc", "miscellaneous"}),
    }

    _HARDWARE_ALIASES: dict[ArcadeHardwareFamily, frozenset[str]] = {
        ArcadeHardwareFamily.CPS1: frozenset({"cps1", "cps-1", "cps 1", "cps-1 system"}),
        ArcadeHardwareFamily.CPS2: frozenset({"cps2", "cps-2", "cps 2", "cps-2 system"}),
        ArcadeHardwareFamily.CPS3: frozenset({"cps3", "cps-3", "cps 3", "cps-3 system"}),
        ArcadeHardwareFamily.NEO_GEO_64: frozenset({"neo geo 64", "neogeo 64", "neo-geo 64", "hyper neo geo 64"}),
        ArcadeHardwareFamily.NEO_GEO: frozenset({"neo geo", "neogeo", "neo-geo", "neo geo mvs", "neo geo aes"}),
        ArcadeHardwareFamily.NAOMI_2: frozenset({"naomi 2", "naomi2", "naomi 2 system"}),
        ArcadeHardwareFamily.NAOMI: frozenset({"naomi", "sega naomi"}),
        ArcadeHardwareFamily.MODEL_1: frozenset({"model 1", "model1", "sega model 1"}),
        ArcadeHardwareFamily.MODEL_2: frozenset({"model 2", "model2", "sega model 2"}),
        ArcadeHardwareFamily.MODEL_3: frozenset({"model 3", "model3", "sega model 3", "supermodel"}),
    }

    _CONTROL_ALIASES: dict[str, ArcadeInputType] = {
        "stick": ArcadeInputType.JOYSTICK,
        "joystick": ArcadeInputType.JOYSTICK,
        "joy": ArcadeInputType.JOYSTICK,
        "doublejoy": ArcadeInputType.JOYSTICK,
        "triplejoy": ArcadeInputType.JOYSTICK,
        "pedal": ArcadeInputType.PEDALS,
        "pedals": ArcadeInputType.PEDALS,
        "dial": ArcadeInputType.DIAL,
        "paddle": ArcadeInputType.STEERING_WHEEL,
        "positional": ArcadeInputType.ANALOG,
        "adstick": ArcadeInputType.ANALOG,
        "analog stick": ArcadeInputType.ANALOG,
        "analog": ArcadeInputType.ANALOG,
        "trackball": ArcadeInputType.TRACKBALL,
        "lightgun": ArcadeInputType.LIGHTGUN,
        "light gun": ArcadeInputType.LIGHTGUN,
        "only_buttons": ArcadeInputType.BUTTONS_2,
        "buttons": ArcadeInputType.BUTTONS_2,
        "dance pad": ArcadeInputType.DANCE_PAD,
        "flight stick": ArcadeInputType.FLIGHT_STICK,
        "flightstick": ArcadeInputType.FLIGHT_STICK,
        "steering wheel": ArcadeInputType.STEERING_WHEEL,
        "wheel": ArcadeInputType.STEERING_WHEEL,
    }

    _WHEEL_KEYS = (
        "wheel_angle",
        "wheel_degrees",
        "steering_angle",
        "steering_degrees",
        "steering_wheel_angle",
        "steering_wheel_degrees",
        "rotation_angle",
        "rotation_degrees",
        "max_wheel_angle",
        "max_steering_angle",
    )

    _BUTTON_KEYS = ("buttons", "button_count", "buttons_count", "input_buttons", "num_buttons")

    def classify(self, game: ArcadeGame) -> ArcadeClassification:
        """Classifica um titulo sem alterar o objeto de catalogo."""
        metadata = self._flatten_metadata(game)
        categories = self._normalized_values(metadata.get("categories"))
        tokens = set(categories)

        content_type = self._first_match(self._CONTENT_ALIASES, tokens)
        if content_type is None and self._truthy(metadata.get("ismechanical")):
            content_type = ArcadeContentType.MECHANICAL

        genres = self._all_matches(self._GENRE_ALIASES, tokens)
        hardware = self._all_matches(self._HARDWARE_ALIASES, tokens)
        if game.platform is ArcadePlatform.MAME:
            hardware = (ArcadeHardwareFamily.MAME, *hardware)

        inputs, input_evidence = self._detect_inputs(tokens, metadata)
        wheel_angle, wheel_evidence = self._detect_wheel_angle(metadata)
        button_type, button_count = self._detect_button_class(metadata)
        if button_type is not None and button_type not in inputs:
            inputs = (*inputs, button_type)

        manufacturer = self._optional_text(metadata.get("manufacturer"))
        series = self._optional_text(metadata.get("series"))
        tags = tuple(sorted(tokens))

        evidence = {
            "categories": tuple(categories),
            "machine_name": game.machine_name,
            "platform": game.platform.value,
            "ismechanical": self._truthy(metadata.get("ismechanical")),
            "inputs": tuple(input_evidence),
            "button_count": button_count,
            "wheel_angle": wheel_evidence,
        }

        return ArcadeClassification(
            content_type=content_type or ArcadeContentType.UNKNOWN,
            genres=genres,
            hardware=self._unique(hardware),
            inputs=self._unique(inputs),
            wheel_angle=wheel_angle,
            manufacturer=manufacturer,
            series=series,
            tags=tags,
            evidence=evidence,
        )

    @staticmethod
    def _flatten_metadata(game: ArcadeGame) -> dict[str, object]:
        metadata = dict(game.metadata)
        if game.category:
            existing = metadata.get("categories")
            values = list(existing) if isinstance(existing, (list, tuple, set, frozenset)) else []
            if game.category not in values:
                values.insert(0, game.category)
            if game.subcategory and game.subcategory not in values:
                values.append(game.subcategory)
            metadata["categories"] = values
        return metadata

    @classmethod
    def _normalized_values(cls, value: object) -> list[str]:
        if isinstance(value, Mapping):
            values: Iterable[object] = value.keys()
        elif isinstance(value, (list, tuple, set, frozenset)):
            values = value
        elif value is None:
            values = ()
        else:
            values = (value,)
        return [cls._normalize(str(item)) for item in values if str(item).strip()]

    @staticmethod
    def _normalize(value: str) -> str:
        value = value.casefold().replace("_", " ")
        value = re.sub(r"[\u2010-\u2015]", "-", value)
        value = re.sub(r"\s*-\s*", "-", value)
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

    @classmethod
    def _detect_inputs(
        cls, tokens: set[str], metadata: Mapping[str, object]
    ) -> tuple[tuple[ArcadeInputType, ...], list[str]]:
        detected: list[ArcadeInputType] = []
        evidence: list[str] = []

        input_values = cls._normalized_values(metadata.get("inputs"))
        control_values = cls._collect_control_values(metadata)
        names = tokens.union(input_values).union(control_values)

        for control in control_values:
            mapped = cls._CONTROL_ALIASES.get(control)
            if mapped is not None:
                detected.append(mapped)
                evidence.append(f"control:{control}")

        explicit_aliases = {
            ArcadeInputType.STEERING_WHEEL: {"steering wheel", "wheel", "steering"},
            ArcadeInputType.LIGHTGUN: {"light gun", "lightgun"},
            ArcadeInputType.TRACKBALL: {"trackball", "track ball"},
            ArcadeInputType.DIAL: {"dial", "spinner"},
            ArcadeInputType.PEDALS: {"pedals", "pedal", "gas pedal", "brake pedal"},
            ArcadeInputType.FLIGHT_STICK: {"flight stick", "flightstick", "yoke"},
            ArcadeInputType.DANCE_PAD: {"dance pad", "dance platform", "dance mat"},
            ArcadeInputType.ANALOG: {"analog", "analogue", "analog stick", "analog axis"},
            ArcadeInputType.JOYSTICK: {"joystick", "joy stick"},
        }
        for input_type, aliases in explicit_aliases.items():
            if names.intersection(aliases):
                detected.append(input_type)
                evidence.append(f"alias:{input_type.value}")

        return cls._unique(detected), evidence

    @classmethod
    def _collect_control_values(cls, metadata: Mapping[str, object]) -> list[str]:
        raw_values: list[object] = []
        for key in ("controls", "control", "input_controls", "input_types"):
            value = metadata.get(key)
            if isinstance(value, Mapping):
                raw_values.extend(value.keys())
            elif isinstance(value, (list, tuple, set, frozenset)):
                raw_values.extend(value)
            elif value is not None:
                raw_values.append(value)

        controls: list[str] = []
        for value in raw_values:
            if isinstance(value, Mapping):
                control = value.get("type") or value.get("control") or value.get("name")
                if control is not None:
                    controls.append(cls._normalize(str(control)))
            else:
                controls.append(cls._normalize(str(value)))
        return controls

    @classmethod
    def _detect_button_class(
        cls, metadata: Mapping[str, object]
    ) -> tuple[ArcadeInputType | None, int | None]:
        counts: list[int] = []
        for key in cls._BUTTON_KEYS:
            counts.extend(cls._extract_ints(metadata.get(key)))
        counts.extend(cls._extract_button_counts(metadata.get("controls")))
        counts.extend(cls._extract_button_counts(metadata.get("control")))

        valid = [value for value in counts if 1 <= value <= 32]
        if not valid:
            return None, None
        maximum = max(valid)
        classes = {
            2: ArcadeInputType.BUTTONS_2,
            3: ArcadeInputType.BUTTONS_3,
            4: ArcadeInputType.BUTTONS_4,
            6: ArcadeInputType.BUTTONS_6,
            8: ArcadeInputType.BUTTONS_8,
        }
        return classes.get(maximum), maximum

    @classmethod
    def _extract_button_counts(cls, value: object) -> list[int]:
        if isinstance(value, Mapping):
            result: list[int] = []
            if "buttons" in value:
                result.extend(cls._extract_ints(value.get("buttons")))
            return result
        if isinstance(value, (list, tuple, set, frozenset)):
            result = []
            for item in value:
                result.extend(cls._extract_button_counts(item))
            return result
        return []

    @staticmethod
    def _extract_ints(value: object) -> list[int]:
        if isinstance(value, bool) or value is None:
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, float) and value.is_integer():
            return [int(value)]
        if isinstance(value, str):
            match = re.fullmatch(r"\s*(\d+)\s*", value)
            return [int(match.group(1))] if match else []
        return []

    @classmethod
    def _detect_wheel_angle(
        cls, metadata: Mapping[str, object]
    ) -> tuple[WheelAngleClass, str | None]:
        for key in cls._WHEEL_KEYS:
            value = metadata.get(key)
            angle = cls._parse_angle(value)
            if angle is not None:
                return cls._wheel_class(angle), f"{key}:{angle}"

        # A nested control may carry an explicit wheel/rotation field. Do not
        # derive degrees from MAME minimum/maximum: those are input ranges,
        # not documented physical steering lock values.
        for value in (metadata.get("controls"), metadata.get("control")):
            angle = cls._find_nested_angle(value)
            if angle is not None:
                return cls._wheel_class(angle), f"control:{angle}"

        return WheelAngleClass.UNKNOWN, None

    @classmethod
    def _find_nested_angle(cls, value: object) -> float | None:
        if isinstance(value, Mapping):
            for key in cls._WHEEL_KEYS:
                angle = cls._parse_angle(value.get(key))
                if angle is not None:
                    return angle
            for child in value.values():
                angle = cls._find_nested_angle(child)
                if angle is not None:
                    return angle
        elif isinstance(value, (list, tuple, set, frozenset)):
            for child in value:
                angle = cls._find_nested_angle(child)
                if angle is not None:
                    return angle
        return None

    @staticmethod
    def _parse_angle(value: object) -> float | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value) if 0 < float(value) <= 1440 else None
        text = str(value).casefold().strip()
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:°|deg(?:ree)?s?)?", text)
        if not match:
            return None
        angle = float(match.group(1))
        return angle if 0 < angle <= 1440 else None

    @staticmethod
    def _wheel_class(angle: float) -> WheelAngleClass:
        mapping = {
            240: WheelAngleClass.DEG_240,
            270: WheelAngleClass.DEG_270,
            360: WheelAngleClass.DEG_360,
            540: WheelAngleClass.DEG_540,
            720: WheelAngleClass.DEG_720,
            900: WheelAngleClass.DEG_900,
            1080: WheelAngleClass.DEG_1080,
        }
        rounded = int(round(angle))
        return mapping.get(rounded, WheelAngleClass.UNKNOWN)

    @staticmethod
    def _truthy(value: object) -> bool:
        if isinstance(value, str):
            return value.casefold().strip() in {"1", "true", "yes", "y"}
        return bool(value)

    @staticmethod
    def _optional_text(value: object) -> str | None:
        text = str(value).strip() if value is not None else ""
        return text or None

    @staticmethod
    def _unique(values: Sequence):
        result = []
        for value in values:
            if value not in result:
                result.append(value)
        return tuple(result)


__all__ = ["ArcadeClassificationService"]
