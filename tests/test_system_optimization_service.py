from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.core.services.system_optimization_service import (
    MANAGED_HEADER,
    SystemOptimizationService,
)


def make_config(root: Path) -> SimpleNamespace:
    """Cria uma configuração mínima e isolada para os testes."""
    config_dir = root / "config"
    shaders = root / "shaders"
    base = shaders / "shaders_slang" / "crt"
    base.mkdir(parents=True, exist_ok=True)
    (base / "crt-guest-advanced-ntsc.slangp").write_text("shaders = 0\n", encoding="utf-8")
    return SimpleNamespace(
        emulator_paths={"retroarch": {"config": config_dir, "shaders": shaders}},
        retroarch_native_paths={"video_shader_directory": shaders, "overlay_directory": root / "overlays"},
        retroarch_dir=root,
        retroarch_core_config_dir=config_dir,
    )


def write_catalog(root: Path, payload: dict) -> None:
    """Cria o catálogo temporário usado pelo serviço."""
    catalog = root / "data" / "launchbox" / "system_optimizations.json"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(json.dumps(payload), encoding="utf-8")


def build_service(tmp_path: Path, payload: dict) -> SystemOptimizationService:
    """Instancia o serviço apontando para um catálogo temporário."""
    write_catalog(tmp_path, payload)
    return SystemOptimizationService(project_root=tmp_path, config=make_config(tmp_path))


def profile_payload() -> dict:
    """Retorna um perfil multi-core usado nas regressões."""
    return {
        "version": 3,
        "profiles": [{
            "id": "nes-fidelity-v2",
            "name": "NES — Fidelity CRT v2",
            "systems": ["Nintendo Entertainment System", "nes"],
            "overlay_asset": "Nintendo-Entertainment-System-Bezel-16x9-2560x1440.cfg",
            "cores": {
                "Nestopia": {
                    "targets": {"override": "Nestopia/NES.cfg", "options": "Nestopia/NES.opt"},
                    "files": {
                        "override": 'aspect_ratio_index = "21"\nvideo_shader = ":/config/Nestopia/NES.slangp"',
                        "options": 'nestopia_palette = "cxa2025as"',
                    },
                },
                "Mesen": {
                    "targets": {"override": "Mesen/NES.cfg", "options": "Mesen/NES.opt"},
                    "files": {"override": 'aspect_ratio_index = "1"', "options": 'mesen_region = "auto"'},
                },
            },
            "shader": {"filename": "NES.slangp", "content": "INVALID OLD CONTENT"},
        }],
    }


def test_parse_new_schema_supports_multiple_cores(tmp_path: Path) -> None:
    """O perfil normalizado deve conter todos os cores declarados."""
    service = build_service(tmp_path, profile_payload())
    profile = service.get("nes-fidelity-v2")
    assert profile is not None
    assert profile.cores == ("Nestopia", "Mesen")
    assert profile.shader is not None
    assert profile.shader.filename == "NES.slangp"


def test_apply_creates_one_override_per_core_and_one_global_shader(tmp_path: Path) -> None:
    """Aplicar o perfil gera um arquivo por core e um shader global."""
    service = build_service(tmp_path, profile_payload())
    result = service.apply("Nintendo Entertainment System", "nes", "nes-fidelity-v2")
    config = tmp_path / "config"
    assert (config / "Nestopia" / "NES.cfg").is_file()
    assert (config / "Nestopia" / "NES.opt").is_file()
    assert (config / "Mesen" / "NES.cfg").is_file()
    assert (config / "Mesen" / "NES.opt").is_file()
    assert (tmp_path / "shaders" / "NES.slangp").is_file()
    assert len(result["written"]) == 5


def test_bezel_16x9_does_not_force_system_viewport(tmp_path: Path) -> None:
    """O overlay 16:9 nunca pode definir aspect_ratio_index do sistema."""
    service = build_service(tmp_path, profile_payload())
    overlay = tmp_path / "overlays" / "2k Systems" / "Nintendo-Entertainment-System-Bezel-16x9-2560x1440.cfg"
    overlay.parent.mkdir(parents=True)
    overlay.write_text("overlay", encoding="utf-8")
    service.apply("Nintendo Entertainment System", "nes", "nes-fidelity-v2")
    cfg = (tmp_path / "config" / "Nestopia" / "NES.cfg").read_text(encoding="utf-8")
    assert "aspect_ratio_index" not in cfg
    assert 'input_overlay = ":/overlays/2k Systems/Nintendo-Entertainment-System-Bezel-16x9-2560x1440.cfg"' in cfg


def test_shader_is_valid_simple_preset_and_not_core_local(tmp_path: Path) -> None:
    """O shader gerado deve ser um Simple Preset válido na pasta global."""
    service = build_service(tmp_path, profile_payload())
    service.apply("Nintendo Entertainment System", "nes", "nes-fidelity-v2")
    shader = tmp_path / "shaders" / "NES.slangp"
    text = shader.read_text(encoding="utf-8")
    assert text.startswith(MANAGED_HEADER)
    assert '#reference ":/shaders/shaders_slang/crt/crt-guest-advanced-ntsc.slangp"' in text
    assert "INVALID OLD CONTENT" not in text
    assert "aspect_ratio_index" not in text
    assert not (tmp_path / "config" / "Nestopia" / "NES.slangp").exists()


def test_existing_files_are_always_overwritten(tmp_path: Path) -> None:
    """Aplicar o perfil substitui arquivo externo sem criar backup."""
    service = build_service(tmp_path, profile_payload())
    target = tmp_path / "config" / "Nestopia" / "NES.cfg"
    target.parent.mkdir(parents=True)
    target.write_text("USER CONFIGURATION\n", encoding="utf-8")
    service.apply("Nintendo Entertainment System", "nes", "nes-fidelity-v2", overwrite=False)
    text = target.read_text(encoding="utf-8")
    assert text.startswith(MANAGED_HEADER)
    assert "USER CONFIGURATION" not in text
    assert list(tmp_path.rglob("*.arcademanager.bak*")) == []


def test_remove_deletes_only_managed_files(tmp_path: Path) -> None:
    """A remoção apaga gerenciados e preserva arquivos externos."""
    service = build_service(tmp_path, profile_payload())
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


def test_legacy_catalog_is_readable(tmp_path: Path) -> None:
    """O catálogo v2 de um único core continua compatível."""
    payload = {
        "version": 2,
        "profiles": [{
            "id": "legacy-v1",
            "name": "Legacy",
            "systems": ["Legacy System"],
            "core": "Legacy Core",
            "targets": {"override": "Legacy Core/Legacy.cfg", "shader": "Legacy Core/Legacy.slangp"},
            "files": {"override": 'aspect_ratio_index = "1"', "shader": '#reference ":/shaders/base.slangp"'},
        }],
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
