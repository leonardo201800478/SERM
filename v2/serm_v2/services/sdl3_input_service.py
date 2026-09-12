"""Backend SDL3 para gamepads.

SDL3 fornece a camada de entrada lógica e HIDAPI fornece a identidade física.
O serviço mantém as duas fontes separadas para evitar que uma mudança de
mapeamento lógico apague a identidade real do hardware.
"""

from __future__ import annotations

import ctypes
import logging
from dataclasses import dataclass

from ..models.input_control import InputDevice, InputDeviceType

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GamepadSnapshot:
    """Estado instantâneo dos controles padronizados pelo SDL3."""

    device_id: int
    buttons: dict[str, bool]
    axes: dict[str, int]


class SDL3InputService:
    """Enumera gamepads SDL3 e permite capturar um snapshot sem assumir um SO."""

    def __init__(self) -> None:
        self._initialized = False

    def _load(self):
        try:
            import sdl3
        except ImportError as exc:
            raise RuntimeError("PySDL3 não está instalado") from exc
        return sdl3

    def initialize(self) -> None:
        if self._initialized:
            return
        sdl3 = self._load()
        flags = sdl3.SDL_INIT_GAMEPAD | sdl3.SDL_INIT_EVENTS
        if not sdl3.SDL_InitSubSystem(flags):
            error = self._decode(sdl3.SDL_GetError())
            raise RuntimeError(f"SDL3 não inicializou o subsistema de gamepad: {error}")
        self._initialized = True

    def enumerate(self) -> tuple[InputDevice, ...]:
        """Retorna somente gamepads que o SDL consegue descrever com segurança."""
        sdl3 = self._load()
        self.initialize()
        count = ctypes.c_int(0)
        ids = sdl3.SDL_GetGamepads(ctypes.byref(count))
        if not ids:
            return ()

        devices: list[InputDevice] = []
        try:
            total = max(0, int(count.value))
            for index in range(total):
                try:
                    instance_id = int(ids[index])
                    devices.append(self._describe(sdl3, instance_id))
                except (AttributeError, TypeError, ValueError, OSError, RuntimeError) as exc:
                    logger.warning("[INPUT] SDL3 não conseguiu descrever gamepad %d: %s", index, exc)
        finally:
            try:
                sdl3.SDL_free(ids)
            except (AttributeError, TypeError, ValueError):
                pass
        return tuple(devices)

    def snapshot(self, instance_id: int) -> GamepadSnapshot:
        """Lê o estado lógico atual de um gamepad SDL3."""
        sdl3 = self._load()
        self.initialize()
        gamepad = sdl3.SDL_OpenGamepad(instance_id)
        if not gamepad:
            error = self._decode(sdl3.SDL_GetError())
            raise RuntimeError(f"Não foi possível abrir o gamepad {instance_id}: {error}")

        try:
            sdl3.SDL_UpdateGamepads()
            button_names = {
                "south": "SDL_GAMEPAD_BUTTON_SOUTH", "east": "SDL_GAMEPAD_BUTTON_EAST",
                "west": "SDL_GAMEPAD_BUTTON_WEST", "north": "SDL_GAMEPAD_BUTTON_NORTH",
                "back": "SDL_GAMEPAD_BUTTON_BACK", "guide": "SDL_GAMEPAD_BUTTON_GUIDE",
                "start": "SDL_GAMEPAD_BUTTON_START", "left_stick": "SDL_GAMEPAD_BUTTON_LEFT_STICK",
                "right_stick": "SDL_GAMEPAD_BUTTON_RIGHT_STICK", "left_shoulder": "SDL_GAMEPAD_BUTTON_LEFT_SHOULDER",
                "right_shoulder": "SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER", "dpad_up": "SDL_GAMEPAD_BUTTON_DPAD_UP",
                "dpad_down": "SDL_GAMEPAD_BUTTON_DPAD_DOWN", "dpad_left": "SDL_GAMEPAD_BUTTON_DPAD_LEFT",
                "dpad_right": "SDL_GAMEPAD_BUTTON_DPAD_RIGHT",
            }
            axis_names = {
                "left_x": "SDL_GAMEPAD_AXIS_LEFTX", "left_y": "SDL_GAMEPAD_AXIS_LEFTY",
                "right_x": "SDL_GAMEPAD_AXIS_RIGHTX", "right_y": "SDL_GAMEPAD_AXIS_RIGHTY",
                "left_trigger": "SDL_GAMEPAD_AXIS_LEFT_TRIGGER", "right_trigger": "SDL_GAMEPAD_AXIS_RIGHT_TRIGGER",
            }
            buttons = {name: bool(sdl3.SDL_GetGamepadButton(gamepad, getattr(sdl3, enum_name))) for name, enum_name in button_names.items()}
            axes = {name: int(sdl3.SDL_GetGamepadAxis(gamepad, getattr(sdl3, enum_name))) for name, enum_name in axis_names.items()}
            return GamepadSnapshot(instance_id, buttons, axes)
        finally:
            sdl3.SDL_CloseGamepad(gamepad)

    @classmethod
    def _describe(cls, sdl3, instance_id: int) -> InputDevice:
        name = cls._decode(sdl3.SDL_GetGamepadNameForID(instance_id)) or f"SDL Gamepad {instance_id}"
        path = cls._decode(sdl3.SDL_GetGamepadPathForID(instance_id))
        guid = cls._guid(sdl3, instance_id)
        vendor = cls._safe_int_call(sdl3.SDL_GetGamepadVendorForID, instance_id)
        product = cls._safe_int_call(sdl3.SDL_GetGamepadProductForID, instance_id)
        version = cls._safe_int_call(sdl3.SDL_GetGamepadProductVersionForID, instance_id)
        mapping = cls._mapping(sdl3, instance_id)
        device_type = cls._device_type(sdl3, instance_id, name)
        return InputDevice(
            device_id=f"sdl3:{instance_id}", name=name, device_type=device_type,
            vendor_id=vendor or None, product_id=product or None, version=version or None,
            path=path, sdl_guid=guid, sdl_mapping=mapping, backend="sdl3",
            metadata={"instance_id": instance_id},
        )

    @staticmethod
    def _safe_int_call(function, instance_id: int) -> int:
        try:
            return int(function(instance_id))
        except (AttributeError, TypeError, ValueError, OSError):
            return 0

    @staticmethod
    def _mapping(sdl3, instance_id: int) -> str | None:
        try:
            value = sdl3.SDL_GetGamepadMappingForID(instance_id)
        except (AttributeError, TypeError, ValueError, OSError):
            return None
        if not value:
            return None
        try:
            return SDL3InputService._decode(value)
        finally:
            try:
                sdl3.SDL_free(value)
            except (AttributeError, TypeError, ValueError):
                pass

    @staticmethod
    def _device_type(sdl3, instance_id: int, name: str) -> InputDeviceType:
        try:
            gamepad_type = int(sdl3.SDL_GetRealGamepadTypeForID(instance_id))
        except (AttributeError, TypeError, ValueError, OSError):
            gamepad_type = -1
        names = {
            getattr(sdl3, "SDL_GAMEPAD_TYPE_XBOX360", -1), getattr(sdl3, "SDL_GAMEPAD_TYPE_XBOXONE", -1),
            getattr(sdl3, "SDL_GAMEPAD_TYPE_XBOX_SERIES", -1), getattr(sdl3, "SDL_GAMEPAD_TYPE_PS3", -1),
            getattr(sdl3, "SDL_GAMEPAD_TYPE_PS4", -1), getattr(sdl3, "SDL_GAMEPAD_TYPE_PS5", -1),
            getattr(sdl3, "SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_PRO", -1),
        }
        if gamepad_type in names:
            return InputDeviceType.GAMEPAD
        normalized = name.casefold()
        if any(token in normalized for token in ("g27", "g25", "g29", "racing wheel", "steering wheel")):
            return InputDeviceType.STEERING_WHEEL
        return InputDeviceType.GAMEPAD

    @staticmethod
    def _guid(sdl3, instance_id: int) -> str | None:
        try:
            guid = sdl3.SDL_GetGamepadGUIDForID(instance_id)
            buffer = ctypes.create_string_buffer(33)
            sdl3.SDL_GUIDToString(guid, buffer, len(buffer))
            value = buffer.value.decode("ascii", errors="replace").strip()
            return value or None
        except (AttributeError, TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _decode(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        try:
            return ctypes.string_at(value).decode("utf-8", errors="replace")
        except (TypeError, ValueError):
            text = str(value).strip()
            return text or None


__all__ = ["GamepadSnapshot", "SDL3InputService"]
