"""Testes da arquitetura atual Schema × Adapter dos cinco emuladores.

Este arquivo é exclusivamente arquitetural: não instancia GUI, não baixa
arquivos e não depende de instalações reais. Testa somente o contrato central
que as abas deverão consumir.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.emulators.adapter_registry import get_adapter, list_adapters
from app.emulators.capabilities import get_capabilities
from app.emulators.config_mapping import validate_mappings
from app.emulators.runtime import discover_all


EMULATORS = ("mame", "flycast", "supermodel", "fbneo", "retroarch")


@pytest.mark.parametrize("emulator", EMULATORS)
def test_schema_adapter_capabilities_share_the_same_identity(emulator: str) -> None:
    """Schema, adapter e capabilities devem reconhecer o mesmo identificador."""
    adapter = get_adapter(emulator)
    assert adapter.emulator == emulator
    assert get_capabilities(emulator).emulator == emulator
    assert adapter.schema()
    assert adapter.capabilities.emulator == emulator


def test_registry_contains_exactly_the_current_five_emulators() -> None:
    """Impede regressão para registros incompletos ou duplicados."""
    assert tuple(item.emulator for item in list_adapters()) == EMULATORS


@pytest.mark.parametrize(
    ("emulator", "install", "expected"),
    [
        ("mame", Path("C:/MAME"), Path("C:/MAME/mame.ini")),
        ("flycast", Path("C:/Flycast"), Path("C:/Flycast/emu.cfg")),
        ("supermodel", Path("C:/Supermodel"), Path("C:/Supermodel/Config/Supermodel.ini")),
        ("fbneo", Path("C:/FBNeo"), Path("C:/FBNeo/config/fbneo64.ini")),
        ("retroarch", Path("C:/RetroArch"), Path("C:/RetroArch/retroarch.cfg")),
    ],
)
def test_adapter_owns_native_config_location(emulator: str, install: Path, expected: Path) -> None:
    """A localização física deve ser uma propriedade do adapter, não da GUI."""
    assert get_adapter(emulator).config_path(install) == expected


def test_all_mappings_reference_existing_schema_keys() -> None:
    """Nenhum mapping pode ficar órfão após alteração do schema."""
    assert validate_mappings() == ()


def test_mame_mapping_uses_schema_native_names() -> None:
    """Evita a antiga divergência sync_refresh/keep_aspect versus schema MAME."""
    from app.emulators.config_mapping import physical_key

    assert physical_key("mame", "waitvsync") == "waitvsync"
    assert physical_key("mame", "syncrefresh") == "syncrefresh"
    assert physical_key("mame", "keepaspect") == "keepaspect"
    assert physical_key("mame", "sync_refresh") is None
    assert physical_key("mame", "keep_aspect") is None


@pytest.mark.parametrize("emulator", EMULATORS)
def test_directory_contract_has_no_duplicate_keys(emulator: str) -> None:
    """Cada adapter deve expor chaves de diretório únicas e rótulos úteis."""
    adapter = get_adapter(emulator)
    keys = [item.key for item in adapter.directories]
    assert len(keys) == len(set(keys))
    assert all(item.label.strip() for item in adapter.directories)
    assert all(item.max_entries >= 1 for item in adapter.directories)


def test_directory_contract_has_expected_special_cases() -> None:
    """Preserva os contratos especiais de MAME e Flycast."""
    mame = get_adapter("mame")
    flycast = get_adapter("flycast")

    mame_roms = mame.directory("roms")
    assert mame_roms.multiple is True
    assert mame_roms.max_entries == 5
    assert mame_roms.native_key == "rompath"

    flycast_roms = flycast.directory("roms")
    assert flycast_roms.multiple is True
    assert flycast_roms.max_entries == 4
    assert flycast_roms.native_key == "Dreamcast.ContentPath"


def test_retroarch_directory_contract_is_distinct_from_rom_paths() -> None:
    """RetroArch deve expor diretórios próprios, sem inventar um ROM path nativo."""
    retroarch = get_adapter("retroarch")
    keys = {item.key for item in retroarch.directories}
    assert {"cores", "system", "saves", "states", "shaders", "overlays"} <= keys
    assert retroarch.directory("shaders").relative_default == "shaders"
    assert retroarch.directory("overlays").relative_default == "overlays"


def test_retroarch_schema_covers_the_current_settings_gui_contract() -> None:
    """Os campos globais administrados pela GUI devem existir no schema canônico."""
    schema_keys = {
        setting.key
        for settings in get_adapter("retroarch").schema().values()
        for setting in settings
    }
    gui_keys = {
        "video_driver", "audio_driver", "input_driver",
        "video_fullscreen", "video_windowed_fullscreen", "video_vsync", "video_threaded",
        "video_fullscreen_x", "video_fullscreen_y", "video_refresh_rate",
        "video_hdr_enable", "video_hdr_max_nits",
        "audio_enable", "audio_out_rate", "audio_latency", "audio_sync", "audio_rate_control",
        "input_joypad_driver", "input_autodetect_enable", "input_axis_threshold",
        "input_analog_deadzone", "input_analog_sensitivity", "input_remap_binds_enable",
        "video_shader_enable", "video_shader", "video_shader_dir",
    }
    assert gui_keys <= schema_keys


@pytest.mark.parametrize("emulator", EMULATORS)
def test_runtime_discovery_returns_all_five_without_executing_missing_installations(tmp_path: Path, emulator: str) -> None:
    """A camada runtime deve devolver os cinco estados sem executar instalações ausentes."""
    paths = {name: tmp_path / name for name in EMULATORS}
    result = discover_all(paths)
    assert tuple(result) == EMULATORS
    state = result[emulator]
    assert state.emulator == emulator
    assert state.executable is None
    assert state.available is False
    assert state.installation_state == "not_installed"
