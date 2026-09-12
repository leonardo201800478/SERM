"""Consolida identidade, modo e perfil lógico dos controles físicos.

A camada é deliberadamente somente descritiva: não injeta eventos nem altera
configurações do sistema operacional ou do emulador.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.input_control import InputDevice, InputDeviceType
from .controller_catalog_service import ControllerCatalogService, ControllerIdentification
from .controller_mode_service import ControllerModeMatch, ControllerModeService


@dataclass(frozen=True, slots=True)
class ControllerProfile:
    model_id: str | None
    model_name: str
    device_type: InputDeviceType
    mode_id: str | None
    mode_name: str
    connection: str
    confidence: int
    confirmed: bool
    input_family: str
    logical_roles: tuple[str, ...]
    notes: tuple[str, ...] = ()


class ControllerProfileService:
    """Resolve o perfil final sem depender do nome exposto pelo Windows."""

    def __init__(self, catalog: ControllerCatalogService | None = None) -> None:
        self.catalog = catalog or ControllerCatalogService.default()

    def resolve(self, device: InputDevice) -> ControllerProfile:
        identification = self.catalog.identify(device)
        mode = ControllerModeService.identify(device)
        model = identification.model

        if model is None:
            return self._unknown(device, mode)

        roles = self._roles(model.model_id, model.device_type)
        mode_id = mode.mode_id if mode else None
        mode_name = mode.mode_name if mode else self._fallback_mode(device)
        connection = mode.connection if mode else device.connection.value
        confidence = min(100, max(identification.confidence, mode.confidence if mode else 0))
        confirmed = bool(mode.confirmed) if mode else identification.confidence >= 85
        notes = list(model.notes)
        if mode is not None and mode.mode_id == "receiver-idle":
            notes.append("Receptor detectado: não criar perfil de jogador enquanto não houver o gamepad ativo.")

        return ControllerProfile(
            model_id=model.model_id,
            model_name=model.model_name,
            device_type=model.device_type,
            mode_id=mode_id,
            mode_name=mode_name,
            connection=connection,
            confidence=confidence,
            confirmed=confirmed,
            input_family=self._input_family(model.model_id, model.device_type),
            logical_roles=roles,
            notes=tuple(notes),
        )

    @staticmethod
    def _unknown(device: InputDevice, mode: ControllerModeMatch | None) -> ControllerProfile:
        return ControllerProfile(
            model_id=None,
            model_name=device.name or "Dispositivo desconhecido",
            device_type=device.device_type,
            mode_id=mode.mode_id if mode else None,
            mode_name=mode.mode_name if mode else "Modo não identificado",
            connection=mode.connection if mode else device.connection.value,
            confidence=mode.confidence if mode else 0,
            confirmed=bool(mode.confirmed) if mode else False,
            input_family="unknown",
            logical_roles=("preservar elementos físicos observados",),
            notes=("Não criar bindings específicos sem evidência suficiente.",),
        )

    @staticmethod
    def _fallback_mode(device: InputDevice) -> str:
        return "USB / HID" if device.connection.value == "usb" else f"{device.connection.value} / HID"

    @staticmethod
    def _input_family(model_id: str, device_type: InputDeviceType) -> str:
        if device_type is InputDeviceType.STEERING_WHEEL:
            return "wheel"
        if model_id.startswith("xbox-") or model_id == "xbox-one-controller":
            return "xinput-gamepad"
        if model_id.startswith("sony-"):
            return "sony-gamepad"
        if model_id.startswith("8bitdo-"):
            return "8bitdo-gamepad"
        if model_id == "machenike-g5-pro":
            return "xinput-gamepad"
        return "gamepad" if device_type is InputDeviceType.GAMEPAD else device_type.value

    @staticmethod
    def _roles(model_id: str, device_type: InputDeviceType) -> tuple[str, ...]:
        if model_id == "logitech-g27":
            return ("steering", "accelerator", "brake", "clutch", "shift/buttons")
        if model_id == "8bitdo-m30":
            return ("dpad", "face-1..6", "shoulders", "start/back", "arcade-six-button")
        if model_id in {"8bitdo-ultimate-2c", "8bitdo-ultimate-2-wireless"}:
            return ("dpad", "face-1..4", "shoulders", "triggers", "sticks", "start/back", "rear-buttons")
        if model_id in {"sony-dualshock-4", "sony-dualsense"}:
            return ("dpad", "face-1..4", "shoulders", "triggers", "sticks", "start/options", "guide", "motion")
        return ("dpad", "face-1..4", "shoulders", "triggers", "sticks", "start/back") if device_type is InputDeviceType.GAMEPAD else ("preserve physical elements",)


__all__ = ["ControllerProfile", "ControllerProfileService"]
