"""Catálogo local de modelos de controladores observados pelo SERM V2."""

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
    """Identifica somente modelos sustentados pelas evidências do dispositivo."""

    MIN_CONFIDENCE = 60

    def __init__(self, entries: tuple[ControllerCatalogEntry, ...] = ()) -> None:
        self._entries = entries

    def identify(self, device: InputDevice) -> ControllerIdentification:
        candidates: list[tuple[int, ControllerCatalogEntry, list[str]]] = []
        device_text = " ".join(
            value.casefold() for value in (device.name, device.product or "", device.manufacturer or "") if value
        )
        for entry in self._entries:
            score = 0
            reasons: list[str] = []
            vendor_match = entry.vendor_id is not None and device.vendor_id == entry.vendor_id
            product_match = bool(entry.product_ids) and device.product_id in entry.product_ids
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
                    "8bitdo-m30", "8BitDo", "M30", InputDeviceType.GAMEPAD,
                    ("8BitDo M30 Gamepad", "M30 Gamepad"), 0x2DC8, (0x5006, 0x0651),
                    6, 2, 1, 0, False,
                    ("D-Input / USB", "D-Input / Android", "XInput / USB", "XInput / Bluetooth", "Nintendo Switch / HID", "macOS / DualShock 4"),
                    "M30", ("Arcade-style six-button face layout; nunca reduzir para quatro botões.",),
                ),
                ControllerCatalogEntry(
                    "8bitdo-ultimate-2c", "8BitDo", "Ultimate 2C", InputDeviceType.GAMEPAD,
                    ("8BitDo Ultimate 2C Wireless Controller", "8BitDo Ultimate 2C Wireless", "Ultimate 2C Wireless Controller"),
                    0x2DC8, (0x310A, 0x301B, 0x3013), 4, 4, 1, 2, False,
                    ("XInput / USB", "XInput / 2.4G", "Bluetooth / HID"), "Ultimate 2C",
                    ("USB/2.4G usam o perfil PC/XInput; Bluetooth é tratado como HID.",),
                ),
                ControllerCatalogEntry(
                    "8bitdo-ultimate-2-wireless", "8BitDo", "Ultimate 2 Wireless", InputDeviceType.GAMEPAD,
                    ("8BitDo Ultimate 2 Wireless Controller", "8BitDo Ultimate 2 Wireless Controller for PC", "8BitDo Ultimate 2"),
                    0x2DC8, (0x310B, 0x6012, 0x6013), 4, 4, 1, 2, True,
                    ("XInput / USB", "XInput / 2.4G", "D-Input / USB", "D-Input / 2.4G", "D-Input / Bluetooth"), "Ultimate 2",
                    ("0x310B é a apresentação XInput ativa; 0x6012 é D-Input; 0x6013 é o receptor 2.4G inativo.",
                     "0x057E:0x2009 não é identidade permanente do Ultimate 2, pois é compartilhado por controles Switch.")
                ),
                ControllerCatalogEntry(
                    "logitech-g27", "Logitech", "G27 Racing Wheel", InputDeviceType.STEERING_WHEEL,
                    ("G27", "Logitech G27"), 0x046D, (0xC29B,), 0, 5, 1, 0, False,
                    ("USB / HID",), "G27", ("Volante e pedais devem permanecer em perfil próprio, sem tratá-los como gamepad.",),
                ),
                ControllerCatalogEntry(
                    "machenike-g5-pro", "MACHENIKE", "Machenike G5 PRO", InputDeviceType.GAMEPAD,
                    ("Xbox 360 Controller for Windows", "Machenike G5 PRO"), 0x2345, (0xE00B,), 4, 4, 1, 0, False,
                    ("XInput / USB",), "G5 PRO", ("O firmware se apresenta como Xbox 360 Controller for Windows; fabricante/VID/PID preservam a identidade física MACHENIKE.",),
                ),
                ControllerCatalogEntry(
                    "xbox-one-controller", "Microsoft", "Xbox One Controller", InputDeviceType.GAMEPAD,
                    ("Controller (Xbox One For Windows)",), 0x045E, (0x02FF,), 4, 4, 1, 0, False,
                    ("XInput / USB",), "Xbox", (),
                ),
                ControllerCatalogEntry(
                    "xbox-wireless-controller", "Microsoft", "Xbox Wireless Controller", InputDeviceType.GAMEPAD,
                    ("Xbox Bluetooth Gamepad",), 0x045E, (0x02E0, 0x0B20), 4, 4, 1, 0, False,
                    ("XInput / Bluetooth",), "Xbox", (),
                ),
                ControllerCatalogEntry(
                    "xbox-360-controller", "Microsoft", "Xbox 360 Controller", InputDeviceType.GAMEPAD,
                    ("Controller (XBOX 360 For Windows)",), 0x045E, (0x028E,), 4, 4, 1, 0, False,
                    ("XInput / USB",), "Xbox 360", (),
                ),
                ControllerCatalogEntry(
                    "sony-dualshock-4", "Sony", "Sony DualShock 4", InputDeviceType.GAMEPAD,
                    ("Wireless Controller", "DualShock 4"), 0x054C, (0x05C4, 0x09CC), 4, 4, 1, 0, True,
                    ("HID / USB", "HID / Bluetooth"), "DualShock 4", ("09CC foi observado em Bluetooth; 05C4 permanece suportado como assinatura USB/DS4.",),
                ),
                ControllerCatalogEntry(
                    "sony-dualsense", "Sony", "Sony DualSense", InputDeviceType.GAMEPAD,
                    ("DualSense Wireless Controller",), 0x054C, (0x0CE6,), 4, 5, 1, 0, True,
                    ("HID / USB", "HID / Bluetooth"), "DualSense", ("0x0CE6 foi observado tanto em USB quanto em Bluetooth.",),
                ),
            )
        )

    @classmethod
    def eightbitdo(cls) -> "ControllerCatalogService":
        """Retorna exclusivamente os modelos 8BitDo físicos já validados."""
        return cls(
            tuple(entry for entry in cls.default().entries() if entry.manufacturer.casefold() == "8bitdo")
        )

    def entries(self) -> tuple[ControllerCatalogEntry, ...]:
        return self._entries


__all__ = ["ControllerCatalogEntry", "ControllerCatalogService", "ControllerIdentification"]
