"""Descoberta de dispositivos de entrada físicos via HIDAPI.

HIDAPI é usado aqui para identidade física e inventário. A leitura de
entradas de alto nível fica a cargo do backend SDL3.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from ..models.input_control import InputConnection, InputDevice, InputDeviceType

logger = logging.getLogger(__name__)


class InputDeviceService:
    """Enumera hardware HID e mantém diagnóstico útil quando o binding falha."""

    def enumerate_hid(self, *, log_summary: bool = True) -> tuple[InputDevice, ...]:
        try:
            import hid
        except ImportError as exc:
            logger.warning("[INPUT] HIDAPI não está disponível: %s", exc)
            return ()
        try:
            records: Iterable[dict[str, object]] = tuple(hid.enumerate())
        except Exception as exc:
            logger.warning("[INPUT] falha ao enumerar HID: %s", exc)
            return ()
        devices = []
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
        return InputDevice(
            device_id=cls._device_id(path, vendor_id, product_id, serial, index),
            name=name,
            device_type=cls._device_type(name, usage_page, usage),
            connection=cls._connection(path, bus_type),
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
    def _device_id(path: str | None, vendor_id: int | None, product_id: int | None, serial: str | None, index: int) -> str:
        if path:
            return f"hid:path:{path}"
        vendor = f"{vendor_id:04x}" if vendor_id is not None else "0000"
        product = f"{product_id:04x}" if product_id is not None else "0000"
        return f"hid:{vendor}:{product}:{serial or index}"

    @staticmethod
    def _connection(path: str | None, bus_type: int | None = None) -> InputConnection:
        # No inventário Windows observado: 1=USB e 2=Bluetooth.
        if bus_type == 1:
            return InputConnection.USB
        if bus_type == 2:
            return InputConnection.BLUETOOTH
        normalized = (path or "").casefold()
        if any(token in normalized for token in ("bthenum", "bluetooth", "{00001124-", "bth")):
            return InputConnection.BLUETOOTH
        if "wireless" in normalized or "receiver" in normalized:
            return InputConnection.WIRELESS
        # HID paths Windows normalmente carregam VID/PID; isso é evidência de
        # transporte USB apenas quando não há uma assinatura Bluetooth acima.
        if re.search(r"hid#vid_[0-9a-f]{4}&pid_[0-9a-f]{4}", normalized):
            return InputConnection.USB
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
