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
from app.emulators.config_schema import get_schema
from app.emulators.runtime import discover_all


EMULATORS = ("mame", "flycast", "supermodel", "fbneo", "retroarch")


@pytest.mark.parametrize("emulator", EMULATORS)
def test_schema_adapter_capabilities_share_the_same_identity(emulator: str) -> None:
    """Schema, adapter e capabilities devem reconhecer o mesmo identificador."""
    adapter = get_adapter(emulator)
    assert adapter.emulator == emulator
    assert get_capabilities(emulator).emulator == emulator
    assert get_schema(emulator)
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


def test_runtime_discovery_returns_all_five_without_executing_missing_installations(tmp_path: Path) -> None:
    """A camada runtime deve devolver cinco estados mesmo sem emuladores instalados."""
    paths = {name: tmp_path / name for name in EMULATORS}
    result = discover_all(paths)
    assert tuple(result) == EMULATORS
    for emulator in EMULATORS:
        state = result[emulator]
        assert state.emulator == emulator
        assert state.executable is None
        assert state.available is False
        assert state.installation_state == "not_installed"
