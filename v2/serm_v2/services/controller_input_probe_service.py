"""Leitura interativa de entradas físicas para calibração de controles.

O probe trabalha sobre o joystick SDL3 bruto. Ele não usa o mapping SDL e não
injeta eventos no sistema ou no emulador. O objetivo é descobrir qual elemento
físico muda quando o usuário pressiona/move um controle durante a calibração.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..models.input_control import LogicalControl


class ProbeEventType(StrEnum):
    BUTTON = "button"
    AXIS = "axis"
    HAT = "hat"


@dataclass(frozen=True, slots=True)
class ProbeEvent:
    element_id: str
    element_type: ProbeEventType
    index: int
    value: int
    display: str


class ControllerInputProbeService:
    """Mantém uma sessão de leitura bruta de um gamepad SDL3."""

    AXIS_THRESHOLD = 12000

    def __init__(self, sdl3: Any | None = None) -> None:
        self._sdl3 = sdl3
        self._gamepad = None
        self._joystick = None
        self._instance_id: int | None = None
        self._previous_buttons: dict[int, bool] = {}
        self._previous_axes: dict[int, int] = {}
        self._previous_hats: dict[int, int] = {}

    def _load(self) -> Any:
        if self._sdl3 is None:
            import sdl3
            self._sdl3 = sdl3
        return self._sdl3

    def start(self, instance_id: int) -> None:
        if self._gamepad is not None:
            self.stop()
        sdl3 = self._load()
        self._enable_input_updates(sdl3)
        open_gamepad = getattr(sdl3, "SDL_OpenGamepad")
        get_joystick = getattr(sdl3, "SDL_GetGamepadJoystick")
        gamepad = open_gamepad(int(instance_id))
        if not gamepad:
            error = getattr(sdl3, "SDL_GetError", lambda: "erro desconhecido")()
            raise RuntimeError(f"SDL3 não conseguiu abrir o gamepad {instance_id}: {error}")
        joystick = get_joystick(gamepad)
        if not joystick:
            close_gamepad = getattr(sdl3, "SDL_CloseGamepad", None)
            if close_gamepad:
                close_gamepad(gamepad)
            raise RuntimeError(f"SDL3 não disponibilizou o joystick do gamepad {instance_id}")
        self._gamepad = gamepad
        self._joystick = joystick
        self._instance_id = int(instance_id)
        self._previous_buttons.clear()
        self._previous_axes.clear()
        self._previous_hats.clear()
        self._prime()

    def stop(self) -> None:
        if self._gamepad is not None:
            close_gamepad = getattr(self._load(), "SDL_CloseGamepad", None)
            if close_gamepad:
                try:
                    close_gamepad(self._gamepad)
                except (AttributeError, TypeError, OSError, RuntimeError):
                    pass
        self._gamepad = None
        self._joystick = None
        self._instance_id = None
        self._previous_buttons.clear()
        self._previous_axes.clear()
        self._previous_hats.clear()

    @property
    def active(self) -> bool:
        return self._joystick is not None

    @property
    def instance_id(self) -> int | None:
        return self._instance_id

    def poll(self) -> tuple[ProbeEvent, ...]:
        if self._joystick is None:
            return ()
        sdl3 = self._load()
        self._pump_and_update(sdl3)

        events: list[ProbeEvent] = []
        num_buttons = self._count("SDL_GetNumJoystickButtons")
        if num_buttons:
            get_button = getattr(sdl3, "SDL_GetJoystickButton")
            for index in range(num_buttons):
                pressed = bool(get_button(self._joystick, index))
                previous = self._previous_buttons.get(index, pressed)
                self._previous_buttons[index] = pressed
                if pressed and not previous:
                    events.append(ProbeEvent(f"button:{index}", ProbeEventType.BUTTON, index, 1, f"Button {index + 1}"))

        num_axes = self._count("SDL_GetNumJoystickAxes")
        if num_axes:
            get_axis = getattr(sdl3, "SDL_GetJoystickAxis")
            for index in range(num_axes):
                value = int(get_axis(self._joystick, index))
                previous = self._previous_axes.get(index, value)
                self._previous_axes[index] = value
                if self._axis_crossed(previous, value):
                    events.append(ProbeEvent(f"axis:{index}", ProbeEventType.AXIS, index, value, f"Axis {index + 1}"))

        num_hats = self._count("SDL_GetNumJoystickHats")
        if num_hats:
            get_hat = getattr(sdl3, "SDL_GetJoystickHat")
            for index in range(num_hats):
                value = int(get_hat(self._joystick, index))
                previous = self._previous_hats.get(index, value)
                self._previous_hats[index] = value
                if value != previous:
                    events.append(ProbeEvent(f"hat:{index}", ProbeEventType.HAT, index, value, self._hat_name(value)))
        return tuple(events)

    @staticmethod
    def _enable_input_updates(sdl3: Any) -> None:
        """Garante que SDL3 deixe habilitados os eventos de joystick/gamepad."""
        set_joystick_events = getattr(sdl3, "SDL_SetJoystickEventsEnabled", None)
        if set_joystick_events:
            set_joystick_events(True)
        set_gamepad_events = getattr(sdl3, "SDL_SetGamepadEventsEnabled", None)
        if set_gamepad_events:
            set_gamepad_events(True)

    @staticmethod
    def _pump_and_update(sdl3: Any) -> None:
        """Processa a fila e depois atualiza o snapshot bruto do joystick."""
        pump = getattr(sdl3, "SDL_PumpEvents", None)
        if pump:
            pump()
        update_joysticks = getattr(sdl3, "SDL_UpdateJoysticks", None)
        if update_joysticks:
            update_joysticks()

    def _prime(self) -> None:
        sdl3 = self._load()
        self._pump_and_update(sdl3)
        num_buttons = self._count("SDL_GetNumJoystickButtons")
        self._previous_buttons = {}
        if num_buttons:
            get_button = getattr(sdl3, "SDL_GetJoystickButton")
            self._previous_buttons = {i: bool(get_button(self._joystick, i)) for i in range(num_buttons)}
        num_axes = self._count("SDL_GetNumJoystickAxes")
        self._previous_axes = {}
        if num_axes:
            get_axis = getattr(sdl3, "SDL_GetJoystickAxis")
            self._previous_axes = {i: int(get_axis(self._joystick, i)) for i in range(num_axes)}
        num_hats = self._count("SDL_GetNumJoystickHats")
        self._previous_hats = {}
        if num_hats:
            get_hat = getattr(sdl3, "SDL_GetJoystickHat")
            self._previous_hats = {i: int(get_hat(self._joystick, i)) for i in range(num_hats)}

    def _count(self, function_name: str) -> int:
        function = getattr(self._load(), function_name)
        return max(0, int(function(self._joystick)))

    @classmethod
    def _axis_crossed(cls, previous: int, current: int) -> bool:
        return abs(current) >= cls.AXIS_THRESHOLD and abs(previous) < cls.AXIS_THRESHOLD

    @staticmethod
    def _hat_name(value: int) -> str:
        directions = []
        if value & 1:
            directions.append("↑")
        if value & 4:
            directions.append("↓")
        if value & 8:
            directions.append("←")
        if value & 2:
            directions.append("→")
        return "Hat " + (" + ".join(directions) if directions else "center")

    @staticmethod
    def default_sequence(model_id: str) -> tuple[LogicalControl, ...]:
        if model_id == "8bitdo-m30":
            # Nomenclatura do hardware real: os quatro sentidos pertencem ao
            # mesmo D-Pad/Hat; SELECT, MODE e MENU são botões físicos distintos.
            return (
                LogicalControl.DPAD_UP, LogicalControl.DPAD_DOWN,
                LogicalControl.DPAD_LEFT, LogicalControl.DPAD_RIGHT,
                LogicalControl.FACE_SOUTH, LogicalControl.FACE_EAST,
                LogicalControl.FACE_WEST, LogicalControl.FACE_NORTH,
                LogicalControl.FACE_EXTRA_1, LogicalControl.FACE_EXTRA_2,
                LogicalControl.LEFT_SHOULDER, LogicalControl.RIGHT_SHOULDER,
                LogicalControl.START, LogicalControl.SELECT,
                LogicalControl.MODE, LogicalControl.MENU,
            )
        if model_id in {"8bitdo-ultimate-2c", "8bitdo-ultimate-2-wireless", "sony-dualshock-4", "sony-dualsense", "xbox-one-controller", "xbox-wireless-controller", "xbox-360-controller", "machenike-g5-pro"}:
            return (
                LogicalControl.DPAD_UP, LogicalControl.DPAD_DOWN, LogicalControl.DPAD_LEFT, LogicalControl.DPAD_RIGHT,
                LogicalControl.FACE_SOUTH, LogicalControl.FACE_EAST, LogicalControl.FACE_WEST, LogicalControl.FACE_NORTH,
                LogicalControl.LEFT_SHOULDER, LogicalControl.RIGHT_SHOULDER,
                LogicalControl.LEFT_TRIGGER, LogicalControl.RIGHT_TRIGGER,
                LogicalControl.LEFT_STICK, LogicalControl.RIGHT_STICK,
                LogicalControl.START, LogicalControl.BACK, LogicalControl.GUIDE,
            )
        if model_id == "logitech-g27":
            return (LogicalControl.STEERING, LogicalControl.ACCELERATOR, LogicalControl.BRAKE, LogicalControl.CLUTCH)
        return (LogicalControl.UNKNOWN,)

    @staticmethod
    def logical_label(control: LogicalControl) -> str:
        labels = {
            LogicalControl.DPAD_UP: "D-Pad ↑", LogicalControl.DPAD_DOWN: "D-Pad ↓",
            LogicalControl.DPAD_LEFT: "D-Pad ←", LogicalControl.DPAD_RIGHT: "D-Pad →",
            LogicalControl.FACE_SOUTH: "A", LogicalControl.FACE_EAST: "B",
            LogicalControl.FACE_WEST: "X", LogicalControl.FACE_NORTH: "Y",
            LogicalControl.FACE_EXTRA_1: "Z", LogicalControl.FACE_EXTRA_2: "C",
            LogicalControl.LEFT_SHOULDER: "L", LogicalControl.RIGHT_SHOULDER: "R",
            LogicalControl.LEFT_TRIGGER: "Trigger L", LogicalControl.RIGHT_TRIGGER: "Trigger R",
            LogicalControl.LEFT_STICK: "Stick L", LogicalControl.RIGHT_STICK: "Stick R",
            LogicalControl.START: "START", LogicalControl.SELECT: "SELECT",
            LogicalControl.MODE: "MODE / PAIR", LogicalControl.MENU: "MENU / HOME",
            LogicalControl.BACK: "Back", LogicalControl.GUIDE: "Guide",
            LogicalControl.STEERING: "Volante", LogicalControl.ACCELERATOR: "Acelerador",
            LogicalControl.BRAKE: "Freio", LogicalControl.CLUTCH: "Embreagem", LogicalControl.UNKNOWN: "Controle desconhecido",
        }
        return labels.get(control, control.value)


__all__ = ["ControllerInputProbeService", "ProbeEvent", "ProbeEventType"]
