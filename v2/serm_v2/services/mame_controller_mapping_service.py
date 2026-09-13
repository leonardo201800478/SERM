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

        MODE/PAIR não é mapeado: Pair é função de pareamento do hardware e não
        representa uma entrada de jogo no MAME.
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
        """Renderiza o primeiro perfil M30 completo para ``-ctrlr``."""
        mapped = cls.build_m30_mapping(profile, controller_number)
        by_type: dict[str, list[str]] = {}
        for item in mapped:
            by_type.setdefault(item.mame_type, []).append(item.sequence)

        lines = [
            '<?xml version="1.0"?>',
            '<mameconfig version="10">',
            '    <system name="default">',
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


__all__ = ["MameControllerMappingService", "MameMappedControl"]
