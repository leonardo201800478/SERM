"""Testes da biblioteca de shaders e da política de desempenho."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.services.system_optimization_service import SystemOptimizationService


def config(root: Path) -> SimpleNamespace:
    """Cria configuração mínima isolada do RetroArch."""
    return SimpleNamespace(
        emulator_paths={"retroarch": {"config": root / "config", "shaders": root / "shaders"}},
        retroarch_native_paths={
            "video_shader_directory": root / "shaders",
            "overlay_directory": root / "overlays",
        },
        retroarch_dir=root,
        retroarch_core_config_dir=root / "config",
    )


def write_catalog(root: Path, payload: dict) -> None:
    """Grava um catálogo mínimo para o teste."""
    path = root / "data" / "launchbox"
    path.mkdir(parents=True)
    (path / "system_optimizations.json").write_text(json.dumps(payload), encoding="utf-8")


def write_shader_library(root: Path, shaders: list[dict]) -> None:
    """Grava uma biblioteca de shaders controlada pelo teste."""
    path = root / "data" / "launchbox"
    path.mkdir(parents=True, exist_ok=True)
    (path / "shader_library.json").write_text(json.dumps({"version": 1, "shaders": shaders}), encoding="utf-8")


def make_service(root: Path, shader: dict) -> SystemOptimizationService:
    """Cria serviço com um único shader cadastrado."""
    write_shader_library(root, [shader])
    write_catalog(
        root,
        {
            "version": 4,
            "profiles": [
                {
                    "id": "test",
                    "name": "Test",
                    "systems": ["Test System"],
                    "shader": shader["id"],
                    "cores": {
                        "Test Core": {
                            "preferred": True,
                            "targets": {"override": "Test Core/Test.cfg"},
                            "files": {"override": 'aspect_ratio_index = "21"'},
                        }
                    },
                }
            ],
        },
    )
    return SystemOptimizationService(root, config(root))


def test_clean_shader_is_available_as_safe_default(tmp_path: Path) -> None:
    """Shader CRT sem reflexo/overlay pode ser selecionado automaticamente."""
    shader = {
        "id": "clean-third-party",
        "name": "Clean Third Party CRT",
        "filename": "{system}.slangp",
        "reference": ":/shaders/third-party/clean.slangp",
        "source": "third-party",
        "source_url": "https://example.invalid/shader",
        "performance": "light",
        "reflection": False,
        "embedded_overlay": False,
        "recommended": True,
    }
    service = make_service(tmp_path, shader)
    options = service.shader_options_for_system("Test System")
    assert options[0].shader_id == "clean-third-party"
    profile = service.get("test")
    assert profile is not None
    assert profile.shader is not None
    assert profile.shader.filename == "Test System.slangp"
    assert profile.shader.reference == ":/shaders/third-party/clean.slangp"


def test_reflection_shader_is_not_safe_default(tmp_path: Path) -> None:
    """Shader com reflexão deve ficar fora da seleção automática."""
    shader = {
        "id": "heavy-reflection",
        "name": "Heavy Reflection",
        "filename": "{system}.slangp",
        "reference": ":/shaders/third-party/reflection.slangp",
        "source": "third-party",
        "source_url": "https://example.invalid/shader",
        "performance": "high",
        "reflection": True,
        "embedded_overlay": True,
        "recommended": False,
    }
    write_shader_library(tmp_path, [shader])
    write_catalog(tmp_path, {"version": 4, "profiles": []})
    service = SystemOptimizationService(tmp_path, config(tmp_path))
    assert service.shader_options_for_system("Test System") == []

    payload = {
        "version": 4,
        "profiles": [{
            "id": "heavy",
            "name": "Heavy",
            "systems": ["Test System"],
            "shader": "heavy-reflection",
            "cores": {"Test Core": {"targets": {"override": "Test Core/Test.cfg"}, "files": {"override": ""}}},
        }],
    }
    write_catalog(tmp_path, payload)
    with pytest.raises(ValueError, match="não é elegível como padrão"):
        SystemOptimizationService(tmp_path, config(tmp_path))


def test_shader_preset_is_simple_reference_only(tmp_path: Path) -> None:
    """O arquivo de sistema não deve duplicar uma cadeia completa de passes."""
    shader = {
        "id": "clean",
        "name": "Clean",
        "filename": "{system}.slangp",
        "reference": ":/shaders/base.slangp",
        "source": "third-party",
        "source_url": "https://example.invalid/shader",
        "performance": "light",
        "reflection": False,
        "embedded_overlay": False,
        "recommended": True,
    }
    service = make_service(tmp_path, shader)
    service.apply("Test System", "", "test")
    text = (tmp_path / "shaders" / "Test System.slangp").read_text(encoding="utf-8")
    assert text.count("#reference") == 1
    assert "shaders =" not in text
    assert "shader0 =" not in text
