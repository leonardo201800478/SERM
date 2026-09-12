from serm_v2.services.controller_input_probe_service import ControllerInputProbeService, ProbeEventType


class FakeSDL:
    def __init__(self):
        self.buttons = [False, False]
        self.axes = [0]
        self.hats = [0]
        self.gamepad = object()
        self.joystick = object()
        self.closed = []

    def SDL_OpenGamepad(self, instance_id):
        return self.gamepad

    def SDL_GetGamepadJoystick(self, gamepad):
        return self.joystick

    def SDL_CloseGamepad(self, gamepad):
        self.closed.append(gamepad)

    def SDL_PumpEvents(self):
        return None

    def SDL_GetNumJoystickButtons(self, joystick):
        return len(self.buttons)

    def SDL_GetJoystickButton(self, joystick, index):
        return self.buttons[index]

    def SDL_GetNumJoystickAxes(self, joystick):
        return len(self.axes)

    def SDL_GetJoystickAxis(self, joystick, index):
        return self.axes[index]

    def SDL_GetNumJoystickHats(self, joystick):
        return len(self.hats)

    def SDL_GetJoystickHat(self, joystick, index):
        return self.hats[index]


def test_probe_detects_new_raw_button_press():
    fake = FakeSDL()
    probe = ControllerInputProbeService(fake)
    probe.start(123)
    assert probe.poll() == ()
    fake.buttons[1] = True
    events = probe.poll()
    assert len(events) == 1
    assert events[0].element_id == "button:1"
    assert events[0].element_type is ProbeEventType.BUTTON
    probe.stop()
    assert fake.closed == [fake.gamepad]


def test_probe_detects_axis_crossing_and_hat_change():
    fake = FakeSDL()
    probe = ControllerInputProbeService(fake)
    probe.start(123)
    fake.axes[0] = 16000
    fake.hats[0] = 1
    events = probe.poll()
    assert {event.element_id for event in events} == {"axis:0", "hat:0"}
    assert {event.element_type for event in events} == {ProbeEventType.AXIS, ProbeEventType.HAT}
    probe.stop()
