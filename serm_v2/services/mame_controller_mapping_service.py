"""Geração de perfis ``ctrlr`` do MAME a partir de perfis lógicos do SERM.

A camada física permanece independente do MAME. Este serviço apenas traduz um
ControlProfile já calibrado para tokens JOYCODE usados pelo MAME e gera um
arquivo ``.cfg`` compatível com a opção ``-ctrlr``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from ..models.input_control import ControlProfile, LogicalControl


@dataclass(frozen=True, slots=True)
class MameMappedControl:
    """Uma entrada lógica do SERM traduzida para uma porta do MAME."""

    mame_type: str
    sequence: str
    logical_control: LogicalControl


class MameControllerMappingService:
    """Traduz perfis físicos calibrados para configuração ``ctrlr`` do MAME."""

    # Primeiro alvo: um único controle arcade, numerado pelo MAME como JOYCODE_1.
    # A estabilização do número via <mapdevice> será adicionada quando tivermos
    # o Device ID efetivamente reportado pelo provider do MAME.
    DEFAULT_CONTROLLER = 1

    @classmethod
    def build_m30_mapping(
        cls,
        profile: ControlProfile,
        controller_number: int = DEFAULT_CONTROLLER,
    ) -> tuple[MameMappedControl, ...]:
        """Converte o perfil calibrado do M30 em controles arcade P1/UI.

        Este é o mapeamento neutro do hardware: os seis botões físicos são
        preservados como A/B/C/X/Y/Z e não são rearranjados para um jogo
        específico. MODE/PAIR não é mapeado porque é função do hardware.
        """
        controls: list[MameMappedControl] = []
        for logical, mame_type in (
            (LogicalControl.DPAD_UP, "P1_JOYSTICK_UP"),
            (LogicalControl.DPAD_DOWN, "P1_JOYSTICK_DOWN"),
            (LogicalControl.DPAD_LEFT, "P1_JOYSTICK_LEFT"),
            (LogicalControl.DPAD_RIGHT, "P1_JOYSTICK_RIGHT"),
            (LogicalControl.FACE_SOUTH, "P1_BUTTON1"),
            (LogicalControl.FACE_EAST, "P1_BUTTON2"),
            (LogicalControl.FACE_WEST, "P1_BUTTON3"),
            (LogicalControl.FACE_NORTH, "P1_BUTTON4"),
            (LogicalControl.FACE_EXTRA_1, "P1_BUTTON5"),
            (LogicalControl.FACE_EXTRA_2, "P1_BUTTON6"),
            (LogicalControl.LEFT_SHOULDER, "P1_BUTTON7"),
            (LogicalControl.RIGHT_SHOULDER, "P1_BUTTON8"),
            (LogicalControl.START, "P1_START"),
            (LogicalControl.SELECT, "COIN1"),
            (LogicalControl.MENU, "UI_MENU"),
        ):
            for element_id in profile.bindings.get(logical, ()):
                token = cls._element_to_joycode(element_id, controller_number)
                if token:
                    controls.append(MameMappedControl(mame_type, token, logical))
        return tuple(controls)

    @classmethod
    def build_m30_street_fighter_ii_mapping(
        cls,
        profile: ControlProfile,
        controller_number: int = DEFAULT_CONTROLLER,
    ) -> tuple[MameMappedControl, ...]:
        """Converte o M30 para o layout clássico de Street Fighter II.

        Layout físico -> portas MAME:

            P1_BUTTON1 = X  (LP)
            P1_BUTTON2 = Y  (MP)
            P1_BUTTON3 = Z  (HP)
            P1_BUTTON4 = A  (LK)
            P1_BUTTON5 = B  (MK)
            P1_BUTTON6 = C  (HK)

        L funciona como 1+2+3 (três socos) e R como 4+5+6 (três chutes).
        O MAME aceita sequências digitais em soma-de-produtos, de modo que
        cada porta recebe ``botão principal OR botão de macro``.
        """
        physical_to_mame = (
            (LogicalControl.FACE_WEST, "P1_BUTTON1"),       # X -> 1
            (LogicalControl.FACE_NORTH, "P1_BUTTON2"),      # Y -> 2
            (LogicalControl.FACE_EXTRA_1, "P1_BUTTON3"),    # Z -> 3
            (LogicalControl.FACE_SOUTH, "P1_BUTTON4"),     # A -> 4
            (LogicalControl.FACE_EAST, "P1_BUTTON5"),      # B -> 5
            (LogicalControl.FACE_EXTRA_2, "P1_BUTTON6"),   # C -> 6
        )
        macros = {
            "P1_BUTTON1": LogicalControl.LEFT_SHOULDER,
            "P1_BUTTON2": LogicalControl.LEFT_SHOULDER,
            "P1_BUTTON3": LogicalControl.LEFT_SHOULDER,
            "P1_BUTTON4": LogicalControl.RIGHT_SHOULDER,
            "P1_BUTTON5": LogicalControl.RIGHT_SHOULDER,
            "P1_BUTTON6": LogicalControl.RIGHT_SHOULDER,
        }

        controls: list[MameMappedControl] = []
        for logical, mame_type in physical_to_mame:
            main_tokens = cls._binding_tokens(profile, logical, controller_number)
            macro_control = macros[mame_type]
            macro_tokens = cls._binding_tokens(profile, macro_control, controller_number)
            sequence = " OR ".join((*main_tokens, *macro_tokens))
            if sequence:
                controls.append(MameMappedControl(mame_type, sequence, logical))

        for logical, mame_type in (
            (LogicalControl.DPAD_UP, "P1_JOYSTICK_UP"),
            (LogicalControl.DPAD_DOWN, "P1_JOYSTICK_DOWN"),
            (LogicalControl.DPAD_LEFT, "P1_JOYSTICK_LEFT"),
            (LogicalControl.DPAD_RIGHT, "P1_JOYSTICK_RIGHT"),
            (LogicalControl.START, "P1_START"),
            (LogicalControl.SELECT, "COIN1"),
            (LogicalControl.MENU, "UI_MENU"),
        ):
            for token in cls._binding_tokens(profile, logical, controller_number):
                controls.append(MameMappedControl(mame_type, token, logical))
        return tuple(controls)

    @classmethod
    def _binding_tokens(
        cls,
        profile: ControlProfile,
        logical: LogicalControl,
        controller_number: int,
    ) -> tuple[str, ...]:
        tokens: list[str] = []
        for element_id in profile.bindings.get(logical, ()):
            token = cls._element_to_joycode(element_id, controller_number)
            if token:
                tokens.append(token)
        return tuple(tokens)

    @staticmethod
    def _element_to_joycode(element_id: str, controller_number: int) -> str | None:
        """Traduz IDs crus do probe para tokens JOYCODE do MAME."""
        prefix = f"JOYCODE_{controller_number}_"
        if element_id.startswith("button:"):
            try:
                index = int(element_id.split(":", 1)[1])
            except ValueError:
                return None
            return f"{prefix}BUTTON{index + 1}"

        if element_id.startswith("axis:"):
            parts = element_id.split(":")
            if len(parts) != 3:
                return None
            try:
                index = int(parts[1])
            except ValueError:
                return None
            sign = parts[2]
            axis = {0: "X", 1: "Y", 2: "Z", 3: "RX", 4: "RY", 5: "RZ"}.get(index)
            if axis is None or sign not in {"+", "-"}:
                return None
            direction = {
                ("X", "-"): "LEFT",
                ("X", "+"): "RIGHT",
                ("Y", "-"): "UP",
                ("Y", "+"): "DOWN",
            }.get((axis, sign))
            if direction:
                return f"{prefix}{axis}AXIS_{direction}_SWITCH"
            return f"{prefix}{axis}AXIS_{'NEG' if sign == '-' else 'POS'}_SWITCH"

        if element_id.startswith("hat:"):
            try:
                index = int(element_id.split(":", 1)[1])
            except ValueError:
                return None
            # A direção do Hat é descoberta durante a calibração. O ID atual
            # não carrega a direção; por isso o Hat só será emitido quando o
            # perfil futuro registrar a direção explicitamente.
            return f"{prefix}HAT{index + 1}"
        return None

    @classmethod
    def render_m30_ctrlr(
        cls,
        profile: ControlProfile,
        controller_number: int = DEFAULT_CONTROLLER,
    ) -> str:
        """Renderiza o perfil M30 neutro para ``-ctrlr``."""
        return cls._render_ctrlr(cls.build_m30_mapping(profile, controller_number), "default")

    @classmethod
    def render_m30_street_fighter_ii_ctrlr(
        cls,
        profile: ControlProfile,
        controller_number: int = DEFAULT_CONTROLLER,
    ) -> str:
        """Renderiza o perfil M30 específico para a família Street Fighter II."""
        mapped = cls.build_m30_street_fighter_ii_mapping(profile, controller_number)
        return cls._render_ctrlr(mapped, "sf2")

    @staticmethod
    def _render_ctrlr(mapped: tuple[MameMappedControl, ...], system_name: str) -> str:
        by_type: dict[str, list[str]] = {}
        for item in mapped:
            by_type.setdefault(item.mame_type, []).append(item.sequence)

        lines = [
            '<?xml version="1.0"?>',
            '<mameconfig version="10">',
            f'    <system name="{escape(system_name)}">',
            '        <input>',
        ]
        for mame_type, sequences in by_type.items():
            sequence = " OR ".join(dict.fromkeys(sequences))
            lines.extend(
                [
                    f'            <port type="{escape(mame_type)}">',
                    f'                <newseq type="standard">{escape(sequence)}</newseq>',
                    '            </port>',
                ]
            )
        lines.extend([
            '        </input>',
            '    </system>',
            '</mameconfig>',
            '',
        ])
        return "\n".join(lines)

    @classmethod
    def write_m30_ctrlr(
        cls,
        profile: ControlProfile,
        path: str | Path,
        controller_number: int = DEFAULT_CONTROLLER,
    ) -> Path:
        """Grava um perfil M30 no formato ``.cfg`` do MAME."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(cls.render_m30_ctrlr(profile, controller_number), encoding="utf-8")
        return destination

    @classmethod
    def write_m30_street_fighter_ii_ctrlr(
        cls,
        profile: ControlProfile,
        path: str | Path,
        controller_number: int = DEFAULT_CONTROLLER,
    ) -> Path:
        """Grava um perfil M30 específico para Street Fighter II."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            cls.render_m30_street_fighter_ii_ctrlr(profile, controller_number),
            encoding="utf-8",
        )
        return destination


__all__ = ["MameControllerMappingService", "MameMappedControl"]
