from types import SimpleNamespace

from serm_v2.services.sdl3_input_service import SDL3InputService


def test_sdl3_device_description_uses_core_metadata_only():
    fake = SimpleNamespace(
        SDL_GetGamepadNameForID=lambda _id: b"8BitDo M30 Gamepad",
        SDL_GetGamepadPathForID=lambda _id: b"usb-path",
        SDL_GetGamepadVendorForID=lambda _id: 0x2DC8,
        SDL_GetGamepadProductForID=lambda _id: 0x5006,
        SDL_GetGamepadProductVersionForID=lambda _id: 1,
        SDL_GetRealGamepadTypeForID=lambda _id: -1,
        SDL_GAMEPAD_TYPE_XBOX360=1,
        SDL_GAMEPAD_TYPE_XBOXONE=2,
        SDL_GAMEPAD_TYPE_XBOX_SERIES=3,
        SDL_GAMEPAD_TYPE_PS3=4,
        SDL_GAMEPAD_TYPE_PS4=5,
        SDL_GAMEPAD_TYPE_PS5=6,
        SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_PRO=7,
    )
    service = SDL3InputService()
    service._guid = lambda _module, _id: "guid"
    service._mapping = lambda _module, _id: None

    device = service._describe(fake, 1)

    assert device.name == "8BitDo M30 Gamepad"
    assert device.vendor_id == 0x2DC8
    assert device.product_id == 0x5006
    assert device.sdl_guid == "guid"
    assert device.backend == "sdl3"


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
    assert closed == [gamepad]
