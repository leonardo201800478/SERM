from types import SimpleNamespace

from serm_v2.models.input_control import InputElementType
from serm_v2.services.sdl3_input_service import SDL3InputService


def test_sdl3_device_description_uses_core_metadata_only():
    fake = SimpleNamespace(
        SDL_GetGamepadNameForID=lambda _id: b"8BitDo M30 Gamepad",
        SDL_GetGamepadPathForID=lambda _id: b"usb-path",
        SDL_GetGamepadVendorForID=lambda _id: 0x2DC8,
        SDL_GetGamepadProductForID=lambda _id: 0x5006,
        SDL_GetGamepadProductVersionForID=lambda _id: 1,
        SDL_GetGamepadJoystick=lambda _gamepad: object(),
        SDL_OpenGamepad=lambda _id: object(),
        SDL_CloseGamepad=lambda _gamepad: None,
        SDL_GetNumJoystickButtons=lambda _joystick: 10,
        SDL_GetNumJoystickAxes=lambda _joystick: 2,
        SDL_GetNumJoystickHats=lambda _joystick: 1,
    )
    service = SDL3InputService()
    service._guid = lambda _module, _id: "guid"

    device = service._describe(fake, 1)

    assert device.name == "8BitDo M30 Gamepad"
    assert device.vendor_id == 0x2DC8
    assert device.product_id == 0x5006
    assert device.sdl_guid == "guid"
    assert device.backend == "sdl3"
    assert device.metadata["raw_button_count"] == 10
    assert device.metadata["raw_axis_count"] == 2
    assert device.metadata["raw_hat_count"] == 1
    assert sum(e.element_type is InputElementType.BUTTON for e in device.elements) == 10
    assert sum(e.element_type is InputElementType.AXIS for e in device.elements) == 2
    assert sum(e.element_type is InputElementType.HAT for e in device.elements) == 1


def test_safe_int_call_returns_zero_on_bad_native_value():
    assert SDL3InputService._safe_int_call(lambda _id: 42, 1) == 42
    assert SDL3InputService._safe_int_call(lambda _id: (_ for _ in ()).throw(OSError("native error")), 1) == 0


def test_sdl3_battery_is_exposed_in_device_metadata():
    class FakeGamepad:
        pass

    gamepad = FakeGamepad()
    closed = []

    def power_info(_gamepad, percent):
        percent._obj.value = 73
        return 4

    fake = SimpleNamespace(
        SDL_GetGamepadNameForID=lambda _id: b"8BitDo M30 Gamepad",
        SDL_GetGamepadPathForID=lambda _id: b"bt-path",
        SDL_GetGamepadVendorForID=lambda _id: 0x2DC8,
        SDL_GetGamepadProductForID=lambda _id: 0x0651,
        SDL_GetGamepadProductVersionForID=lambda _id: 1,
        SDL_OpenGamepad=lambda _id: gamepad,
        SDL_GetGamepadJoystick=lambda _gamepad: object(),
        SDL_GetNumJoystickButtons=lambda _joystick: 10,
        SDL_GetNumJoystickAxes=lambda _joystick: 2,
        SDL_GetNumJoystickHats=lambda _joystick: 1,
        SDL_GetGamepadPowerInfo=power_info,
        SDL_CloseGamepad=lambda value: closed.append(value),
        SDL_POWERSTATE_UNKNOWN=0,
        SDL_POWERSTATE_ON_BATTERY=1,
        SDL_POWERSTATE_NO_BATTERY=2,
        SDL_POWERSTATE_CHARGING=3,
        SDL_POWERSTATE_CHARGED=4,
        SDL_POWERSTATE_ERROR=5,
    )
    service = SDL3InputService()
    service._guid = lambda _module, _id: "guid"

    device = service._describe(fake, 1)

    assert device.metadata["battery_percent"] == 73
    assert device.metadata["battery_state"] == "charged"
    assert closed == [gamepad, gamepad]
