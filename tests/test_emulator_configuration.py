"""Testes de regressão para a camada de configuração dos cinco emuladores.

Os testes não dependem de instalações reais: usam arquivos temporários para
validar leitura, escrita, preservação de opções desconhecidas e limites dos
adaptadores. A descoberta de executáveis continua sendo responsabilidade do
ambiente real.
"""
from __future__ import annotations

from pathlib import Path

from app.emulators.capabilities import get_capabilities
from app.emulators.fbneo_config import FBNeoConfig
from app.emulators.flycast_config import FlycastConfig
from app.emulators.retroarch_config import RetroArchConfig
from app.emulators.supermodel_config import SupermodelConfig


def test_all_five_emulators_are_registered() -> None:
    """Garante registro de capacidades para os cinco emuladores."""
    for emulator in ("mame", "flycast", "supermodel", "fbneo", "retroarch"):
        capabilities = get_capabilities(emulator)
        assert capabilities.emulator == emulator
        assert capabilities.domains


def test_flycast_preserves_unknown_configuration(tmp_path: Path) -> None:
    """Flycast deve alterar somente chaves administradas pelo adapter."""
    path = tmp_path / "emu.cfg"
    path.write_text(
        "[config]\n"
        "rend.Resolution = 1080\n"
        "Custom.FutureOption = keep-me\n"
        "\n[network]\n"
        "server = example\n",
        encoding="utf-8",
    )
    config = FlycastConfig(path)
    config.update_named({"resolution": 1440, "vsync": True})
    text = path.read_text(encoding="utf-8")
    assert "rend.Resolution = 1440" in text
    assert "rend.vsync = yes" in text
    assert "Custom.FutureOption = keep-me" in text
    assert "[network]" in text


def test_fbneo_exposes_only_four_rom_slots_without_touching_rest(tmp_path: Path) -> None:
    """A GUI deve alterar quatro slots e preservar os demais dezesseis."""
    path = tmp_path / "fbneo64.ini"
    lines = ["// preserved\n"]
    for index in range(20):
        lines.append(f"szAppRomPaths[{index}] old{index}\n")
    path.write_text("".join(lines), encoding="utf-8")
    config = FBNeoConfig(path)
    config.set_rom_paths(["one", "two", "three", "four"], limit=4)
    config.save(create_backup=False)
    saved = path.read_text(encoding="utf-8")
    assert "szAppRomPaths[0] one" in saved
    assert "szAppRomPaths[3] four" in saved
    assert "szAppRomPaths[4] old4" in saved
    assert "szAppRomPaths[19] old19" in saved


def test_supermodel_preserves_global_configuration(tmp_path: Path) -> None:
    """Supermodel deve atualizar somente as chaves globais solicitadas."""
    install = tmp_path / "Supermodel"
    config_dir = install / "Config"
    config_dir.mkdir(parents=True)
    ini = config_dir / "Supermodel.ini"
    ini.write_text(
        "[ Global ]\n"
        "RomsDirectory = old-roms\n"
        "UnknownOption = preserve\n"
        "\n[ Game ]\n"
        "Foo = Bar\n",
        encoding="utf-8",
    )
    config = SupermodelConfig(install)
    config.write_global_settings({"RomsDirectory": "new-roms", "VSync": 1})
    saved = ini.read_text(encoding="utf-8")
    assert "RomsDirectory = new-roms" in saved
    assert "VSync = 1" in saved
    assert "UnknownOption = preserve" in saved
    assert "[ Game ]" in saved


def test_retroarch_limits_writes_to_managed_keys(tmp_path: Path) -> None:
    """RetroArch não deve modificar chaves fora da lista administrada."""
    path = tmp_path / "retroarch.cfg"
    path.write_text(
        'video_driver = "gl"\n'
        'video_vsync = "true"\n'
        'custom_future_option = "keep"\n',
        encoding="utf-8",
    )
    config = RetroArchConfig(path)
    config.set_many({
        "video_driver": "vulkan",
        "video_vsync": False,
        "custom_future_option": "must-not-change",
    })
    config.save(create_backup=False)
    saved = path.read_text(encoding="utf-8")
    assert 'video_driver = "vulkan"' in saved
    assert "video_vsync = false" in saved
    assert 'custom_future_option = "keep"' in saved


def test_retroarch_round_trip_managed_values(tmp_path: Path) -> None:
    """Valores booleanos, numéricos e caminhos devem sobreviver ao round-trip."""
    path = tmp_path / "retroarch.cfg"
    config = RetroArchConfig(path)
    config.set_many({
        "video_vsync": True,
        "audio_out_rate": 48000,
        "video_shader_enable": True,
        "video_shader_dir": r"G:\RetroArch\shaders",
    })
    config.save(create_backup=False)

    reloaded = RetroArchConfig(path)
    assert reloaded.get("video_vsync") == "true"
    assert reloaded.get("audio_out_rate") == "48000"
    assert reloaded.get("video_shader_enable") == "true"
    assert reloaded.get("video_shader_dir") == r"G:\RetroArch\shaders"
