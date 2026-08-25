"""Testes dos perfis de otimização por sistema."""
from __future__ import annotations

from pathlib import Path

from app.config.app_config import AppConfig
from app.core.services.system_optimization_service import SystemOptimizationService


CATALOG_SOURCE = Path(__file__).resolve().parents[1] / "data" / "launchbox" / "system_optimizations.json"


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
    return SystemOptimizationService(project_root=project_root, config=config)


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
    """A aplicação preserva o existente e não cria a pasta config/config."""
    service = _service(tmp_path)
    config_root = service.config.emulator_paths["retroarch"]["config"]
    target = config_root / "Genesis Plus GX" / "Sega SG-1000.cfg"
    target.parent.mkdir(parents=True)
    target.write_text("old = \"value\"\n", encoding="utf-8")

    result = service.apply("Sega SG-1000", "sega sg-1000", "sega-sg1000-fidelity-v1")

    assert len(result["written"]) == 4
    assert len(result["backups"]) == 1
    assert target.is_file()
    assert not (config_root / "config" / "Genesis Plus GX").exists()
    assert target.read_text(encoding="utf-8").startswith("video_smooth")
    assert target.with_name(target.name + ".arcademanager.bak").read_text(encoding="utf-8") == 'old = "value"\n'


def test_new_profiles_write_under_retroarch_config_root(tmp_path: Path) -> None:
    """Os novos presets devem escrever somente dentro da árvore Config do RetroArch."""
    service = _service(tmp_path)
    config_root = service.config.emulator_paths["retroarch"]["config"]

    cases = [
        ("NES", "nes-fidelity-v1", "NES.cfg"),
        ("Super Nintendo Entertainment System", "snes-fidelity-v1", "Super Nintendo.cfg"),
        ("Master System", "master-system-fidelity-v1", "Sega Master System.cfg"),
        ("Mega Drive", "mega-drive-fidelity-v1", "Sega Mega Drive.cfg"),
        ("PlayStation", "playstation-fidelity-v1", "PlayStation.cfg"),
        ("Sega Saturn", "sega-saturn-fidelity-v1", "Sega Saturn.cfg"),
        ("Nintendo 64", "nintendo-64-fidelity-v1", "Nintendo 64.cfg"),
    ]

    for system_name, profile_id, filename in cases:
        result = service.apply(system_name, system_name.casefold(), profile_id)
        assert result["written"]
        assert all(config_root in path.parents for path in result["written"])
        assert (config_root / next(profile for profile in service.profiles.values() if profile.profile_id == profile_id).targets["override"]).name == filename
