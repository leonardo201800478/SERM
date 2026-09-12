from serm_v2.models.input_control import ControlProfile, InputDevice, InputDeviceType, InputElement, InputElementType, LogicalControl
from serm_v2.services.mame_control_service import MameControlRequirement, MameInputRequirements
from serm_v2.services.system_control_mapper import SystemControlMapper


def _m30() -> InputDevice:
    controls = (
        LogicalControl.FACE_SOUTH,
        LogicalControl.FACE_EAST,
        LogicalControl.FACE_WEST,
        LogicalControl.FACE_NORTH,
        LogicalControl.FACE_EXTRA_1,
        LogicalControl.FACE_EXTRA_2,
    )
    return InputDevice(
        device_id="m30:test",
        name="8BitDo M30",
        device_type=InputDeviceType.GAMEPAD,
        elements=tuple(
            InputElement(f"b{i}", InputElementType.BUTTON, f"button_{i}", i, control)
            for i, control in enumerate(controls)
        ),
    )


def test_six_button_device_is_compatible_with_six_button_system() -> None:
    device = _m30()
    profile = ControlProfile(
        profile_id="m30",
        name="8BitDo M30",
        device_id=device.device_id,
        bindings={
            control: (f"b{i}",)
            for i, control in enumerate(
                (
                    LogicalControl.FACE_SOUTH,
                    LogicalControl.FACE_EAST,
                    LogicalControl.FACE_WEST,
                    LogicalControl.FACE_NORTH,
                    LogicalControl.FACE_EXTRA_1,
                    LogicalControl.FACE_EXTRA_2,
                )
            )
        },
    )
    requirements = MameInputRequirements(
        machine_name="test",
        players=1,
        coins=1,
        service=False,
        controls=(MameControlRequirement("joystick", player=1, buttons=6, ways=8),),
    )

    result = SystemControlMapper().map_mame(requirements, device, profile)

    assert result.compatible is True
    assert result.score >= 90
    assert len(result.suggestions) == 6


def test_four_button_requirement_warns_for_smaller_device() -> None:
    device = InputDevice(
        device_id="pad:test",
        name="Pad",
        device_type=InputDeviceType.GAMEPAD,
        elements=(InputElement("b0", InputElementType.BUTTON, "button_0", 0),),
    )
    requirements = MameInputRequirements(
        machine_name="test",
        players=1,
        coins=1,
        service=False,
        controls=(MameControlRequirement("joystick", player=1, buttons=4),),
    )

    result = SystemControlMapper().map_mame(requirements, device)

    assert result.compatible is False
    assert any("oferece" in warning for warning in result.warnings)
