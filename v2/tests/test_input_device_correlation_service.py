from serm_v2.models.input_control import InputConnection, InputDevice, InputDeviceType
from serm_v2.services.input_device_correlation_service import InputDeviceCorrelationService


def test_correlates_by_vid_pid_and_product() -> None:
    physical = InputDevice(
        device_id="hid:path:one",
        name="8BitDo M30",
        device_type=InputDeviceType.GAMEPAD,
        connection=InputConnection.USB,
        vendor_id=0x2DC8,
        product_id=0x3106,
        product="8BitDo M30",
        manufacturer="8BitDo",
        backend="hidapi",
    )
    logical = InputDevice(
        device_id="sdl3:42",
        name="8BitDo M30",
        vendor_id=0x2DC8,
        product_id=0x3106,
        product="8BitDo M30",
        manufacturer="8BitDo",
        sdl_guid="m30-guid",
        backend="sdl3",
    )

    result = InputDeviceCorrelationService.best_match(physical, [logical])

    assert result is not None
    assert result.logical.device_id == "sdl3:42"
    assert result.score >= 90
    assert "VID" in result.reasons
    assert "PID" in result.reasons


def test_does_not_match_unrelated_device() -> None:
    physical = InputDevice(
        device_id="hid:path:one",
        name="Controller A",
        vendor_id=0x1111,
        product_id=0x2222,
    )
    logical = InputDevice(
        device_id="sdl3:2",
        name="Controller B",
        vendor_id=0x3333,
        product_id=0x4444,
    )

    assert InputDeviceCorrelationService.best_match(physical, [logical]) is None
