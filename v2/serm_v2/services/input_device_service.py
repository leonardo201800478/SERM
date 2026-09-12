"""Descoberta de dispositivos de entrada físicos via HIDAPI.

HIDAPI é usado aqui para identidade física e inventário. A leitura de
entradas de alto nível fica a cargo do backend SDL3, evitando que o SERM
interprete relatórios HID proprietários de cada fabricante.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from ..models.input_control import InputConnection, InputDevice, InputDeviceType

logger = logging.getLogger(__name__)


class InputDeviceService:
    """Enumera hardware HID e mantém diagnóstico útil quando o binding falha."""

    def enumerate_hid(self, *, log_summary: bool = True) -> tuple[InputDevice, ...]:
        """Retorna os dispositivos HID visíveis, degradando com segurança."""
        try:
            import hid
        except ImportError as exc:
            logger.warning("[INPUT] HIDAPI não está disponível: %s", exc)
            return ()

        try:
            records: Iterable[dict[str, object]] = hid.enumerate()
            records = tuple(records)
        except Exception as exc:  # HIDAPI depende do backend do SO.
            logger.warning("[INPUT] falha ao enumerar HID: %s", exc)
            return ()

        devices: list[InputDevice] = []
        for index, record in enumerate(records):
            device = self._from_hid_record(index, record)
            if device is not None:
                devices.append(device)

        if log_summary:
            logger.info("[INPUT] HIDAPI enumerou %d dispositivos", len(devices))
        return tuple(devices)

    @classmethod
    def _from_hid_record(cls, index: int, record: dict[str, object]) -> InputDevice | None:
        path = cls._text(record.get("path"))
        vendor_id = cls._int(record.get("vendor_id"))
        product_id = cls._int(record.get("product_id"))
        if path is None and vendor_id is None and product_id is None:
            return None

        product = cls._text(record.get("product_string"))
        manufacturer = cls._text(record.get("manufacturer_string"))
        if product or manufacturer:
            name = product or manufacturer or "HID"
        elif vendor_id is not None and product_id is not None:
            name = f"HID {vendor_id:04X}:{product_id:04X}"
        else:
            name = f"HID {index + 1}"

        usage_page = cls._int(record.get("usage_page"))
        usage = cls._int(record.get("usage"))
        serial = cls._text(record.get("serial_number"))
        bus_type = cls._int(record.get("bus_type"))
        connection = cls._connection(path, bus_type)
        device_type = cls._device_type(name, usage_page, usage)
        device_id = cls._device_id(path, vendor_id, product_id, serial, index)

        return InputDevice(
            device_id=device_id,
            name=name,
            device_type=device_type,
            connection=connection,
            vendor_id=vendor_id,
            product_id=product_id,
            version=cls._int(record.get("release_number")),
            serial=serial,
            manufacturer=manufacturer,
            product=product,
            usage_page=usage_page,
            usage=usage,
            path=path,
            interface_number=cls._int(record.get("interface_number")),
            bus_type=bus_type,
            backend="hidapi",
            metadata={"raw_hid": True},
        )

    @staticmethod
    def _device_id(
        path: str | None, vendor_id: int | None, product_id: int | None, serial: str | None, index: int
    ) -> str:
        if path:
            return f"hid:path:{path}"
        vendor = f"{vendor_id:04x}" if vendor_id is not None else "0000"
        product = f"{product_id:04x}" if product_id is not None else "0000"
        suffix = serial or str(index)
        return f"hid:{vendor}:{product}:{suffix}"

    @staticmethod
    def _connection(path: str | None, bus_type: int | None = None) -> InputConnection:
        # HIDAPI no Windows expõe bus_type com valores que são mais confiáveis
        # que o texto do path: 1 = USB, 2 = Bluetooth. O path continua como
        # fallback para outros backends/versões do binding.
        if bus_type == 2:
            return InputConnection.BLUETOOTH
        if bus_type == 1:
            return InputConnection.USB
        normalized = (path or "").casefold()
        if "bthenum" in normalized or "bluetooth" in normalized:
            return InputConnection.BLUETOOTH
        if "usb" in normalized:
            return InputConnection.USB
        if "wireless" in normalized or "receiver" in normalized:
            return InputConnection.WIRELESS
        return InputConnection.UNKNOWN

    @staticmethod
    def _device_type(name: str, usage_page: int | None, usage: int | None) -> InputDeviceType:
        normalized = name.casefold()
        if usage_page == 0x01:
            if usage == 0x06:
                return InputDeviceType.KEYBOARD
            if usage == 0x02:
                return InputDeviceType.MOUSE
            if usage in {0x04, 0x05, 0x08}:
                return InputDeviceType.GAMEPAD

        if any(token in normalized for token in ("g27", "g25", "g29", "racing wheel", "steering wheel", "wheel")):
            return InputDeviceType.STEERING_WHEEL
        if any(token in normalized for token in ("arcade stick", "fight stick", "fighting stick")):
            return InputDeviceType.ARCADE_STICK
        if any(token in normalized for token in ("light gun", "lightgun")):
            return InputDeviceType.LIGHTGUN
        if any(token in normalized for token in ("dance pad", "dance mat")):
            return InputDeviceType.DANCE_PAD
        return InputDeviceType.UNKNOWN

    @staticmethod
    def _text(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _int(value: object) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


__all__ = ["InputDeviceService"]
