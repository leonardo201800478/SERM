from serm_v2.models.input_control import InputConnection
from serm_v2.services.input_device_service import InputDeviceService


def test_hid_bus_type_two_is_bluetooth():
    device = InputDeviceService._from_hid_record(
        0,
        {
            "path": b"BT-HID",
            "vendor_id": 0x2DC8,
            "product_id": 0x0651,
            "product_string": "Bluetooth Wireless Controller",
            "usage_page": 1,
            "usage": 5,
            "bus_type": 2,
        },
    )
    assert device is not None
    assert device.connection == InputConnection.BLUETOOTH


def test_hid_bus_type_one_is_usb():
    device = InputDeviceService._from_hid_record(
        0,
        {
            "path": b"USB-HID",
            "vendor_id": 0x2DC8,
            "product_id": 0x5006,
            "product_string": "8BitDo M30 gamepad",
            "usage_page": 1,
            "usage": 5,
            "bus_type": 1,
        },
    )
    assert device is not None
    assert device.connection == InputConnection.USB
