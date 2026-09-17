"""Compara requisitos de um sistema emulado com um perfil físico."""

from __future__ import annotations

from dataclasses import dataclass

from ..models.input_control import (
    ControlProfile,
    InputDevice,
    InputDeviceType,
    InputElementType,
    LogicalControl,
)
from .mame_control_service import MameInputRequirements


@dataclass(frozen=True, slots=True)
class ControlMappingSuggestion:
    logical_control: LogicalControl
    source_element_ids: tuple[str, ...]
    score: int
    reason: str


@dataclass(frozen=True, slots=True)
class SystemControlMapping:
    compatible: bool
    score: int
    warnings: tuple[str, ...]
    suggestions: tuple[ControlMappingSuggestion, ...]


class SystemControlMapper:
    """Calcula compatibilidade sem injetar eventos ou alterar o emulador."""

    def map_mame(
        self,
        requirements: MameInputRequirements,
        device: InputDevice,
        profile: ControlProfile | None = None,
    ) -> SystemControlMapping:
        warnings: list[str] = []
        suggestions: list[ControlMappingSuggestion] = []
        score = 100

        if requirements.players and requirements.players > 1:
            warnings.append(f"Sistema exige {requirements.players} jogadores; validar dispositivos disponíveis.")
            score -= 10

        if requirements.max_buttons is not None:
            physical_buttons = self._button_count(device, profile)
            if physical_buttons < requirements.max_buttons:
                warnings.append(
                    f"Sistema exige até {requirements.max_buttons} botões; dispositivo oferece {physical_buttons}."
                )
                score -= min(50, (requirements.max_buttons - physical_buttons) * 15)
            else:
                suggestions.extend(self._face_suggestions(profile, requirements.max_buttons))

        for control in requirements.controls:
            if control.ways and control.ways > 4 and control.control_type not in {"dial", "paddle", "trackball"}:
                warnings.append(
                    f"Controle {control.control_type} declara {control.ways} vias; validar a topologia do jogo."
                )
                score -= 5
            if control.control_type in {"dial", "paddle", "trackball", "pedal", "positional"}:
                if device.device_type is InputDeviceType.GAMEPAD:
                    warnings.append(f"Controle analógico especializado: {control.control_type}.")
                    score -= 20

        score = max(0, min(100, score))
        compatible = score >= 70 and not any("oferece" in warning for warning in warnings)
        return SystemControlMapping(compatible, score, tuple(warnings), tuple(suggestions))

    @staticmethod
    def _button_count(device: InputDevice, profile: ControlProfile | None) -> int:
        if profile:
            bound = {control for control in profile.bindings if control.value.startswith("face_")}
            if bound:
                return len(bound)
        return sum(1 for element in device.elements if element.element_type is InputElementType.BUTTON)

    @staticmethod
    def _face_suggestions(
        profile: ControlProfile | None,
        max_buttons: int,
    ) -> list[ControlMappingSuggestion]:
        if not profile:
            return []
        ordered = (
            LogicalControl.FACE_SOUTH,
            LogicalControl.FACE_EAST,
            LogicalControl.FACE_WEST,
            LogicalControl.FACE_NORTH,
            LogicalControl.FACE_EXTRA_1,
            LogicalControl.FACE_EXTRA_2,
        )
        suggestions: list[ControlMappingSuggestion] = []
        for control in ordered[:max_buttons]:
            ids = profile.bindings.get(control, ())
            if ids:
                suggestions.append(
                    ControlMappingSuggestion(control, tuple(ids), 100, "Controle lógico já definido no perfil físico.")
                )
        return suggestions


__all__ = ["ControlMappingSuggestion", "SystemControlMapping", "SystemControlMapper"]
