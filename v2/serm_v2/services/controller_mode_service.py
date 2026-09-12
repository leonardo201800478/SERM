"""Reconhecimento de modos de entrada dos controles observados no SERM V2.

O serviço interpreta assinaturas VID/PID e contexto físico. Ele não envia
comandos ao dispositivo e não cria driver virtual.
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
    """Interpreta modo de hardware sem confundir assinaturas compartilhadas."""

    _M30 = "8bitdo-m30"
    _ULTIMATE_2C = "8bitdo-ultimate-2c"
    _ULTIMATE_2 = "8bitdo-ultimate-2-wireless"
    _GENERIC_SWITCH = "generic-switch-pro-controller"
    _G27 = "logitech-g27"
    _MACHENIKE_G5_PRO = "machenike-g5-pro"
    _XBOX_ONE = "xbox-one-controller"
    _XBOX = "xbox-controller"
    _DUALSHOCK_4 = "sony-dualshock-4"
    _DUALSENSE = "sony-dualsense"

    @classmethod
    def identify(cls, device: InputDevice) -> ControllerModeMatch | None:
        for detector in (
            cls.identify_ultimate_2,
            cls.identify_ultimate_2c,
            cls.identify_m30,
            cls.identify_machenike_g5_pro,
            cls.identify_g27,
            cls.identify_dualsense,
            cls.identify_dualshock_4,
            cls.identify_xbox_one,
            cls.identify_xbox,
            cls.identify_generic_switch,
        ):
            match = detector(device)
            if match is not None:
                return match
        return None

    @staticmethod
    def _connection_name(device: InputDevice) -> str:
        if device.connection == InputConnection.BLUETOOTH or device.bus_type == 2:
            return "Bluetooth"
        if device.connection == InputConnection.USB or device.bus_type == 1:
            return "USB"
        return device.connection.value

    @classmethod
    def identify_m30(cls, device: InputDevice) -> ControllerModeMatch | None:
        vendor, product = device.vendor_id, device.product_id
        if vendor is None or product is None:
            return None
        name = " ".join(v for v in (device.name, device.product, device.manufacturer) if v).casefold()
        explicit_m30 = "m30" in name

        native = {
            0x0651: ("dinput", "D-Input / Android", "B + START", "LED 1 piscando"),
            0x5006: ("dinput-usb", "D-Input / USB", "B + START", "LED 1 / conexão sólida"),
        }
        signature = native.get(product) if vendor == 0x2DC8 else None

        # 045E:02E0/028E e 054C:05C4 são apresentações XInput/DS4
        # compartilhadas. Só podem ser atribuídas ao M30 se o próprio nome
        # trouxer evidência explícita de M30.
        if signature is None and explicit_m30:
            shared = {
                (0x045E, 0x02E0): ("xinput-bt", "XInput / Bluetooth", "X + START", "LEDs 1 e 2 piscando"),
                (0x045E, 0x028E): ("xinput-usb", "XInput / USB", "X + START", "LEDs 1 e 2 piscando"),
                (0x054C, 0x05C4): ("macos", "macOS / DualShock 4", "A + START", "LEDs 1, 2 e 3 piscando"),
            }
            signature = shared.get((vendor, product))
        if signature is None:
            return None

        mode_id, mode_name, power_on, led_hint = signature
        confirmed = vendor == 0x2DC8
        return ControllerModeMatch(
            cls._M30, "8BitDo M30", mode_id, mode_name,
            cls._connection_name(device), 100 if confirmed else 70,
            confirmed, f"VID 0x{vendor:04X} / PID 0x{product:04X}", power_on, led_hint,
        )

    @classmethod
    def identify_ultimate_2(cls, device: InputDevice) -> ControllerModeMatch | None:
        if device.vendor_id != 0x2DC8 or device.product_id not in {0x310B, 0x6012, 0x6013}:
            return None
        signatures = {
            0x310B: ("xinput-2p4g-or-usb", "XInput / 2.4G ou USB", "HOME", "LED de status aceso"),
            0x6012: ("dinput-2p4g-usb-bt", "D-Input / 2.4G, USB ou Bluetooth", "B + HOME", "LED de status aceso"),
            0x6013: ("receiver-idle", "Receptor 2.4G / controle inativo", "HOME no controle para ativar", "receptor presente"),
        }
        mode_id, mode_name, power_on, led_hint = signatures[device.product_id]
        return ControllerModeMatch(
            cls._ULTIMATE_2, "8BitDo Ultimate 2 Wireless", mode_id, mode_name,
            cls._connection_name(device), 100, True,
            f"VID 0x{device.vendor_id:04X} / PID 0x{device.product_id:04X}", power_on, led_hint,
        )

    @classmethod
    def identify_ultimate_2c(cls, device: InputDevice) -> ControllerModeMatch | None:
        if device.vendor_id != 0x2DC8 or device.product_id not in {0x310A, 0x301B, 0x3013}:
            return None
        signatures = {
            0x310A: ("xinput-usb-2p4g", "XInput / USB ou 2.4G", "HOME", "LED de status aceso fixo"),
            0x301B: ("bluetooth", "Bluetooth / HID", "HOME; PAIR por 3 s", "LED piscando durante pareamento"),
            0x3013: ("bluetooth", "Bluetooth / HID", "HOME; PAIR por 3 s", "LED piscando durante pareamento"),
        }
        mode_id, mode_name, power_on, led_hint = signatures[device.product_id]
        return ControllerModeMatch(
            cls._ULTIMATE_2C, "8BitDo Ultimate 2C", mode_id, mode_name,
            cls._connection_name(device), 100, True,
            f"VID 0x{device.vendor_id:04X} / PID 0x{device.product_id:04X}", power_on, led_hint,
        )

    @classmethod
    def identify_g27(cls, device: InputDevice) -> ControllerModeMatch | None:
        if device.vendor_id != 0x046D or device.product_id != 0xC29B:
            return None
        return ControllerModeMatch(cls._G27, "Logitech G27 Racing Wheel", "native-hid", "Volante / HID", cls._connection_name(device), 100, True, "VID 0x046D / PID 0xC29B", "conectar USB", "LED conforme hardware")

    @classmethod
    def identify_machenike_g5_pro(cls, device: InputDevice) -> ControllerModeMatch | None:
        if device.vendor_id != 0x2345 or device.product_id != 0xE00B:
            return None
        name = " ".join(v for v in (device.name, device.product, device.manufacturer) if v).casefold()
        if "machenike" not in name and "g5" not in name:
            return None
        return ControllerModeMatch(cls._MACHENIKE_G5_PRO, "Machenike G5 PRO", "xinput", "XInput / USB", cls._connection_name(device), 100, True, "VID 0x2345 / PID 0xE00B + fabricante/nome", "USB", "LED conforme hardware")

    @classmethod
    def identify_xbox_one(cls, device: InputDevice) -> ControllerModeMatch | None:
        if device.vendor_id != 0x045E or device.product_id != 0x02FF:
            return None
        return ControllerModeMatch(cls._XBOX_ONE, "Xbox One Controller", "xinput", "XInput / USB", cls._connection_name(device), 100, True, "VID 0x045E / PID 0x02FF", "USB", "LED do Xbox")

    @classmethod
    def identify_xbox(cls, device: InputDevice) -> ControllerModeMatch | None:
        signatures = {
            0x02E0: "Xbox Wireless Controller",
            0x0B20: "Xbox Wireless Controller",
            0x028E: "Xbox 360 Controller",
        }
        if device.vendor_id != 0x045E or device.product_id not in signatures:
            return None
        name = signatures[device.product_id]
        mode = "XInput / Bluetooth" if device.product_id in {0x02E0, 0x0B20} else "XInput / USB"
        return ControllerModeMatch(cls._XBOX, name, "xinput", mode, cls._connection_name(device), 100, True, f"VID 0x045E / PID 0x{device.product_id:04X}", "HOME", "LED do Xbox")

    @classmethod
    def identify_dualshock_4(cls, device: InputDevice) -> ControllerModeMatch | None:
        if device.vendor_id != 0x054C or device.product_id not in {0x05C4, 0x09CC}:
            return None
        return ControllerModeMatch(cls._DUALSHOCK_4, "Sony DualShock 4", "hid", "HID / Bluetooth ou USB", cls._connection_name(device), 100, True, f"VID 0x054C / PID 0x{device.product_id:04X}", "PS", "barra de luz")

    @classmethod
    def identify_dualsense(cls, device: InputDevice) -> ControllerModeMatch | None:
        if device.vendor_id != 0x054C or device.product_id != 0x0CE6:
            return None
        return ControllerModeMatch(cls._DUALSENSE, "Sony DualSense", "hid", "HID / Bluetooth ou USB", cls._connection_name(device), 100, True, "VID 0x054C / PID 0x0CE6", "PS", "barra de luz")

    @classmethod
    def identify_generic_switch(cls, device: InputDevice) -> ControllerModeMatch | None:
        if device.vendor_id != 0x057E or device.product_id != 0x2009:
            return None
        return ControllerModeMatch(cls._GENERIC_SWITCH, "Nintendo Switch Pro Controller (genérico)", "switch", "Nintendo Switch / HID", cls._connection_name(device), 100, False, "VID 0x057E / PID 0x2009", "Y + HOME", "LEDs em rotação")

    @staticmethod
    def m30_instructions() -> tuple[str, ...]:
        return (
            "D-Input / Android: desligado, segure B + START para ligar.",
            "XInput / Windows: desligado, segure X + START para ligar.",
            "macOS / DS4: desligado, segure A + START para ligar.",
            "Nintendo Switch: desligado, segure Y + START para ligar.",
        )

    @staticmethod
    def ultimate_2_instructions() -> tuple[str, ...]:
        return (
            "XInput / 2.4G: pressione HOME com o receptor conectado.",
            "D-Input / 2.4G: segure B + HOME.",
            "O PID 0x6012 foi observado em USB e Bluetooth; não é exclusivo de Bluetooth.",
            "O PID 0x6013 é o receptor 2.4G inativo, não um gamepad.",
            "0x057E:0x2009 permanece neutro por ser uma assinatura Switch compartilhada.",
        )

    @staticmethod
    def ultimate_2c_instructions() -> tuple[str, ...]:
        return (
            "2.4G/USB: perfil XInput do PC.",
            "Bluetooth: perfil HID.",
            "O SERM identifica o transporte/modo observado; não envia comandos.",
        )


__all__ = ["ControllerModeMatch", "ControllerModeService"]
