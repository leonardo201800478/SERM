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


def test_unknown_catalog_does_not_guess():
    result = ControllerCatalogService.default().identify(device())
    assert result.model is None
    assert result.confidence == 0
