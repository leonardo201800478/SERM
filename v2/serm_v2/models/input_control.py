"""Modelos de domínio para hardware e perfis de entrada.

A identidade física é separada da camada lógica. Isso permite que o mesmo
controle lógico seja usado por MAME e, futuramente, por outros emuladores
sem gravar regras específicas do emulador no cadastro do dispositivo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class InputDeviceType(StrEnum):
    GAMEPAD = "gamepad"
    ARCADE_STICK = "arcade_stick"
    FIGHTING_CONTROLLER = "fighting_controller"
    STEERING_WHEEL = "steering_wheel"
    FLIGHT_CONTROLLER = "flight_controller"
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    LIGHTGUN = "lightgun"
    DANCE_PAD = "dance_pad"
    SPECIALIZED = "specialized"
    UNKNOWN = "unknown"


class InputConnection(StrEnum):
    USB = "usb"
    BLUETOOTH = "bluetooth"
    WIRELESS = "wireless"
    VIRTUAL = "virtual"
    UNKNOWN = "unknown"


class InputElementType(StrEnum):
    BUTTON = "button"
    AXIS = "axis"
    HAT = "hat"
    KEY = "key"
    MOUSE_BUTTON = "mouse_button"
    MOUSE_AXIS = "mouse_axis"
    UNKNOWN = "unknown"


class LogicalControl(StrEnum):
    DPAD_UP = "dpad_up"
    DPAD_DOWN = "dpad_down"
    DPAD_LEFT = "dpad_left"
    DPAD_RIGHT = "dpad_right"
    FACE_SOUTH = "face_south"
    FACE_EAST = "face_east"
    FACE_WEST = "face_west"
    FACE_NORTH = "face_north"
    START = "start"
    BACK = "back"
    GUIDE = "guide"
    LEFT_SHOULDER = "left_shoulder"
    RIGHT_SHOULDER = "right_shoulder"
    LEFT_TRIGGER = "left_trigger"
    RIGHT_TRIGGER = "right_trigger"
    LEFT_STICK = "left_stick"
    RIGHT_STICK = "right_stick"
    LEFT_X = "left_x"
    LEFT_Y = "left_y"
    RIGHT_X = "right_x"
    RIGHT_Y = "right_y"
    STEERING = "steering"
    ACCELERATOR = "accelerator"
    BRAKE = "brake"
    CLUTCH = "clutch"
    PEDAL = "pedal"
    COIN = "coin"
    SERVICE = "service"
    TEST = "test"
    PLAYER_START = "player_start"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class InputElement:
    """Elemento físico ou lógico de entrada."""

    element_id: str
    element_type: InputElementType
    name: str
    index: int | None = None
    logical_control: LogicalControl | None = None
    minimum: int | None = None
    maximum: int | None = None


@dataclass(frozen=True, slots=True)
class InputDevice:
    """Identidade estável de um dispositivo detectado no sistema."""

    device_id: str
    name: str
    device_type: InputDeviceType = InputDeviceType.UNKNOWN
    connection: InputConnection = InputConnection.UNKNOWN
    vendor_id: int | None = None
    product_id: int | None = None
    version: int | None = None
    serial: str | None = None
    manufacturer: str | None = None
    product: str | None = None
    usage_page: int | None = None
    usage: int | None = None
    path: str | None = None
    interface_number: int | None = None
    bus_type: int | None = None
    sdl_guid: str | None = None
    sdl_mapping: str | None = None
    backend: str = "unknown"
    elements: tuple[InputElement, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def hardware_key(self) -> str:
        """Chave persistente preferindo VID/PID e, quando disponível, serial."""
        vendor = f"{self.vendor_id:04x}" if self.vendor_id is not None else "0000"
        product = f"{self.product_id:04x}" if self.product_id is not None else "0000"
        serial = self.serial or ""
        return f"{vendor}:{product}:{serial}".casefold()


@dataclass(frozen=True, slots=True)
class ControlProfile:
    """Perfil lógico independente do emulador."""

    profile_id: str
    name: str
    device_id: str
    bindings: dict[LogicalControl, tuple[str, ...]] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)


__all__ = [
    "ControlProfile",
    "InputConnection",
    "InputDevice",
    "InputDeviceType",
    "InputElement",
    "InputElementType",
    "LogicalControl",
]
