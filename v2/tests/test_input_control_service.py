from serm_v2.models.input_control import InputConnection, InputDevice, InputDeviceType, InputElement, InputElementType
from serm_v2.services.input_control_service import InputControlService


class FakeDeviceService:
    def __init__(self, devices):
        self.devices = devices

    def enumerate_hid(self):
        return self.devices


class FakeCorrelationService:
    def __init__(self):
        self.calls = []

    def correlate(self, physical, logical):
        self.calls.append((physical, logical))
        return ()


class FakeCatalogService:
    def identify(self, device):
        return type("Identification", (), {"display_name": f"Catalog: {device.name}"})()


class FakeLayoutAnalyzer:
    def analyze(self, device):
        return type("Layout", (), {"profile_kind": "six-button-gamepad", "button_count": 6})()


class FakeMapper:
    def map_mame(self, requirements, device, profile):
        return requirements, device, profile


class FakeMameService:
    def read_machine(self, xml_path, machine_name):
        return xml_path, machine_name


class FakeSDL3Service:
    def __init__(self, devices=()):
        self.devices = devices
        self.initialize_calls = 0
        self.enumerate_calls = 0

    def initialize(self):
        self.initialize_calls += 1

    def enumerate(self):
        self.enumerate_calls += 1
        return self.devices


def _device():
    return InputDevice(
        device_id="hid-1",
        name="Test Controller",
        device_type=InputDeviceType.GAMEPAD,
        connection=InputConnection.USB,
        manufacturer="Test",
        product="Controller",
        vendor_id=0x1234,
        product_id=0x5678,
        version=1,
        serial="ABC",
        path="\\\\?\\hid#test",
        elements=(InputElement("button-1", InputElementType.BUTTON, "B1", index=0),),
    )


def test_discover_builds_consolidated_snapshot():
    device = _device()
    service = InputControlService(
        device_service=FakeDeviceService((device,)),
        correlation_service=FakeCorrelationService(),
        catalog_service=FakeCatalogService(),
        layout_analyzer=FakeLayoutAnalyzer(),
        mapper=FakeMapper(),
        mame_control_service=FakeMameService(),
        sdl3_input_service=FakeSDL3Service(),
    )

    snapshot = service.discover()

    assert snapshot.physical_devices == (device,)
    assert snapshot.logical_devices == ()
    assert len(snapshot.devices) == 1
    assert snapshot.devices[0].device.name == "Test Controller"
    assert snapshot.devices[0].identification.display_name == "Catalog: Test Controller"
    assert snapshot.devices[0].layout.profile_kind == "six-button-gamepad"
    assert snapshot.devices[0].layout.button_count == 6


def test_discover_enumerates_sdl3_and_passes_logical_devices_to_correlation():
    physical = _device()
    logical = InputDevice(
        device_id="sdl3:7",
        name="SDL Controller",
        device_type=InputDeviceType.GAMEPAD,
        backend="sdl3",
    )
    correlation = FakeCorrelationService()
    sdl = FakeSDL3Service((logical,))
    service = InputControlService(
        device_service=FakeDeviceService((physical,)),
        correlation_service=correlation,
        catalog_service=FakeCatalogService(),
        layout_analyzer=FakeLayoutAnalyzer(),
        sdl3_input_service=sdl,
    )

    snapshot = service.discover()

    assert snapshot.logical_devices == (logical,)
    assert correlation.calls == [((physical,), (logical,))]
    assert sdl.initialize_calls == 1
    assert sdl.enumerate_calls == 1


def test_discover_keeps_hid_diagnostics_when_sdl3_is_unavailable():
    physical = _device()

    class UnavailableSDL3:
        def initialize(self):
            raise RuntimeError("SDL unavailable")

        def enumerate(self):
            raise AssertionError("enumerate must not run after initialization failure")

    service = InputControlService(
        device_service=FakeDeviceService((physical,)),
        correlation_service=FakeCorrelationService(),
        catalog_service=FakeCatalogService(),
        layout_analyzer=FakeLayoutAnalyzer(),
        sdl3_input_service=UnavailableSDL3(),
    )

    snapshot = service.discover()

    assert snapshot.physical_devices == (physical,)
    assert snapshot.logical_devices == ()
    assert len(snapshot.devices) == 1


def test_discover_accepts_explicit_logical_devices_without_reenumerating_sdl3():
    physical = _device()
    logical = InputDevice(device_id="sdl3:9", name="Explicit SDL", device_type=InputDeviceType.GAMEPAD, backend="sdl3")
    sdl = FakeSDL3Service((InputDevice(device_id="sdl3:10", name="Ignored", device_type=InputDeviceType.GAMEPAD),))
    service = InputControlService(
        device_service=FakeDeviceService((physical,)),
        correlation_service=FakeCorrelationService(),
        catalog_service=FakeCatalogService(),
        layout_analyzer=FakeLayoutAnalyzer(),
        sdl3_input_service=sdl,
    )

    snapshot = service.discover((logical,))

    assert snapshot.logical_devices == (logical,)
    assert sdl.initialize_calls == 0
    assert sdl.enumerate_calls == 0


def test_facade_delegates_mame_mapping_and_machine_read():
    device = _device()
    service = InputControlService(
        device_service=FakeDeviceService(()),
        mapper=FakeMapper(),
        mame_control_service=FakeMameService(),
        sdl3_input_service=FakeSDL3Service(),
    )
    requirements = object()
    profile = object()

    assert service.map_mame(requirements, device, profile) == (requirements, device, profile)
    assert service.read_mame_machine("catalog.xml", "pacman") == ("catalog.xml", "pacman")
