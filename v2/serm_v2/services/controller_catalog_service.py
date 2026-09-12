"""Catálogo local de modelos de controladores.

O catálogo não substitui HIDAPI/SDL3. Ele apenas transforma evidências já
coletadas em uma identificação de modelo explicável e em um layout esperado.
Novos modelos podem ser adicionados sem alterar o backend de entrada.

O inventário atual consolidado do SERM contém somente os 8BitDo efetivamente
observados/confirmados no ambiente do projeto: M30, Ultimate 2C e Ultimate 2
Wireless. Assinaturas de transporte compartilhadas, como 057E:2009, continuam
neutras e não são usadas como identidade definitiva.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.input_control import InputDevice, InputDeviceType


@dataclass(frozen=True, slots=True)
class ControllerCatalogEntry:
    model_id: str
    manufacturer: str
    model_name: str
    device_type: InputDeviceType
    aliases: tuple[str, ...] = ()
    vendor_id: int | None = None
    product_ids: tuple[int, ...] = ()
    expected_face_buttons: int | None = None
    expected_axes: int | None = None
    expected_hats: int | None = None
    expected_extra_buttons: int | None = None
    supports_motion: bool | None = None
    modes: tuple[str, ...] = ()
    family: str = ""
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ControllerIdentification:
    model: ControllerCatalogEntry | None
    confidence: int
    reasons: tuple[str, ...] = ()


class ControllerCatalogService:
    """Identifica modelos somente quando há evidência suficiente."""

    MIN_CONFIDENCE = 60

    def __init__(self, entries: tuple[ControllerCatalogEntry, ...] = ()) -> None:
        self._entries = entries

    def identify(self, device: InputDevice) -> ControllerIdentification:
        candidates: list[tuple[int, ControllerCatalogEntry, list[str]]] = []
        device_text = " ".join(
            value.casefold()
            for value in (device.name, device.product or "", device.manufacturer or "")
            if value
        )
        for entry in self._entries:
            score = 0
            reasons: list[str] = []
            vendor_match = entry.vendor_id is not None and device.vendor_id == entry.vendor_id
            product_match = bool(entry.product_ids) and device.product_id in entry.product_ids

            # VID sozinho identifica apenas o fabricante, não o modelo.
            if vendor_match and product_match:
                score += 85
                reasons.append("VID+PID")
            elif vendor_match:
                score += 20
                reasons.append("VID")

            model_name = entry.model_name.casefold()
            if model_name and model_name in device_text:
                score += 60
                reasons.append("nome/modelo exato")
            elif any(alias.casefold() in device_text for alias in entry.aliases if alias):
                score += 30
                reasons.append("nome/modelo")

            if score:
                candidates.append((score, entry, reasons))

        if not candidates:
            return ControllerIdentification(None, 0)
        candidates.sort(key=lambda item: item[0], reverse=True)
        score, model, reasons = candidates[0]
        second = candidates[1][0] if len(candidates) > 1 else -1
        if score < self.MIN_CONFIDENCE or (second >= 0 and score - second < 15):
            return ControllerIdentification(None, score, tuple(reasons))
        return ControllerIdentification(model, min(100, score), tuple(reasons))

    @staticmethod
    def default() -> "ControllerCatalogService":
        return ControllerCatalogService(
            (
                ControllerCatalogEntry(
                    model_id="8bitdo-m30",
                    manufacturer="8BitDo",
                    model_name="M30",
                    aliases=("8BitDo M30 Gamepad", "M30 Gamepad"),
                    device_type=InputDeviceType.GAMEPAD,
                    vendor_id=0x2DC8,
                    product_ids=(0x5006, 0x0651),
                    expected_face_buttons=6,
                    expected_axes=2,
                    expected_hats=1,
                    expected_extra_buttons=0,
                    supports_motion=False,
                    modes=("D-Input / USB", "D-Input / Android", "XInput / USB", "XInput / Bluetooth", "Nintendo Switch / HID", "macOS / DualShock 4"),
                    family="M30",
                    notes=(
                        "Arcade-style six-button face layout; must never be reduced to a four-button layout.",
                        "VID/PID 0x2DC8:0x5006 and 0x2DC8:0x0651 are native M30 signatures.",
                        "XInput/macOS signatures may be shared with other devices and remain conservative.",
                    ),
                ),
                ControllerCatalogEntry(
                    model_id="8bitdo-ultimate-2c",
                    manufacturer="8BitDo",
                    model_name="Ultimate 2C",
                    aliases=(
                        "8BitDo Ultimate 2C Wireless Controller",
                        "8BitDo Ultimate 2C Wireless",
                        "Ultimate 2C Wireless Controller",
                    ),
                    device_type=InputDeviceType.GAMEPAD,
                    vendor_id=0x2DC8,
                    product_ids=(0x310A, 0x301B, 0x3013),
                    expected_face_buttons=4,
                    expected_axes=4,
                    expected_hats=1,
                    expected_extra_buttons=2,
                    supports_motion=False,
                    modes=("XInput / USB", "XInput / 2.4G", "Bluetooth / HID"),
                    family="Ultimate 2C",
                    notes=(
                        "81HD family; USB and 2.4G share the PC/XInput profile.",
                        "Bluetooth is represented as HID/D-Input by the mode service.",
                        "Do not identify the model from generic Xbox PIDs alone.",
                    ),
                ),
                ControllerCatalogEntry(
                    model_id="8bitdo-ultimate-2-wireless",
                    manufacturer="8BitDo",
                    model_name="Ultimate 2 Wireless",
                    aliases=(
                        "8BitDo Ultimate 2 Wireless Controller",
                        "8BitDo Ultimate 2 Wireless Controller for PC",
                        "8BitDo Ultimate 2",
                    ),
                    device_type=InputDeviceType.GAMEPAD,
                    vendor_id=0x2DC8,
                    product_ids=(0x310B, 0x6012, 0x6013),
                    expected_face_buttons=4,
                    expected_axes=4,
                    expected_hats=1,
                    expected_extra_buttons=2,
                    supports_motion=True,
                    modes=(
                        "XInput / USB",
                        "XInput / 2.4G",
                        "D-Input / USB",
                        "D-Input / 2.4G",
                        "D-Input / Bluetooth",
                        "Nintendo Switch / HID (contextual)",
                    ),
                    family="Ultimate 2",
                    notes=(
                        "Physical SERM scans confirmed 0x310B, 0x6012 and 0x6013 with no other controller connected.",
                        "0x310B is the active XInput presentation; 0x6012 is D-Input across USB/2.4G/Bluetooth.",
                        "0x6013 is the 2.4G receiver in inactive state, not a gamepad mode.",
                        "0x057E:0x2009 is intentionally not part of the permanent identity because it is shared by third-party Switch controllers.",
                    ),
                ),
            )
        )

    @classmethod
    def eightbitdo(cls) -> "ControllerCatalogService":
        """Alias explícito para obter o inventário 8BitDo consolidado."""
        return cls.default()

    def entries(self) -> tuple[ControllerCatalogEntry, ...]:
        """Retorna o catálogo imutável para UI, auditoria e documentação."""
        return self._entries


__all__ = [
    "ControllerCatalogEntry",
    "ControllerCatalogService",
    "ControllerIdentification",
]
