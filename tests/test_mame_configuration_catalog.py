from serm_v2.services.mame_configuration_catalog import MameConfigurationCatalog


def test_parse_usage_detects_boolean_and_enum_options() -> None:
    text = """Core Video Options
-video <bgfx|gdi|d3d|opengl|soft|none>
    Specifies the video subsystem.
-[no]waitvsync
    Wait for VBLANK.
Core Sound Options
-sound <wasapi|xaudio2|none>
    Select sound module.
"""

    options = MameConfigurationCatalog._parse_usage(
        text,
        {"video": "bgfx", "waitvsync": "0", "sound": "wasapi"},
        {"video": "bgfx", "waitvsync": "0", "sound": "wasapi"},
    )
    by_key = {option.key: option for option in options}

    assert by_key["waitvsync"].value_type == "bool"
    assert by_key["waitvsync"].control_type == "checkbox"
    assert by_key["video"].value_type == "enum"
    assert by_key["video"].choices == ("bgfx", "gdi", "d3d", "opengl", "soft", "none")
    assert by_key["sound"].choices == ("wasapi", "xaudio2", "none")


def test_parse_config_uses_last_value_for_duplicate_keys() -> None:
    text = "video bgfx\nwaitvsync 0\nvideo opengl\n"
    values = MameConfigurationCatalog._parse_config(text)
    assert values == {"video": "opengl", "waitvsync": "0"}
