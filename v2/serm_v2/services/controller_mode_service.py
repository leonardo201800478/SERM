"""Reconhecimento de modos de entrada conhecidos do 8BitDo M30.

O M30 Bluetooth deliberadamente se apresenta como outros controladores em
alguns modos. Por isso VID/PID é tratado como assinatura de modo, não como
identidade universal do fabricante. Assinaturas genéricas (XInput/Switch/DS4)
são marcadas como compatíveis até que o nome ou outra evidência confirme o M30.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.input_control import InputConnection, InputDevice


@dataclass(frozen=True, slots=True)
class ControllerModeMatch:
    model_id: str
    model_name: str
    mode_id: str
    mode_name: str
    connection: str
    confidence: int
    confirmed: bool
    signature: str
    power_on: str
    led_hint: str


class ControllerModeService:
    """Interpreta assinaturas de modo do M30 sem alterar o dispositivo."""

    _M30 = "8bitdo-m30"

    @classmethod
    def identify_m30(cls, device: InputDevice) -> ControllerModeMatch | None:
        vendor = device.vendor_id
        product = device.product_id
        if vendor is None or product is None:
            return None

        key = (vendor, product)
        connection = device.connection
        bluetooth = connection == InputConnection.BLUETOOTH or device.bus_type == 2
        usb = connection == InputConnection.USB or device.bus_type == 1
        name = " ".join(v for v in (device.name, device.product, device.manufacturer) if v).casefold()
        explicit_m30 = "m30" in name or "8bitdo" in name

        signatures = {
            (0x2DC8, 0x0651): ("dinput", "D-Input / Android", "B + START", "LED 1 piscando", True),
            (0x2DC8, 0x5006): ("dinput-usb", "D-Input / USB", "B + START", "LED 1 / conexão sólida", True),
            (0x045E, 0x02E0): ("xinput-bt", "XInput / Bluetooth", "X + START", "LEDs 1 e 2 piscando", False),
            (0x045E, 0x028E): ("xinput-usb", "XInput / USB", "X + START", "LEDs 1 e 2 piscando", False),
            (0x057E, 0x2009): ("switch", "Nintendo Switch", "Y + START", "LEDs em rotação", False),
            (0x054C, 0x05C4): ("macos", "macOS / DualShock 4", "A + START", "LEDs 1, 2 e 3 piscando", False),
        }
        signature = signatures.get(key)
        if signature is None:
            return None

        mode_id, mode_name, power_on, led_hint, native_m30 = signature
        if bluetooth:
            connection_name = "Bluetooth"
        elif usb:
            connection_name = "USB"
        else:
            connection_name = connection.value

        confirmed = native_m30 or explicit_m30
        confidence = 100 if confirmed else 70
        return ControllerModeMatch(
            model_id=cls._M30,
            model_name="8BitDo M30",
            mode_id=mode_id,
            mode_name=mode_name,
            connection=connection_name,
            confidence=confidence,
            confirmed=confirmed,
            signature=f"VID 0x{vendor:04X} / PID 0x{product:04X}",
            power_on=power_on,
            led_hint=led_hint,
        )

    @staticmethod
    def m30_instructions() -> tuple[str, ...]:
        return (
            "D-Input / Android: desligado, segure B + START para ligar.",
            "XInput / Windows: desligado, segure X + START para ligar.",
            "macOS / DS4: desligado, segure A + START para ligar.",
            "Nintendo Switch: desligado, segure Y + START para ligar.",
            "Desligar: segure START por 3 s; desligamento forçado: 8 s.",
            "Pareamento Bluetooth: com o modo escolhido, segure PAIR por 2 s.",
        )


__all__ = ["ControllerModeMatch", "ControllerModeService"]
