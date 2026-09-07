"""Classificacao semantica usada pelo pipeline do Arcade Studio.

A classificacao e deliberadamente separada de ROM status, playability e
selecao. Ela descreve *o que* um titulo e; as regras posteriores decidem se
ele sera incluido ou excluido do conjunto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ArcadeContentType(StrEnum):
    """Tipo de conteudo, usado primeiro para reduzir o catalogo."""

    ARCADE = "arcade"
    MECHANICAL = "mechanical"
    ELECTROMECHANICAL = "electromechanical"
    PACHINKO = "pachinko"
    PACHISLOT = "pachislot"
    QUIZ = "quiz"
    GAMBLING = "gambling"
    FRUIT_MACHINE = "fruit_machine"
    CASINO = "casino"
    TABLETOP = "tabletop"
    HANDHELD = "handheld"
    CONSOLE = "console"
    COMPUTER = "computer"
    ELECTRONIC_GAME = "electronic_game"
    REDEMPTION = "redemption"
    MEDAL = "medal"
    MAHJONG = "mahjong"
    UNKNOWN = "unknown"


class ArcadeGenre(StrEnum):
    """Genero funcional, aplicado depois da limpeza de conteudo."""

    FIGHTING = "fighting"
    SHOOTER = "shooter"
    DANCE = "dance"
    RACING = "racing"
    DRIVING = "driving"
    PLATFORM = "platform"
    BEAT_EM_UP = "beat_em_up"
    SPORTS = "sports"
    ACTION = "action"
    PUZZLE = "puzzle"
    RHYTHM = "rhythm"
    SHOOTING = "shooting"
    MISC = "misc"
    UNKNOWN = "unknown"


class ArcadeHardwareFamily(StrEnum):
    """Familia/plataforma de hardware para refinamento posterior."""

    MAME = "mame"
    CPS1 = "cps1"
    CPS2 = "cps2"
    CPS3 = "cps3"
    NEO_GEO = "neo_geo"
    NEO_GEO_64 = "neo_geo_64"
    NAOMI = "naomi"
    NAOMI_2 = "naomi_2"
    MODEL_1 = "model_1"
    MODEL_2 = "model_2"
    MODEL_3 = "model_3"
    UNKNOWN = "unknown"


class ArcadeInputType(StrEnum):
    """Tipo de controle exigido ou recomendado pelo titulo."""

    JOYSTICK = "joystick"
    BUTTONS_2 = "buttons_2"
    BUTTONS_3 = "buttons_3"
    BUTTONS_4 = "buttons_4"
    BUTTONS_6 = "buttons_6"
    BUTTONS_8 = "buttons_8"
    ANALOG = "analog"
    LIGHTGUN = "lightgun"
    TRACKBALL = "trackball"
    DIAL = "dial"
    PEDALS = "pedals"
    STEERING_WHEEL = "steering_wheel"
    FLIGHT_STICK = "flight_stick"
    DANCE_PAD = "dance_pad"
    UNKNOWN = "unknown"


class WheelAngleClass(StrEnum):
    """Faixas padronizadas para volantes de arcade.

    O valor representa o curso total de giro. O catalogo pode futuramente
    fornecer um valor exato; ate la, a classe permanece UNKNOWN.
    """

    DEG_240 = "240"
    DEG_270 = "270"
    DEG_360 = "360"
    DEG_540 = "540"
    DEG_720 = "720"
    DEG_900 = "900"
    DEG_1080 = "1080"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class ArcadeClassification:
    """Resultado normalizado da classificacao de um titulo."""

    content_type: ArcadeContentType = ArcadeContentType.UNKNOWN
    genres: tuple[ArcadeGenre, ...] = ()
    hardware: tuple[ArcadeHardwareFamily, ...] = ()
    inputs: tuple[ArcadeInputType, ...] = ()
    wheel_angle: WheelAngleClass = WheelAngleClass.UNKNOWN
    manufacturer: str | None = None
    series: str | None = None
    tags: tuple[str, ...] = ()
    evidence: dict[str, object] = field(default_factory=dict)


__all__ = [
    "ArcadeClassification",
    "ArcadeContentType",
    "ArcadeGenre",
    "ArcadeHardwareFamily",
    "ArcadeInputType",
    "WheelAngleClass",
]
