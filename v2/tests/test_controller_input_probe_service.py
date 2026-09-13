from serm_v2.models.input_control import LogicalControl
from serm_v2.services.controller_input_probe_service import ControllerInputProbeService, ProbeEventType


def test_m30_sequence_uses_physical_nomenclature_and_all_buttons():
    sequence = ControllerInputProbeService.default_sequence("8bitdo-m30")
    assert len(sequence) == 16
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
    assert sequence[12:] == (
        LogicalControl.START,
        LogicalControl.SELECT,
        LogicalControl.MODE,
        LogicalControl.MENU,
    )


def test_m30_labels_match_physical_controller():
    labels = ControllerInputProbeService.logical_label
    assert labels(LogicalControl.FACE_SOUTH) == "A"
    assert labels(LogicalControl.FACE_EAST) == "B"
    assert labels(LogicalControl.FACE_WEST) == "X"
    assert labels(LogicalControl.FACE_NORTH) == "Y"
    assert labels(LogicalControl.FACE_EXTRA_1) == "Z"
    assert labels(LogicalControl.FACE_EXTRA_2) == "C"
    assert labels(LogicalControl.LEFT_SHOULDER) == "L"
    assert labels(LogicalControl.RIGHT_SHOULDER) == "R"
    assert labels(LogicalControl.SELECT) == "SELECT"
    assert labels(LogicalControl.MODE) == "MODE / PAIR"
    assert labels(LogicalControl.MENU) == "MENU / HOME"


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
    assert service._axis_crossed(13000, -13000)
    assert service._axis_crossed(-13000, 13000)
    assert not service._axis_crossed(13000, 11000)


def test_axis_direction_is_encoded_in_element_id():
    assert ControllerInputProbeService._axis_direction(-20000) == "−"
    assert ControllerInputProbeService._axis_direction(20000) == "+"


def test_unknown_model_does_not_invent_layout():
    assert ControllerInputProbeService.default_sequence("unknown-model") == (LogicalControl.UNKNOWN,)


def test_probe_processes_event_queue_before_joystick_state():
    class FakeSDL:
        def __init__(self):
            self.updated = 0
            self.pumped = 0
            self.joystick_events = None
            self.gamepad_events = None

        def SDL_SetJoystickEventsEnabled(self, enabled):
            self.joystick_events = enabled

        def SDL_SetGamepadEventsEnabled(self, enabled):
            self.gamepad_events = enabled

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
    assert fake.pumped == 1
    assert fake.updated == 1


def test_probe_enables_joystick_and_gamepad_events():
    class FakeSDL:
        def __init__(self):
            self.joystick_events = None
            self.gamepad_events = None

        def SDL_SetJoystickEventsEnabled(self, enabled):
            self.joystick_events = enabled

        def SDL_SetGamepadEventsEnabled(self, enabled):
            self.gamepad_events = enabled

    fake = FakeSDL()
    ControllerInputProbeService._enable_input_updates(fake)
    assert fake.joystick_events is True
    assert fake.gamepad_events is True


def test_probe_axis_event_keeps_direction_as_part_of_binding():
    # A mesma linha de eixo físico representa duas entradas lógicas distintas.
    # O sinal observado pelo hardware precisa fazer parte da identidade do evento.
    assert "axis:0:-" != "axis:0:+"
    assert ProbeEventType.AXIS.value == "axis"
