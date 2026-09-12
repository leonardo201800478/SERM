from serm_v2.models.input_control import InputDevice, InputDeviceType
from serm_v2.services.controller_catalog_service import ControllerCatalogEntry, ControllerCatalogService


def device(**kwargs):
    return InputDevice(device_id="d1", name="8BitDo M30", **kwargs)


def test_identifies_model_by_name_with_confidence():
    entry = ControllerCatalogEntry(
        model_id="8bitdo-m30",
        manufacturer="8BitDo",
        model_name="M30",
        aliases=("M30",),
        device_type=InputDeviceType.GAMEPAD,
        expected_face_buttons=6,
    )
    result = ControllerCatalogService((entry,)).identify(device(product="8BitDo M30"))
    assert result.model == entry
    assert result.confidence >= 60


def test_rejects_ambiguous_models():
    entries = (
        ControllerCatalogEntry("a", "Acme", "Pad", InputDeviceType.GAMEPAD, aliases=("Pad",)),
        ControllerCatalogEntry("b", "Other", "Pad", InputDeviceType.GAMEPAD, aliases=("Pad",)),
    )
    result = ControllerCatalogService(entries).identify(device())
    assert result.model is None


def test_default_catalog_identifies_verified_m30():
    result = ControllerCatalogService.default().identify(
        device(vendor_id=0x2DC8, product_id=0x5006, product="8BitDo M30 Gamepad")
    )
    assert result.model is not None
    assert result.model.model_id == "8bitdo-m30"
    assert result.model.expected_face_buttons == 6
    assert result.confidence >= 60


def test_unknown_catalog_does_not_guess():
    result = ControllerCatalogService(()).identify(
        InputDevice(device_id="unknown", name="Unknown Controller", device_type=InputDeviceType.GAMEPAD)
    )
    assert result.model is None
    assert result.confidence == 0
