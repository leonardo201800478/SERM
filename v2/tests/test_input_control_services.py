from serm_v2.models.input_control import InputConnection, InputDeviceType
from serm_v2.services.input_device_service import InputDeviceService
from serm_v2.services.sdl_mapping_service import SDLMappingService


def test_hid_record_preserves_physical_identity() -> None:
    device = InputDeviceService._from_hid_record(
        0,
        {
            "path": "\\\\?\\hid#usb#VID_054C&PID_0CE6",
            "vendor_id": 0x054C,
            "product_id": 0x0CE6,
            "release_number": 0x0100,
            "manufacturer_string": "Sony",
            "product_string": "DualSense Wireless Controller",
            "serial_number": "ABC123",
            "usage_page": 0x01,
            "usage": 0x05,
        },
    )

    assert device is not None
    assert device.vendor_id == 0x054C
    assert device.product_id == 0x0CE6
    assert device.serial == "ABC123"
    assert device.manufacturer == "Sony"
    assert device.connection is InputConnection.USB
    assert device.device_type is InputDeviceType.GAMEPAD
    assert device.hardware_key == "054c:0ce6:abc123"


def test_sdl_mapping_line_is_normalized() -> None:
    mapping = SDLMappingService.parse_line(
        "030000004c050000c405000000010000,PS4 Controller,a:b1,b:b2,leftx:a0,platform:Windows,"
    )

    assert mapping is not None
    assert mapping.guid == "030000004c050000c405000000010000"
    assert mapping.name == "PS4 Controller"
    assert mapping.platform == "Windows"
    assert mapping.bindings["a"] == "b1"
    assert mapping.bindings["leftx"] == "a0"
