from serm_v2.models.input_control import LogicalControl
from serm_v2.services.controller_input_probe_service import ControllerInputProbeService


def test_m30_sequence_contains_all_physical_button_roles():
    sequence = ControllerInputProbeService.default_sequence("8bitdo-m30")
    assert len(sequence) == 15
    assert sequence[:4] == (
        LogicalControl.DPAD_UP,
        LogicalControl.DPAD_DOWN,
        LogicalControl.DPAD_LEFT,
        LogicalControl.DPAD_RIGHT,
    )
    assert sequence[4:10] == (
        LogicalControl.FACE_SOUTH,
        LogicalControl.FACE_EAST,
        LogicalControl.FACE_WEST,
        LogicalControl.FACE_NORTH,
        LogicalControl.FACE_EXTRA_1,
        LogicalControl.FACE_EXTRA_2,
    )
    assert sequence[10:12] == (LogicalControl.LEFT_SHOULDER, LogicalControl.RIGHT_SHOULDER)
    assert sequence[12:] == (LogicalControl.START, LogicalControl.GUIDE, LogicalControl.BACK)


def test_hat_name_handles_diagonal_and_center():
    assert ControllerInputProbeService._hat_name(0) == "Hat center"
    assert ControllerInputProbeService._hat_name(1) == "Hat ↑"
    assert ControllerInputProbeService._hat_name(3) == "Hat ↑ + →"
    assert ControllerInputProbeService._hat_name(12) == "Hat ↓ + ←"


def test_axis_threshold_only_reports_new_crossing():
    service = ControllerInputProbeService()
    assert service._axis_crossed(0, 12001)
    assert not service._axis_crossed(13000, 14000)
    assert service._axis_crossed(-1000, -13000)


def test_unknown_model_does_not_invent_layout():
    assert ControllerInputProbeService.default_sequence("unknown-model") == (LogicalControl.UNKNOWN,)


def test_probe_prefers_update_joysticks_over_event_pump():
    class FakeSDL:
        def __init__(self):
            self.updated = 0
            self.pumped = 0

        def SDL_UpdateJoysticks(self):
            self.updated += 1

        def SDL_PumpEvents(self):
            self.pumped += 1

        def SDL_GetNumJoystickButtons(self, joystick):
            return 0

        def SDL_GetNumJoystickAxes(self, joystick):
            return 0

        def SDL_GetNumJoystickHats(self, joystick):
            return 0

    fake = FakeSDL()
    service = ControllerInputProbeService(fake)
    service._joystick = object()
    assert service.poll() == ()
    assert fake.updated == 1
    assert fake.pumped == 0
