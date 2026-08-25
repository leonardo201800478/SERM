"""Testes dos perfis de otimização por sistema."""
from __future__ import annotations

import json
from pathlib import Path

from app.config.app_config import AppConfig
from app.core.services.system_optimization_service import SystemOptimizationService


def test_sg1000_profile_is_catalogued(tmp_path: Path) -> None:
    """O perfil SG-1000 deve ser descoberto e associado ao sistema."""
    project_root = tmp_path
    catalog = project_root / "data" / "launchbox"
    catalog.mkdir(parents=True)
    catalog.write_text if False else None
    source = Path(__file__).resolve().parents[1] / "data" / "launchbox" / "system_optimizations.json"
    (catalog / "system_optimizations.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    config = AppConfig()
    config.retroarch_dir = tmp_path / "retroarch"
    config.emulator_paths["retroarch"]["config"] = config.retroarch_dir / "config"

    service = SystemOptimizationService(project_root=project_root, config=config)
    profiles = service.profiles_for_system("Sega SG-1000", "sega sg-1000")

    assert len(profiles) == 1
    assert profiles[0].profile_id == "sega-sg1000-fidelity-v1"
    assert profiles[0].core == "Genesis Plus GX"
    assert "options" in profiles[0].files
    assert "shader" in profiles[0].files


def test_sg1000_profile_applies_with_backup(tmp_path: Path) -> None:
    """A aplicação cria os quatro arquivos do perfil e preserva o existente."""
    project_root = tmp_path / "project"
    catalog = project_root / "data" / "launchbox"
    catalog.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1] / "data" / "launchbox" / "system_optimizations.json"
    (catalog / "system_optimizations.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    config = AppConfig()
    config.retroarch_dir = tmp_path / "retroarch"
    config.emulator_paths["retroarch"]["config"] = config.retroarch_dir / "config"
    target = config.retroarch_dir / "config" / "Genesis Plus GX" / "Sega SG-1000.cfg"
    target.parent.mkdir(parents=True)
    target.write_text("old = \"value\"\n", encoding="utf-8")

    service = SystemOptimizationService(project_root=project_root, config=config)
    result = service.apply("Sega SG-1000", "sega sg-1000", "sega-sg1000-fidelity-v1")

    assert len(result["written"]) == 4
    assert len(result["backups"]) == 1
    assert target.read_text(encoding="utf-8").startswith("video_smooth")
    assert target.with_name(target.name + ".arcademanager.bak").read_text(encoding="utf-8") == 'old = "value"\n'
