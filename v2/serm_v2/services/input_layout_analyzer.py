"""Análise de elementos físicos e construção de um layout de controle.

O analisador não presume que todo dispositivo seja um gamepad de quatro
botões. Ele preserva a contagem e a ordem dos elementos observados e fornece
uma classificação simples para a camada de apresentação e de mapeamento.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.input_control import InputDevice, InputDeviceType, InputElement, InputElementType


@dataclass(frozen=True, slots=True)
class LayoutSummary:
    """Resumo independente de fabricante do layout detectado."""

    device_id: str
    device_type: InputDeviceType
    buttons: int
    axes: int
    hats: int
    keys: int
    mouse_buttons: int
    has_six_face_buttons: bool
    profile_kind: str


class InputLayoutAnalyzer:
    """Extrai a topologia do controle a partir dos elementos conhecidos."""

    def analyze(self, device: InputDevice) -> LayoutSummary:
        elements = device.elements
        counts = {
            InputElementType.BUTTON: 0,
            InputElementType.AXIS: 0,
            InputElementType.HAT: 0,
            InputElementType.KEY: 0,
            InputElementType.MOUSE_BUTTON: 0,
        }
        for element in elements:
            if element.element_type in counts:
                counts[element.element_type] += 1

        face_buttons = self._face_button_count(elements)
        return LayoutSummary(
            device_id=device.device_id,
            device_type=device.device_type,
            buttons=counts[InputElementType.BUTTON],
            axes=counts[InputElementType.AXIS],
            hats=counts[InputElementType.HAT],
            keys=counts[InputElementType.KEY],
            mouse_buttons=counts[InputElementType.MOUSE_BUTTON],
            has_six_face_buttons=face_buttons >= 6,
            profile_kind=self._profile_kind(device.device_type, face_buttons, counts),
        )

    @staticmethod
    def _face_button_count(elements: tuple[InputElement, ...]) -> int:
        logical = {element.logical_control for element in elements}
        names = {
            value
            for value in logical
            if value is not None and (value.value.startswith("face_") or value.value in {"face_south", "face_east", "face_west", "face_north"})
        }
        if names:
            return len(names)
        # Fallback para inventários ainda sem mapeamento lógico.
        return sum(1 for element in elements if element.element_type is InputElementType.BUTTON and "face" in element.name.casefold())

    @staticmethod
    def _profile_kind(device_type: InputDeviceType, face_buttons: int, counts: dict[InputElementType, int]) -> str:
        if device_type is InputDeviceType.STEERING_WHEEL:
            return "steering-wheel"
        if device_type in {InputDeviceType.KEYBOARD, InputDeviceType.MOUSE}:
            return device_type.value
        if face_buttons >= 6:
            return "six-button-gamepad"
        if face_buttons >= 4:
            return "four-button-gamepad"
        if counts[InputElementType.BUTTON] >= 1:
            return "custom-gamepad"
        return "unknown"


__all__ = ["InputLayoutAnalyzer", "LayoutSummary"]
