"""Backend SDL3 para gamepads."""

from __future__ import annotations

import ctypes
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from ..models.input_control import InputDevice, InputDeviceType, InputElement, InputElementType

logger = logging.getLogger(__name__)
input_logger = logging.getLogger("SERM.INPUT")


@dataclass(frozen=True, slots=True)
class GamepadSnapshot:
    device_id: int
    buttons: dict[str, bool]
    axes: dict[str, int]


class SDL3InputService:
    """Enumera gamepads SDL3 e coleta a topologia física sem alterar mappings."""

    def __init__(self) -> None:
        self._initialized = False

    def _load(self) -> Any:
        input_logger.info("[SDL3][01] carregando PySDL3")
        try:
            import sdl3
        except ImportError as exc:
            raise RuntimeError("PySDL3 não está instalado") from exc
        return sdl3

    @staticmethod
    def _callable(sdl3: Any, function_name: str) -> Callable[..., Any] | None:
        function = getattr(sdl3, function_name, None)
        if not callable(function):
            return None
        return cast(Callable[..., Any], function)

    def initialize(self) -> None:
        if self._initialized:
            input_logger.info("[SDL3][01] subsistema já inicializado")
            return
        sdl3: Any = self._load()
        flags = sdl3.SDL_INIT_GAMEPAD | sdl3.SDL_INIT_EVENTS
        input_logger.info("[SDL3][02] SDL_InitSubSystem flags=%s", flags)
        init_subsystem = self._callable(sdl3, "SDL_InitSubSystem")
        if init_subsystem is None:
            raise RuntimeError("SDL3 não disponibiliza SDL_InitSubSystem")
        if not init_subsystem(flags):
            error = self._decode(sdl3.SDL_GetError())
            raise RuntimeError(f"SDL3 não inicializou o subsistema de gamepad: {error}")
        self._initialized = True
        input_logger.info("[SDL3][03] subsistema inicializado")

    def enumerate(self) -> tuple[InputDevice, ...]:
        sdl3: Any = self._load()
        self.initialize()
        count = ctypes.c_int(0)
        input_logger.info("[SDL3][04] chamando SDL_GetGamepads")
        get_gamepads = self._callable(sdl3, "SDL_GetGamepads")
        if get_gamepads is None:
            raise RuntimeError("SDL3 não disponibiliza SDL_GetGamepads")
        ids = get_gamepads(ctypes.pointer(count))
        if not ids:
            input_logger.info("[SDL3][05] SDL não retornou gamepads")
            return ()
        input_logger.info("[SDL3][05] SDL retornou %d gamepad(s)", count.value)
        devices: list[InputDevice] = []
        ids_ptr = ctypes.cast(ids, ctypes.POINTER(ctypes.c_uint32))
        try:
            for index in range(max(0, int(count.value))):
                instance_id = int(ids_ptr[index])
                input_logger.info("[SDL3][06] gamepad[%d] instance_id=%d", index, instance_id)
                try:
                    devices.append(self._describe(sdl3, instance_id))
                except (AttributeError, TypeError, ValueError, OSError, RuntimeError):
                    logger.exception("[INPUT] SDL3 não conseguiu descrever gamepad %d", index)
        finally:
            input_logger.info("[SDL3][16] liberando array retornado por SDL_GetGamepads")
            free = self._callable(sdl3, "SDL_free")
            if free is not None:
                free(ctypes.cast(ids, ctypes.c_void_p))
        input_logger.info("[SDL3][17] enumeração SDL3 concluída: %d dispositivo(s)", len(devices))
        return tuple(devices)

    def _describe(self, sdl3: Any, instance_id: int) -> InputDevice:
        input_logger.info("[SDL3][07] ID %d: Name", instance_id)
        name = self._decode(sdl3.SDL_GetGamepadNameForID(instance_id)) or f"SDL Gamepad {instance_id}"
        input_logger.info("[SDL3][08] ID %d: Path", instance_id)
        path = self._optional_text_call(sdl3, "SDL_GetGamepadPathForID", instance_id)
        input_logger.info("[SDL3][09] ID %d: GUID", instance_id)
        guid = self._guid(sdl3, instance_id)
        input_logger.info("[SDL3][10] ID %d: Vendor/Product/Version", instance_id)
        vendor = self._optional_int_call(sdl3, "SDL_GetGamepadVendorForID", instance_id)
        product = self._optional_int_call(sdl3, "SDL_GetGamepadProductForID", instance_id)
        version = self._optional_int_call(sdl3, "SDL_GetGamepadProductVersionForID", instance_id)
        input_logger.info("[SDL3][11] ID %d: Mapping ignorado durante descoberta segura", instance_id)

        elements, topology = self._topology(sdl3, instance_id)
        battery_percent, battery_state = self._battery_info(sdl3, instance_id)
        input_logger.info(
            "[SDL3][13] ID %d: bateria=%s%% | estado=%s",
            instance_id,
            battery_percent if battery_percent is not None else "?",
            battery_state or "unknown",
        )
        input_logger.info(
            "[SDL3][14] ID %d: topologia buttons=%d axes=%d hats=%d",
            instance_id,
            topology[0], topology[1], topology[2],
        )
        input_logger.info("[SDL3][15] ID %d: criando InputDevice", instance_id)
        metadata: dict[str, object] = {"instance_id": instance_id, "topology_source": "SDL3 joystick"}
        if battery_percent is not None:
            metadata["battery_percent"] = battery_percent
        if battery_state:
            metadata["battery_state"] = battery_state
        metadata.update({"raw_button_count": topology[0], "raw_axis_count": topology[1], "raw_hat_count": topology[2]})
        device = InputDevice(
            device_id=f"sdl3:{instance_id}", name=name, device_type=InputDeviceType.GAMEPAD,
            vendor_id=vendor, product_id=product, version=version,
            path=path, sdl_guid=guid, sdl_mapping=None, backend="sdl3",
            elements=elements,
            metadata=metadata,
        )
        input_logger.info("[SDL3][16] ID %d: gamepad descrito", instance_id)
        return device

    @classmethod
    def _topology(cls, sdl3: Any, instance_id: int) -> tuple[tuple[InputElement, ...], tuple[int, int, int]]:
        """Lê a topologia bruta do joystick subjacente.

        Não depende do mapping SDL. Assim, botões extras do M30 (Start/Mode/Menu,
        além dos seis face e dois ombros) continuam visíveis mesmo que não sejam
        representados por um controle lógico padrão.
        """
        open_gamepad = cls._callable(sdl3, "SDL_OpenGamepad")
        get_joystick = cls._callable(sdl3, "SDL_GetGamepadJoystick")
        close_gamepad = cls._callable(sdl3, "SDL_CloseGamepad")
        num_buttons = cls._callable(sdl3, "SDL_GetNumJoystickButtons")
        num_axes = cls._callable(sdl3, "SDL_GetNumJoystickAxes")
        num_hats = cls._callable(sdl3, "SDL_GetNumJoystickHats")
        if open_gamepad is None or get_joystick is None or close_gamepad is None or num_buttons is None or num_axes is None or num_hats is None:
            return (), (0, 0, 0)

        open_gamepad_fn = open_gamepad
        get_joystick_fn = get_joystick
        close_gamepad_fn = close_gamepad
        num_buttons_fn = num_buttons
        num_axes_fn = num_axes
        num_hats_fn = num_hats

        gamepad: Any = None
        try:
            gamepad = open_gamepad_fn(instance_id)
            if not gamepad:
                return (), (0, 0, 0)
            joystick = get_joystick_fn(gamepad)
            if not joystick:
                return (), (0, 0, 0)
            buttons = max(0, int(num_buttons_fn(joystick)))
            axes = max(0, int(num_axes_fn(joystick)))
            hats = max(0, int(num_hats_fn(joystick)))
            elements: list[InputElement] = []
            for index in range(buttons):
                elements.append(
                    InputElement(
                        element_id=f"button:{index}",
                        element_type=InputElementType.BUTTON,
                        name=f"Raw Button {index + 1}",
                        index=index,
                    )
                )
            for index in range(axes):
                elements.append(
                    InputElement(
                        element_id=f"axis:{index}",
                        element_type=InputElementType.AXIS,
                        name=f"Raw Axis {index + 1}",
                        index=index,
                    )
                )
            for index in range(hats):
                elements.append(
                    InputElement(
                        element_id=f"hat:{index}",
                        element_type=InputElementType.HAT,
                        name=f"Raw Hat {index + 1}",
                        index=index,
                    )
                )
            return tuple(elements), (buttons, axes, hats)
        except (AttributeError, TypeError, ValueError, OSError, RuntimeError):
            logger.debug("[INPUT] SDL3 não conseguiu consultar topologia %s", instance_id, exc_info=True)
            return (), (0, 0, 0)
        finally:
            if gamepad:
                try:
                    close_gamepad_fn(gamepad)
                except (AttributeError, TypeError, OSError, RuntimeError):
                    logger.debug("[INPUT] falha ao fechar gamepad %s", instance_id, exc_info=True)

    @classmethod
    def _battery_info(cls, sdl3: Any, instance_id: int) -> tuple[int | None, str | None]:
        """Consulta a bateria abrindo o gamepad apenas durante a leitura."""
        open_gamepad = cls._callable(sdl3, "SDL_OpenGamepad")
        power_info = cls._callable(sdl3, "SDL_GetGamepadPowerInfo")
        close_gamepad = cls._callable(sdl3, "SDL_CloseGamepad")
        if open_gamepad is None or power_info is None or close_gamepad is None:
            return None, None

        open_gamepad_fn = open_gamepad
        power_info_fn = power_info
        close_gamepad_fn = close_gamepad

        gamepad: Any = None
        try:
            gamepad = open_gamepad_fn(instance_id)
            if not gamepad:
                return None, None
            percent = ctypes.c_int(-1)
            try:
                state = power_info_fn(gamepad, ctypes.pointer(percent))
            except AttributeError:
                # Alguns doubles e versões antigas da API expõem `_obj` no ponteiro.
                class _PercentPointer:
                    _obj = percent

                state = power_info_fn(gamepad, _PercentPointer())
            value = int(percent.value)
            battery_percent = value if 0 <= value <= 100 else None
            state_name = cls._power_state_name(sdl3, state)
            return battery_percent, state_name
        except (AttributeError, TypeError, ValueError, OSError, RuntimeError):
            logger.debug("[INPUT] SDL3 não disponibilizou bateria para gamepad %s", instance_id, exc_info=True)
            return None, None
        finally:
            if gamepad:
                try:
                    close_gamepad_fn(gamepad)
                except (AttributeError, TypeError, OSError, RuntimeError):
                    logger.debug("[INPUT] falha ao fechar handle SDL3 do gamepad %s", instance_id, exc_info=True)

    @staticmethod
    def _power_state_name(sdl3: Any, state: object) -> str | None:
        if state is None:
            return None
        for name in ("SDL_POWERSTATE_UNKNOWN", "SDL_POWERSTATE_ON_BATTERY", "SDL_POWERSTATE_NO_BATTERY", "SDL_POWERSTATE_CHARGING", "SDL_POWERSTATE_CHARGED", "SDL_POWERSTATE_ERROR"):
            try:
                if state == getattr(sdl3, name):
                    return name.removeprefix("SDL_POWERSTATE_").lower()
            except AttributeError:
                continue
        return str(state).casefold()

    @classmethod
    def _optional_text_call(cls, sdl3: Any, function_name: str, instance_id: int) -> str | None:
        function = cls._callable(sdl3, function_name)
        if function is None:
            return None
        try:
            return cls._decode(function(instance_id))
        except (AttributeError, TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _safe_int_call(function: Callable[..., Any], instance_id: int) -> int:
        try:
            return int(function(instance_id))
        except (AttributeError, TypeError, ValueError, OSError):
            return 0

    @classmethod
    def _optional_int_call(cls, sdl3: Any, function_name: str, instance_id: int) -> int | None:
        function = cls._callable(sdl3, function_name)
        if function is None:
            return None
        value = cls._safe_int_call(function, instance_id)
        return value or None

    @staticmethod
    def _guid(sdl3: Any, instance_id: int) -> str | None:
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
        if isinstance(value, ctypes.c_char_p):
            raw = value.value
            return raw.decode("utf-8", errors="replace") if raw else None
        if isinstance(value, ctypes.c_void_p):
            pointer = value.value
            if pointer:
                return ctypes.string_at(pointer).decode("utf-8", errors="replace")
            return None
        if isinstance(value, int):
            return ctypes.string_at(value).decode("utf-8", errors="replace")
        text = str(value).strip()
        return text or None


__all__ = ["GamepadSnapshot", "SDL3InputService"]