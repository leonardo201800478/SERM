from dataclasses import replace

from serm_v2.models.input_control import InputDevice, InputDeviceType, InputConnection, InputElementType
from serm_v2.services.input_control_service import InputControlService


class FakeDeviceService:
    def __init__(self, devices):
        self.devices = devices

    def enumerate_hid(self):
        return self.devices


class FakeCorrelationService:
    def correlate(self, physical, logical):
        return ()


class FakeCatalogService:
    def identify(self, device):
        return replace(device, display_name=f"Catalog: {device.display_name}")


class FakeLayoutAnalyzer:
    def analyze(self, device):
        return type("Layout", (), {"profile_kind": "six-button-gamepad", "button_count": 6})()


class FakeMapper:
    def map_mame(self, requirements, device, profile):
        return (requirements, device, profile)


class FakeMameService:
    def read_machine(self, xml_path, machine_name):
        return (xml_path, machine_name)


def _device():
    return InputDevice(
        device_id="hid-1",
        device_type=InputDeviceType.GAMEPAD,
        connection=InputConnection.USB,
        display_name="Test Controller",
        manufacturer="Test",
        product="Controller",
        vendor_id=0x1234,
        product_id=0x5678,
        product_version=1,
        serial_number="ABC",
        path="\\\\?\\hid#test",
        elements=(
            type("Element", (), {"element_type": InputElementType.BUTTON})(),
        ),
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
    )

    snapshot = service.discover()

    assert snapshot.physical_devices == (device,)
    assert len(snapshot.devices) == 1
    assert snapshot.devices[0].device.display_name == "Test Controller"
    assert snapshot.devices[0].identification.display_name == "Catalog: Test Controller"
    assert snapshot.devices[0].layout.profile_kind == "six-button-gamepad"
    assert snapshot.devices[0].layout.button_count == 6


def test_facade_delegates_mame_mapping_and_machine_read():
    device = _device()
    mapper = FakeMapper()
    mame = FakeMameService()
    service = InputControlService(
        device_service=FakeDeviceService(()),
        mapper=mapper,
        mame_control_service=mame,
    )
    requirements = object()
    profile = object()

    assert service.map_mame(requirements, device, profile) == (requirements, device, profile)
    assert service.read_mame_machine("catalog.xml", "pacman") == ("catalog.xml", "pacman")
