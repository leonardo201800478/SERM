from serm_v2.models.input_control import ControlProfile, LogicalControl
from serm_v2.services.mame_controller_mapping_service import MameControllerMappingService


def _profile() -> ControlProfile:
    return ControlProfile(
        profile_id="m30:test",
        name="M30",
        device_id="2dc8:5006",
        bindings={
            LogicalControl.DPAD_UP: ("axis:1:-",),
            LogicalControl.DPAD_DOWN: ("axis:1:+",),
            LogicalControl.DPAD_LEFT: ("axis:0:-",),
            LogicalControl.DPAD_RIGHT: ("axis:0:+",),
            LogicalControl.FACE_SOUTH: ("button:0",),       # A
            LogicalControl.FACE_EAST: ("button:1",),        # B
            LogicalControl.FACE_EXTRA_2: ("button:2",),     # C
            LogicalControl.FACE_WEST: ("button:3",),        # X
            LogicalControl.FACE_NORTH: ("button:4",),       # Y
            LogicalControl.FACE_EXTRA_1: ("button:5",),     # Z
            LogicalControl.LEFT_SHOULDER: ("button:6",),    # L
            LogicalControl.RIGHT_SHOULDER: ("button:7",),   # R
            LogicalControl.START: ("button:8",),
            LogicalControl.SELECT: ("button:9",),
            LogicalControl.MODE: ("button:10",),
            LogicalControl.MENU: ("button:11",),
        },
    )


def test_m30_maps_six_face_buttons_and_shoulders_without_pair_button():
    mapped = MameControllerMappingService.build_m30_mapping(_profile())
    by_type = {item.mame_type: item.sequence for item in mapped}

    assert by_type["P1_BUTTON1"] == "JOYCODE_1_BUTTON1"
    assert by_type["P1_BUTTON6"] == "JOYCODE_1_BUTTON3"
    assert by_type["P1_BUTTON7"] == "JOYCODE_1_BUTTON7"
    assert by_type["P1_BUTTON8"] == "JOYCODE_1_BUTTON8"
    assert "JOYCODE_1_BUTTON11" not in by_type.values()


def test_m30_maps_dpad_digital_axes_using_raw_axis_sign():
    mapped = MameControllerMappingService.build_m30_mapping(_profile())
    by_type = {item.mame_type: item.sequence for item in mapped}

    assert by_type["P1_JOYSTICK_UP"] == "JOYCODE_1_YAXIS_UP_SWITCH"
    assert by_type["P1_JOYSTICK_DOWN"] == "JOYCODE_1_YAXIS_DOWN_SWITCH"
    assert by_type["P1_JOYSTICK_LEFT"] == "JOYCODE_1_XAXIS_LEFT_SWITCH"
    assert by_type["P1_JOYSTICK_RIGHT"] == "JOYCODE_1_XAXIS_RIGHT_SWITCH"


def test_m30_start_select_and_menu_map_to_mame_system_controls():
    mapped = MameControllerMappingService.build_m30_mapping(_profile())
    by_type = {item.mame_type: item.sequence for item in mapped}

    assert by_type["P1_START"] == "JOYCODE_1_BUTTON9"
    assert by_type["COIN1"] == "JOYCODE_1_BUTTON10"
    assert by_type["UI_MENU"] == "JOYCODE_1_BUTTON12"
    assert "MODE" not in by_type


def test_m30_street_fighter_ii_uses_arcade_button_order_and_macros():
    mapped = MameControllerMappingService.build_m30_street_fighter_ii_mapping(_profile())
    by_type = {item.mame_type: item.sequence for item in mapped}

    # SFII: 1=X, 2=Y, 3=Z, 4=A, 5=B, 6=C.
    assert by_type["P1_BUTTON1"] == "JOYCODE_1_BUTTON4 OR JOYCODE_1_BUTTON7"
    assert by_type["P1_BUTTON2"] == "JOYCODE_1_BUTTON5 OR JOYCODE_1_BUTTON7"
    assert by_type["P1_BUTTON3"] == "JOYCODE_1_BUTTON6 OR JOYCODE_1_BUTTON7"
    assert by_type["P1_BUTTON4"] == "JOYCODE_1_BUTTON1 OR JOYCODE_1_BUTTON8"
    assert by_type["P1_BUTTON5"] == "JOYCODE_1_BUTTON2 OR JOYCODE_1_BUTTON8"
    assert by_type["P1_BUTTON6"] == "JOYCODE_1_BUTTON3 OR JOYCODE_1_BUTTON8"

    assert by_type["P1_START"] == "JOYCODE_1_BUTTON9"
    assert by_type["COIN1"] == "JOYCODE_1_BUTTON10"
    assert by_type["UI_MENU"] == "JOYCODE_1_BUTTON12"


def test_m30_street_fighter_ii_ctrlr_targets_sf2_parent_system():
    xml = MameControllerMappingService.render_m30_street_fighter_ii_ctrlr(_profile())

    assert '<system name="sf2">' in xml
    assert '<port type="P1_BUTTON1">' in xml
    assert "JOYCODE_1_BUTTON4 OR JOYCODE_1_BUTTON7" in xml
    assert "JOYCODE_1_BUTTON6 OR JOYCODE_1_BUTTON7" in xml
    assert "JOYCODE_1_BUTTON3 OR JOYCODE_1_BUTTON8" in xml
    assert "MODE / PAIR" not in xml


def test_m30_ctrlr_is_valid_mame_xml_shape():
    xml = MameControllerMappingService.render_m30_ctrlr(_profile())

    assert xml.startswith('<?xml version="1.0"?>')
    assert '<mameconfig version="10">' in xml
    assert '<system name="default">' in xml
    assert '<port type="P1_BUTTON6">' in xml
    assert "MODE / PAIR" not in xml
