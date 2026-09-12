from serm_v2.models.input_control import InputConnection, InputDevice, InputDeviceType
from serm_v2.services.controller_profile_service import ControllerProfileService


def device(name, manufacturer, vid, pid, connection=InputConnection.USB):
    return InputDevice(
        device_id=f"test:{vid:04x}:{pid:04x}",
        name=name,
        manufacturer=manufacturer,
        product=name,
        vendor_id=vid,
        product_id=pid,
        connection=connection,
        bus_type=1 if connection is InputConnection.USB else 2,
        device_type=InputDeviceType.GAMEPAD,
    )


def test_m30_keeps_arcade_six_button_profile():
    profile = ControllerProfileService().resolve(device("8BitDo M30 gamepad", "8BitDo", 0x2DC8, 0x5006))
    assert profile.model_id == "8bitdo-m30"
    assert profile.input_family == "8bitdo-gamepad"
    assert "arcade-six-button" in profile.logical_roles


def test_machenike_g5_pro_is_not_collapsed_into_microsoft_xbox():
    profile = ControllerProfileService().resolve(device("Xbox 360 Controller for Windows", "MACHENIKE", 0x2345, 0xE00B))
    assert profile.model_id == "machenike-g5-pro"
    assert profile.input_family == "xinput-gamepad"


def test_g27_is_steering_wheel():
    profile = ControllerProfileService().resolve(
        InputDevice(
            device_id="g27", name="G27 Racing Wheel", manufacturer="Logitech",
            product="G27 Racing Wheel", vendor_id=0x046D, product_id=0xC29B,
            connection=InputConnection.USB, bus_type=1,
            device_type=InputDeviceType.STEERING_WHEEL,
        )
    )
    assert profile.model_id == "logitech-g27"
    assert profile.device_type is InputDeviceType.STEERING_WHEEL
    assert profile.input_family == "wheel"


def test_sony_models_are_distinguished_by_pid():
    ds4 = ControllerProfileService().resolve(device("Wireless Controller", "Sony Interactive Entertainment", 0x054C, 0x09CC, InputConnection.BLUETOOTH))
    ds5 = ControllerProfileService().resolve(device("DualSense Wireless Controller", "Sony Interactive Entertainment", 0x054C, 0x0CE6, InputConnection.BLUETOOTH))
    assert ds4.model_id == "sony-dualshock-4"
    assert ds5.model_id == "sony-dualsense"


def test_xbox_one_is_not_m30_when_using_shared_xinput_pid():
    profile = ControllerProfileService().resolve(device("Controller (Xbox One For Windows)", "Microsoft", 0x045E, 0x02FF))
    assert profile.model_id == "xbox-one-controller"
    assert profile.model_id != "8bitdo-m30"
