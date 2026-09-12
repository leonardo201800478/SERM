"""Backend SDL3 para gamepads, com diagnóstico por etapa."""

from __future__ import annotations

import ctypes
import logging
from dataclasses import dataclass

from ..models.input_control import InputDevice, InputDeviceType

logger = logging.getLogger("SERM.INPUT")


@dataclass(frozen=True, slots=True)
class GamepadSnapshot:
    """Estado instantâneo dos controles padronizados pelo SDL3."""

    device_id: int
    buttons: dict[str, bool]
    axes: dict[str, int]


class SDL3InputService:
    """Enumera gamepads SDL3 sem deixar metadados opcionais interromper a descoberta."""

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
            logger.info("[SDL3][01] subsistema já inicializado")
            return
        logger.info("[SDL3][01] carregando PySDL3")
        sdl3 = self._load()
        flags = sdl3.SDL_INIT_GAMEPAD | sdl3.SDL_INIT_EVENTS
        logger.info("[SDL3][02] SDL_InitSubSystem flags=%s", flags)
        if not sdl3.SDL_InitSubSystem(flags):
            error = self._decode(sdl3.SDL_GetError())
            raise RuntimeError(f"SDL3 não inicializou o subsistema de gamepad: {error}")
        self._initialized = True
        logger.info("[SDL3][03] subsistema inicializado")

    def enumerate(self) -> tuple[InputDevice, ...]:
        sdl3 = self._load()
        self.initialize()
        count = ctypes.c_int(0)
        logger.info("[SDL3][04] chamando SDL_GetGamepads")
        ids = sdl3.SDL_GetGamepads(ctypes.byref(count))
        if not ids:
            logger.info("[SDL3][05] nenhum gamepad retornado")
            return ()
        logger.info("[SDL3][05] SDL retornou %d gamepad(s)", count.value)
        devices: list[InputDevice] = []
        try:
            for index in range(max(0, int(count.value))):
                instance_id = int(ids[index])
                logger.info("[SDL3][06] gamepad[%d] instance_id=%d", index, instance_id)
                try:
                    device = self._describe(sdl3, instance_id)
                    devices.append(device)
                    logger.info("[SDL3][15] gamepad[%d] descrito: %s", index, device.name)
                except Exception:
                    logger.exception("[SDL3][ERR] falha descrevendo gamepad[%d] id=%d", index, instance_id)
        finally:
            logger.info("[SDL3][16] liberando array retornado por SDL_GetGamepads")
            try:
                sdl3.SDL_free(ids)
            except Exception:
                logger.exception("[SDL3][ERR] SDL_free falhou")
        logger.info("[SDL3][17] enumeração SDL3 concluída: %d dispositivo(s)", len(devices))
        return tuple(devices)

    @classmethod
    def _describe(cls, sdl3, instance_id: int) -> InputDevice:
        logger.info("[SDL3][07] ID %d: Name", instance_id)
        name = cls._decode(sdl3.SDL_GetGamepadNameForID(instance_id)) or f"SDL Gamepad {instance_id}"
        logger.info("[SDL3][08] ID %d: Path", instance_id)
        path = cls._optional_text_call(sdl3, "SDL_GetGamepadPathForID", instance_id)
        logger.info("[SDL3][09] ID %d: GUID", instance_id)
        guid = cls._guid(sdl3, instance_id)
        logger.info("[SDL3][10] ID %d: Vendor/Product/Version", instance_id)
        vendor = cls._optional_int_call(sdl3, "SDL_GetGamepadVendorForID", instance_id)
        product = cls._optional_int_call(sdl3, "SDL_GetGamepadProductForID", instance_id)
        version = cls._optional_int_call(sdl3, "SDL_GetGamepadProductVersionForID", instance_id)
        logger.info("[SDL3][11] ID %d: Mapping", instance_id)
        mapping = cls._mapping(sdl3, instance_id)
        logger.info("[SDL3][12] ID %d: RealGamepadType", instance_id)
        device_type = cls._device_type(sdl3, instance_id, name)
        logger.info("[SDL3][13] ID %d: criando InputDevice", instance_id)
        return InputDevice(
            device_id=f"sdl3:{instance_id}", name=name, device_type=device_type,
            vendor_id=vendor, product_id=product, version=version,
            path=path, sdl_guid=guid, sdl_mapping=mapping, backend="sdl3",
            metadata={"instance_id": instance_id},
        )

    @staticmethod
    def _optional_text_call(sdl3, function_name: str, instance_id: int) -> str | None:
        try:
            function = getattr(sdl3, function_name)
            return SDL3InputService._decode(function(instance_id))
        except (AttributeError, TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _optional_int_call(sdl3, function_name: str, instance_id: int) -> int | None:
        try:
            function = getattr(sdl3, function_name)
            value = int(function(instance_id))
            return value or None
        except (AttributeError, TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _mapping(sdl3, instance_id: int) -> str | None:
        try:
            function = getattr(sdl3, "SDL_GetGamepadMappingForID")
            value = function(instance_id)
        except (AttributeError, TypeError, ValueError, OSError):
            return None
        if not value:
            return None
        try:
            return SDL3InputService._decode(value)
        finally:
            try:
                sdl3.SDL_free(value)
            except (AttributeError, TypeError, ValueError, OSError):
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
