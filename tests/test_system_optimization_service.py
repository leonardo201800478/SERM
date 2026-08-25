from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.services.system_optimization_service import (
    MANAGED_HEADER,
    SystemOptimizationService,
)


def make_config(root: Path) -> SimpleNamespace:
    """Cria uma configuração mínima e isolada para os testes."""
    config_dir = root / "config"
    shaders = root / "shaders"
    return SimpleNamespace(
        emulator_paths={
            "retroarch": {
                "config": config_dir,
                "shaders": shaders,
            }
        },
        retroarch_native_paths={
            "video_shader_directory": shaders,
            "overlay_directory": root / "overlays",
        },
        retroarch_dir=root,
        retroarch_core_config_dir=config_dir,
        retroarch_core_remap_dir=config_dir / "remaps",
    )


def write_catalog(root: Path, payload: dict) -> None:
    """Cria o catálogo temporário usado pelo serviço."""
    catalog = root / "data" / "launchbox" / "system_optimizations.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(json.dumps(payload), encoding="utf-8")


def build_service(tmp_path: Path, payload: dict) -> SystemOptimizationService:
    """Instancia o serviço apontando para um catálogo temporário."""
    write_catalog(tmp_path, payload)
    return SystemOptimizationService(project_root=tmp_path, config=make_config(tmp_path))


def multi_core_profile() -> dict:
    """Retorna um perfil novo com dois cores e um shader compartilhado."""
    return {
        "version": 3,
        "profiles": [
            {
                "id": "nes-fidelity-v2",
                "name": "NES — Fidelity CRT v2",
                "description": "Teste multi-core.",
                "systems": ["Nintendo Entertainment System", "nes"],
                "cores": {
                    "Nestopia": {
                        "targets": {
                            "override": "Nestopia/NES.cfg",
                            "options": "Nestopia/NES.opt",
                        },
                        "files": {
                            "override": 'aspect_ratio_index = "1"',
                            "options": 'nestopia_palette = "cxa2025as"',
                        },
                    },
                    "Mesen": {
                        "targets": {
                            "override": "Mesen/NES.cfg",
                            "options": "Mesen/NES.opt",
                        },
                        "files": {
                            "override": 'aspect_ratio_index = "1"',
                            "options": 'mesen_region = "auto"',
                        },
                    },
                },
                "shader": {
                    "filename": "NES.slangp",
                    "content": '#reference ":/shaders/shaders_slang/crt/crt-guest-advanced-ntsc.slangp"',
                },
            }
        ],
    }


def test_parse_new_schema_supports_multiple_cores(tmp_path: Path) -> None:
    """O perfil normalizado deve conter todos os cores declarados."""
    service = build_service(tmp_path, multi_core_profile())
    profile = service.get("nes-fidelity-v2")

    assert profile is not None
    assert profile.cores == ("Nestopia", "Mesen")
    assert set(profile.core_optimizations) == {"Nestopia", "Mesen"}
    assert profile.shader is not None
    assert profile.shader.filename == "NES.slangp"


def test_apply_creates_one_override_per_core_and_one_global_shader(tmp_path: Path) -> None:
    """Aplicar o perfil deve gerar arquivos independentes por core."""
    service = build_service(tmp_path, multi_core_profile())

    result = service.apply("Nintendo Entertainment System", "nes", "nes-fidelity-v2")

    config = tmp_path / "config"
    assert (config / "Nestopia" / "NES.cfg").is_file()
    assert (config / "Nestopia" / "NES.opt").is_file()
    assert (config / "Mesen" / "NES.cfg").is_file()
    assert (config / "Mesen" / "NES.opt").is_file()

    shader = tmp_path / "shaders" / "NES.slangp"
    assert shader.is_file()
    assert len(result["written"]) == 5
    assert shader.read_text(encoding="utf-8").startswith(MANAGED_HEADER)

    nestopia_cfg = (config / "Nestopia" / "NES.cfg").read_text(encoding="utf-8")
    mesen_cfg = (config / "Mesen" / "NES.cfg").read_text(encoding="utf-8")

    assert 'video_shader = ":/shaders/NES.slangp"' in nestopia_cfg
    assert 'video_shader = ":/shaders/NES.slangp"' in mesen_cfg
    assert 'video_shader = ":/config/' not in nestopia_cfg
    assert 'video_shader = ":/config/' not in mesen_cfg


def test_apply_does_not_create_backups(tmp_path: Path) -> None:
    """A aplicação nova nunca deve criar arquivos .bak."""
    service = build_service(tmp_path, multi_core_profile())
    service.apply("NES", "nes", "nes-fidelity-v2")

    assert list(tmp_path.rglob("*.arcademanager.bak*")) == []


def test_remove_deletes_only_managed_files(tmp_path: Path) -> None:
    """A remoção deve apagar arquivos gerenciados e preservar arquivos externos."""
    service = build_service(tmp_path, multi_core_profile())
    service.apply("NES", "nes", "nes-fidelity-v2")

    external = tmp_path / "config" / "Mesen" / "external.cfg"
    external.parent.mkdir(parents=True, exist_ok=True)
    external.write_text("user setting\n", encoding="utf-8")

    result = service.remove("NES", "nes", "nes-fidelity-v2")

    assert not (tmp_path / "config" / "Nestopia" / "NES.cfg").exists()
    assert not (tmp_path / "config" / "Nestopia" / "NES.opt").exists()
    assert not (tmp_path / "config" / "Mesen" / "NES.cfg").exists()
    assert not (tmp_path / "config" / "Mesen" / "NES.opt").exists()
    assert not (tmp_path / "shaders" / "NES.slangp").exists()
    assert external.is_file()
    assert result["backups"] == []


def test_apply_refuses_to_overwrite_external_file_without_explicit_permission(tmp_path: Path) -> None:
    """Arquivos externos não podem ser sobrescritos silenciosamente."""
    service = build_service(tmp_path, multi_core_profile())

    external = tmp_path / "config" / "Mesen" / "NES.cfg"
    external.parent.mkdir(parents=True, exist_ok=True)
    external.write_text("user configuration\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        service.apply("NES", "nes", "nes-fidelity-v2")

    assert external.read_text(encoding="utf-8") == "user configuration\n"


def test_apply_can_explicitly_overwrite_external_file(tmp_path: Path) -> None:
    """A opção overwrite permite uma substituição deliberada, sem backup."""
    service = build_service(tmp_path, multi_core_profile())

    external = tmp_path / "config" / "Mesen" / "NES.cfg"
    external.parent.mkdir(parents=True, exist_ok=True)
    external.write_text("user configuration\n", encoding="utf-8")

    service.apply("NES", "nes", "nes-fidelity-v2", overwrite=True)

    assert external.read_text(encoding="utf-8").startswith(MANAGED_HEADER)
    assert list(tmp_path.rglob("*.arcademanager.bak*")) == []


def test_legacy_catalog_is_still_readable(tmp_path: Path) -> None:
    """O catálogo atual de um único core continua compatível durante a migração."""
    payload = {
        "version": 2,
        "profiles": [
            {
                "id": "legacy-v1",
                "name": "Legacy",
                "systems": ["Legacy System"],
                "core": "Legacy Core",
                "targets": {
                    "override": "Legacy Core/Legacy.cfg",
                    "shader": "Legacy Core/Legacy.slangp",
                },
                "files": {
                    "override": 'aspect_ratio_index = "1"',
                    "shader": '#reference ":/shaders/base.slangp"',
                },
            }
        ],
    }

    service = build_service(tmp_path, payload)
    profile = service.get("legacy-v1")

    assert profile is not None
    assert profile.cores == ("Legacy Core",)
    assert profile.shader is not None
    assert profile.shader.filename == "Legacy.slangp"

    service.apply("Legacy System", "", "legacy-v1")

    assert (tmp_path / "shaders" / "Legacy.slangp").is_file()
    assert (tmp_path / "config" / "Legacy Core" / "Legacy.cfg").is_file()
    assert not (tmp_path / "config" / "Legacy Core" / "Legacy.slangp").exists()
