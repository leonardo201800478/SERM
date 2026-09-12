"""Reconhecimento de modos de entrada conhecidos dos controles 8BitDo.

O serviço interpreta assinaturas VID/PID já observadas no inventário HID.
Ele não envia comandos ao dispositivo e não cria driver virtual.
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
    """Interpreta assinaturas de modo sem alterar o dispositivo."""

    _M30 = "8bitdo-m30"
    _ULTIMATE_2C = "8bitdo-ultimate-2c"
    _ULTIMATE_2 = "8bitdo-ultimate-2-wireless"
    _GENERIC_SWITCH = "generic-switch-pro-controller"

    @classmethod
    def identify(cls, device: InputDevice) -> ControllerModeMatch | None:
        """Identifica um modo conhecido de um controlador físico.

        Assinaturas compartilhadas por vários modelos não devem ser atribuídas
        a um modelo específico. Isso é especialmente importante para
        057E:2009, que representa um Nintendo Switch Pro Controller genérico.
        """
        ultimate_2 = cls.identify_ultimate_2(device)
        if ultimate_2 is not None:
            return ultimate_2

        # 057E:2009 é uma assinatura de transporte/protocolo compartilhada.
        # Só depois das assinaturas proprietárias tentamos interpretá-la como
        # um dispositivo Switch genérico.
        switch = cls.identify_generic_switch(device)
        if switch is not None:
            return switch

        m30 = cls.identify_m30(device)
        if m30 is not None:
            return m30
        return cls.identify_ultimate_2c(device)

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
        explicit_m30 = "m30" in name

        signatures = {
            (0x2DC8, 0x0651): ("dinput", "D-Input / Android", "B + START", "LED 1 piscando", True),
            (0x2DC8, 0x5006): ("dinput-usb", "D-Input / USB", "B + START", "LED 1 / conexão sólida", True),
            (0x045E, 0x02E0): ("xinput-bt", "XInput / Bluetooth", "X + START", "LEDs 1 e 2 piscando", False),
            (0x045E, 0x028E): ("xinput-usb", "XInput / USB", "X + START", "LEDs 1 e 2 piscando", False),
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

    @classmethod
    def identify_ultimate_2(cls, device: InputDevice) -> ControllerModeMatch | None:
        """Identifica os modos proprietários observados no Ultimate 2 Wireless."""
        vendor = device.vendor_id
        product = device.product_id
        if vendor != 0x2DC8 or product is None:
            return None

        signatures = {
            0x310B: (
                "xinput-2p4g-or-usb",
                "XInput / 2.4G ou USB",
                "HOME",
                "LED de status aceso",
            ),
            0x6012: (
                "dinput-2p4g-usb-bt",
                "D-Input / 2.4G, USB ou Bluetooth",
                "B + HOME",
                "LED de status aceso",
            ),
            0x6013: (
                "receiver-idle",
                "Receptor 2.4G / controle inativo",
                "HOME no controle para ativar",
                "receptor presente",
            ),
        }
        signature = signatures.get(product)
        if signature is None:
            return None

        mode_id, mode_name, power_on, led_hint = signature
        if device.connection == InputConnection.BLUETOOTH or device.bus_type == 2:
            connection_name = "Bluetooth"
        elif device.connection == InputConnection.USB or device.bus_type == 1:
            connection_name = "USB"
        else:
            connection_name = device.connection.value

        return ControllerModeMatch(
            model_id=cls._ULTIMATE_2,
            model_name="8BitDo Ultimate 2 Wireless",
            mode_id=mode_id,
            mode_name=mode_name,
            connection=connection_name,
            confidence=100,
            confirmed=True,
            signature=f"VID 0x{vendor:04X} / PID 0x{product:04X}",
            power_on=power_on,
            led_hint=led_hint,
        )

    @classmethod
    def identify_generic_switch(cls, device: InputDevice) -> ControllerModeMatch | None:
        """Retorna uma identificação neutra para a assinatura Switch compartilhada."""
        if device.vendor_id != 0x057E or device.product_id != 0x2009:
            return None

        if device.connection == InputConnection.BLUETOOTH or device.bus_type == 2:
            connection_name = "Bluetooth"
        elif device.connection == InputConnection.USB or device.bus_type == 1:
            connection_name = "USB"
        else:
            connection_name = device.connection.value

        return ControllerModeMatch(
            model_id=cls._GENERIC_SWITCH,
            model_name="Nintendo Switch Pro Controller (genérico)",
            mode_id="switch",
            mode_name="Nintendo Switch / HID",
            connection=connection_name,
            confidence=100,
            confirmed=False,
            signature="VID 0x057E / PID 0x2009",
            power_on="Y + HOME",
            led_hint="LEDs em rotação",
        )

    @classmethod
    def identify_ultimate_2c(cls, device: InputDevice) -> ControllerModeMatch | None:
        vendor = device.vendor_id
        product = device.product_id
        if vendor != 0x2DC8 or product is None:
            return None

        signatures = {
            0x310A: (
                "xinput-usb-2p4g",
                "XInput / USB ou 2.4G",
                "HOME",
                "LED de status aceso fixo",
            ),
            0x301B: (
                "bluetooth",
                "Bluetooth / HID",
                "HOME; PAIR por 3 s para pareamento",
                "LED piscando durante pareamento",
            ),
            0x3013: (
                "bluetooth",
                "Bluetooth / HID",
                "HOME; PAIR por 3 s para pareamento",
                "LED piscando durante pareamento",
            ),
        }
        signature = signatures.get(product)
        if signature is None:
            return None

        mode_id, mode_name, power_on, led_hint = signature
        if device.connection == InputConnection.BLUETOOTH or device.bus_type == 2:
            connection_name = "Bluetooth"
        elif device.connection == InputConnection.USB or device.bus_type == 1:
            connection_name = "USB"
        else:
            connection_name = device.connection.value

        return ControllerModeMatch(
            model_id=cls._ULTIMATE_2C,
            model_name="8BitDo Ultimate 2C",
            mode_id=mode_id,
            mode_name=mode_name,
            connection=connection_name,
            confidence=100,
            confirmed=True,
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

    @staticmethod
    def ultimate_2_instructions() -> tuple[str, ...]:
        return (
            "XInput / 2.4G: desligado, pressione HOME para ligar com o receptor conectado.",
            "D-Input / 2.4G: desligado, segure B + HOME para ligar.",
            "Switch / 2.4G: desligado, segure Y + HOME para ligar.",
            "Bluetooth: PID 0x6012 foi observado no inventário físico como D-Input.",
            "USB: o teste físico confirmou 0x310B em XInput e 0x6012 em D-Input.",
            "O PID 0x6013 representa o receptor 2.4G em estado inativo e não um modo de jogo.",
            "0x057E:0x2009 é uma assinatura Switch genérica; não atribuir automaticamente ao Ultimate 2.",
            "O SERM identifica o modo observado; não envia comandos ao controle.",
        )

    @staticmethod
    def ultimate_2c_instructions() -> tuple[str, ...]:
        return (
            "2.4G: coloque a chave física em 2.4G, conecte o receptor e pressione HOME.",
            "USB: conecte o cabo USB-C ao PC; o controle é apresentado no mesmo perfil XInput do modo PC.",
            "Bluetooth: coloque a chave física em BT e pressione HOME.",
            "Primeiro pareamento Bluetooth: segure PAIR por 3 s até o LED piscar rapidamente.",
            "O 2C Wireless 81HD não possui no gabinete o seletor de XInput/D-Input do M30.",
            "O SERM identifica o transporte/modo observado; não envia comandos ao controle.",
        )


__all__ = ["ControllerModeMatch", "ControllerModeService"]
