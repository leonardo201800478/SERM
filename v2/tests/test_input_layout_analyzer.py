from serm_v2.models.input_control import InputDevice, InputDeviceType, InputElement, InputElementType, LogicalControl
from serm_v2.services.input_layout_analyzer import InputLayoutAnalyzer


def test_detects_six_button_gamepad() -> None:
    controls = (
        LogicalControl.FACE_SOUTH,
        LogicalControl.FACE_EAST,
        LogicalControl.FACE_WEST,
        LogicalControl.FACE_NORTH,
        LogicalControl.FACE_EXTRA_1,
        LogicalControl.FACE_EXTRA_2,
    )
    elements = tuple(
        InputElement(
            element_id=f"b{index}",
            element_type=InputElementType.BUTTON,
            name=f"face_{index}",
            index=index,
            logical_control=control,
        )
        for index, control in enumerate(controls)
    )
    device = InputDevice(
        device_id="m30:test",
        name="8BitDo M30",
        device_type=InputDeviceType.GAMEPAD,
        elements=elements,
    )

    summary = InputLayoutAnalyzer().analyze(device)

    assert summary.buttons == 6
    assert summary.has_six_face_buttons is True
    assert summary.profile_kind == "six-button-gamepad"


def test_detects_steering_wheel_profile() -> None:
    device = InputDevice(
        device_id="g27:test",
        name="Logitech G27",
        device_type=InputDeviceType.STEERING_WHEEL,
        elements=(
            InputElement("axis0", InputElementType.AXIS, "steering"),
            InputElement("axis1", InputElementType.AXIS, "pedal"),
        ),
    )

    summary = InputLayoutAnalyzer().analyze(device)

    assert summary.axes == 2
    assert summary.profile_kind == "steering-wheel"
