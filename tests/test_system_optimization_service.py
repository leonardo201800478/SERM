"""Testes dos perfis de otimização por sistema."""
from __future__ import annotations

from pathlib import Path

from app.config.app_config import AppConfig
from app.core.services.system_optimization_service import SystemOptimizationService


CATALOG_SOURCE = Path(__file__).resolve().parents[1] / "data" / "launchbox" / "system_optimizations.json"


OVERLAYS = {
    "Sega SG-1000": "Sega-SG-1000-Bezel-16x9-2560x1440.cfg",
    "NES": "Nintendo-Entertainment-System-Bezel-16x9-2560x1440.cfg",
    "Super Nintendo Entertainment System": "Super-Nintendo-Entertainment-System-Bezel-16x9-2560x1440.cfg",
    "Master System": "Sega-Master-System-Bezel-16x9-2560x1440.cfg",
    "Mega Drive": "Sega-Genesis-16bit-Bezel-16x9-2560x1440.cfg",
    "PlayStation": "Sony-Playstation-Bezel-16x9-2560x1440.cfg",
    "Sega Saturn": "Sega-Saturn-Bezel-16x9-2560x1440.cfg",
    "Nintendo 64": "Nintendo-64-Bezel-16x9-2560x1440.cfg",
}


def _service(tmp_path: Path) -> SystemOptimizationService:
    """Cria um serviço isolado apontando para um catálogo temporário."""
    project_root = tmp_path / "project"
    catalog = project_root / "data" / "launchbox"
    catalog.mkdir(parents=True)
    (catalog / "system_optimizations.json").write_text(
        CATALOG_SOURCE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    config = AppConfig()
    config.retroarch_dir = tmp_path / "retroarch"
    config.emulator_paths["retroarch"]["config"] = config.retroarch_dir / "config"
    config.retroarch_native_paths["overlay_directory"] = config.retroarch_dir / "overlays"
    return SystemOptimizationService(project_root=project_root, config=config)


def _create_overlay(config: AppConfig, filename: str) -> Path:
    """Cria um bezel fictício para validar a resolução automática do serviço."""
    path = Path(config.retroarch_native_paths["overlay_directory"]) / "2k Systems" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("overlay", encoding="utf-8")
    return path


def test_all_console_profiles_are_catalogued(tmp_path: Path) -> None:
    """Os oito perfis atuais devem ser carregados pelo catálogo."""
    service = _service(tmp_path)

    expected = {
        "sega-sg1000-fidelity-v1",
        "nes-fidelity-v1",
        "snes-fidelity-v1",
        "master-system-fidelity-v1",
        "mega-drive-fidelity-v1",
        "playstation-fidelity-v1",
        "sega-saturn-fidelity-v1",
        "nintendo-64-fidelity-v1",
    }

    assert set(service.profiles) == expected


def test_profiles_match_system_aliases(tmp_path: Path) -> None:
    """Os nomes usados pelo LaunchBox e pelos bancos RetroArch devem resolver os perfis."""
    service = _service(tmp_path)

    cases = {
        "Nintendo Entertainment System": "nes-fidelity-v1",
        "Super Nintendo Entertainment System": "snes-fidelity-v1",
        "Master System": "master-system-fidelity-v1",
        "Mega Drive": "mega-drive-fidelity-v1",
        "PlayStation": "playstation-fidelity-v1",
        "Sega Saturn": "sega-saturn-fidelity-v1",
        "Nintendo 64": "nintendo-64-fidelity-v1",
        "Sega SG-1000": "sega-sg1000-fidelity-v1",
    }

    for system_name, expected_id in cases.items():
        profiles = service.profiles_for_system(system_name, system_name.casefold())
        assert [profile.profile_id for profile in profiles] == [expected_id]


def test_sg1000_profile_applies_with_backup_and_correct_paths(tmp_path: Path) -> None:
    """A aplicação preserva o existente e instala shader/overlay no formato correto."""
    service = _service(tmp_path)
    config_root = service.config.emulator_paths["retroarch"]["config"]
    overlay = _create_overlay(service.config, OVERLAYS["Sega SG-1000"])
    target = config_root / "Genesis Plus GX" / "Sega SG-1000.cfg"
    target.parent.mkdir(parents=True)
    target.write_text("old = \"value\"\n", encoding="utf-8")

    result = service.apply("Sega SG-1000", "sega sg-1000", "sega-sg1000-fidelity-v1")

    assert len(result["written"]) == 4
    assert len(result["backups"]) == 1
    assert target.is_file()
    assert not (config_root / "config" / "Genesis Plus GX").exists()
    assert target.read_text(encoding="utf-8").startswith("video_smooth")
    assert 'video_shader = ":/config/Genesis Plus GX/Sega SG-1000.slangp"' in target.read_text(encoding="utf-8")
    assert 'input_overlay = ":/overlays/2k Systems/Sega-SG-1000-Bezel-16x9-2560x1440.cfg"' in target.read_text(encoding="utf-8")
    assert (config_root / "Genesis Plus GX" / "Sega SG-1000.slangp").is_file()
    assert overlay.is_file()
    assert target.with_name(target.name + ".arcademanager.bak").read_text(encoding="utf-8") == 'old = "value"\n'


def test_all_profiles_use_slang_and_resolve_bezels(tmp_path: Path) -> None:
    """Cada perfil instala um preset Slang e injeta o bezel correspondente."""
    service = _service(tmp_path)
    config_root = service.config.emulator_paths["retroarch"]["config"]

    cases = [
        ("NES", "nes-fidelity-v1", "NES.slangp", OVERLAYS["NES"]),
        ("Super Nintendo Entertainment System", "snes-fidelity-v1", "Super Nintendo.slangp", OVERLAYS["Super Nintendo Entertainment System"]),
        ("Master System", "master-system-fidelity-v1", "Sega Master System.slangp", OVERLAYS["Master System"]),
        ("Mega Drive", "mega-drive-fidelity-v1", "Sega Mega Drive.slangp", OVERLAYS["Mega Drive"]),
        ("PlayStation", "playstation-fidelity-v1", "PlayStation.slangp", OVERLAYS["PlayStation"]),
        ("Sega Saturn", "sega-saturn-fidelity-v1", "Sega Saturn.slangp", OVERLAYS["Sega Saturn"]),
        ("Nintendo 64", "nintendo-64-fidelity-v1", "Nintendo 64.slangp", OVERLAYS["Nintendo 64"]),
    ]

    for system_name, profile_id, shader_filename, overlay_filename in cases:
        _create_overlay(service.config, overlay_filename)
        result = service.apply(system_name, system_name.casefold(), profile_id)
        profile = service.get(profile_id)
        assert profile is not None
        assert result["written"]
        assert (config_root / profile.core / shader_filename).is_file()
        override = next(path for path in result["written"] if path.suffix == ".cfg")
        text = override.read_text(encoding="utf-8")
        assert 'video_shader_enable = "true"' in text
        assert 'video_shader = ":/config/' in text
        assert f'input_overlay = ":/overlays/2k Systems/{overlay_filename}"' in text
        assert "\\config\\" not in text
        assert "\\overlays\\" not in text


def test_missing_overlay_is_warning_not_failure(tmp_path: Path) -> None:
    """A ausência do bezel não impede a aplicação do restante do perfil."""
    service = _service(tmp_path)
    result = service.apply("Nintendo 64", "nintendo 64", "nintendo-64-fidelity-v1")

    assert result["written"]
    assert any("Bezel" in warning for warning in result["warnings"])
