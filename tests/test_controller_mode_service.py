from serm_v2.models.input_control import InputConnection, InputDevice, InputDeviceType
from serm_v2.services.controller_mode_service import ControllerModeService


def device(vendor, product, *, name="Controller", connection=InputConnection.BLUETOOTH, bus_type=2):
    return InputDevice(
        device_id="d1",
        name=name,
        device_type=InputDeviceType.GAMEPAD,
        connection=connection,
        vendor_id=vendor,
        product_id=product,
        bus_type=bus_type,
    )


def test_m30_bluetooth_dinput_is_confirmed():
    match = ControllerModeService.identify_m30(device(0x2DC8, 0x0651))
    assert match is not None
    assert match.mode_id == "dinput"
    assert match.confirmed
    assert match.confidence == 100


def test_m30_usb_dinput_is_confirmed():
    match = ControllerModeService.identify_m30(
        device(0x2DC8, 0x5006, name="8BitDo M30 gamepad", connection=InputConnection.USB, bus_type=1)
    )
    assert match is not None
    assert match.mode_id == "dinput-usb"
    assert match.confirmed
    assert match.connection == "USB"


def test_generic_xinput_signature_is_not_claimed_as_unique_m30():
    match = ControllerModeService.identify_m30(device(0x045E, 0x02E0, name="Xbox Bluetooth Gamepad"))
    assert match is None


def test_explicit_m30_name_on_shared_xinput_signature_remains_unconfirmed():
    match = ControllerModeService.identify_m30(
        device(0x045E, 0x02E0, name="8BitDo M30 Controller Xbox 360 Controller")
    )
    assert match is not None
    assert not match.confirmed
    assert match.confidence == 70
    assert match.mode_id == "xinput-bt"


def test_m30_no_longer_claims_generic_switch_signature():
    assert ControllerModeService.identify_m30(device(0x057E, 0x2009, name="Wireless Gamepad")) is None


def test_generic_switch_signature_is_neutral():
    match = ControllerModeService.identify_generic_switch(
        device(0x057E, 0x2009, name="Pro Controller", connection=InputConnection.USB, bus_type=1)
    )
    assert match is not None
    assert match.model_id == "generic-switch-pro-controller"
    assert match.mode_id == "switch"
    assert match.connection == "USB"
    assert not match.confirmed
    assert match.confidence == 100


def test_identify_does_not_mislabel_generic_switch_as_m30():
    match = ControllerModeService.identify(
        device(0x057E, 0x2009, name="Pro Controller", connection=InputConnection.USB, bus_type=1)
    )
    assert match is not None
    assert match.model_id == "generic-switch-pro-controller"
    assert match.model_name == "Nintendo Switch Pro Controller (genérico)"
    assert not match.confirmed


def test_ultimate_2_wireless_xinput_24g_is_confirmed():
    match = ControllerModeService.identify_ultimate_2(
        device(
            0x2DC8,
            0x310B,
            name="8BitDo Ultimate 2 Wireless Controller for PC",
            connection=InputConnection.USB,
            bus_type=1,
        )
    )
    assert match is not None
    assert match.model_id == "8bitdo-ultimate-2-wireless"
    assert match.mode_id == "xinput-2p4g-or-usb"
    assert match.confirmed
    assert match.confidence == 100


def test_ultimate_2_wireless_xinput_usb_is_confirmed():
    match = ControllerModeService.identify_ultimate_2(
        device(
            0x2DC8,
            0x310B,
            name="8BitDo Ultimate 2 Wireless Controller for PC",
            connection=InputConnection.USB,
            bus_type=1,
        )
    )
    assert match is not None
    assert match.mode_name == "XInput / 2.4G ou USB"


def test_ultimate_2_wireless_dinput_usb_is_confirmed():
    match = ControllerModeService.identify_ultimate_2(
        device(
            0x2DC8,
            0x6012,
            name="8BitDo Ultimate 2 Wireless Controller for PC",
            connection=InputConnection.USB,
            bus_type=1,
        )
    )
    assert match is not None
    assert match.model_id == "8bitdo-ultimate-2-wireless"
    assert match.mode_id == "dinput-2p4g-usb-bt"
    assert match.mode_name == "D-Input / 2.4G, USB ou Bluetooth"
    assert match.confirmed
    assert match.connection == "USB"


def test_ultimate_2_wireless_dinput_bluetooth_is_confirmed():
    match = ControllerModeService.identify_ultimate_2(
        device(
            0x2DC8,
            0x6012,
            name="8BitDo Ultimate 2 Wireless",
            connection=InputConnection.BLUETOOTH,
            bus_type=2,
        )
    )
    assert match is not None
    assert match.mode_id == "dinput-2p4g-usb-bt"
    assert match.connection == "Bluetooth"
    assert match.confirmed


def test_ultimate_2_wireless_receiver_idle_is_identified():
    match = ControllerModeService.identify_ultimate_2(
        device(
            0x2DC8,
            0x6013,
            name="Ultimate 2",
            connection=InputConnection.USB,
            bus_type=1,
        )
    )
    assert match is not None
    assert match.model_id == "8bitdo-ultimate-2-wireless"
    assert match.mode_id == "receiver-idle"
    assert match.confirmed


def test_ultimate_2_wireless_switch_signature_is_not_globally_claimed():
    assert ControllerModeService.identify_ultimate_2(device(0x057E, 0x2009, name="Pro Controller")) is None


def test_ultimate_2c_24g_or_usb_signature_is_confirmed():
    match = ControllerModeService.identify_ultimate_2c(
        device(
            0x2DC8,
            0x310A,
            name="8BitDo Ultimate 2C Wireless Controller",
            connection=InputConnection.USB,
            bus_type=1,
        )
    )
    assert match is not None
    assert match.model_id == "8bitdo-ultimate-2c"
    assert match.mode_id == "xinput-usb-2p4g"
    assert match.confirmed
    assert match.confidence == 100


def test_ultimate_2c_bluetooth_301b_is_confirmed():
    match = ControllerModeService.identify_ultimate_2c(
        device(
            0x2DC8,
            0x301B,
            name="8BitDo Ultimate 2C Wireless",
            connection=InputConnection.BLUETOOTH,
            bus_type=2,
        )
    )
    assert match is not None
    assert match.model_id == "8bitdo-ultimate-2c"
    assert match.mode_id == "bluetooth"
    assert match.connection == "Bluetooth"
    assert match.confirmed


def test_ultimate_2c_bluetooth_3013_variant_is_supported():
    match = ControllerModeService.identify_ultimate_2c(
        device(
            0x2DC8,
            0x3013,
            name="8BitDo Ultimate 2C Wireless",
            connection=InputConnection.BLUETOOTH,
            bus_type=2,
        )
    )
    assert match is not None
    assert match.model_id == "8bitdo-ultimate-2c"
    assert match.mode_id == "bluetooth"


def test_generic_045e_does_not_identify_as_ultimate_2c():
    assert ControllerModeService.identify_ultimate_2c(device(0x045E, 0x028E)) is None


def test_unknown_signature_returns_none():
    assert ControllerModeService.identify(device(0x1234, 0x5678)) is None
