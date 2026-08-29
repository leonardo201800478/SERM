"""Testes do resolvedor de dependências de shaders."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.core.services.shader_dependency_service import ShaderDependencyService
from app.core.services.shader_manager_service import ShaderStatus
from app.core.services.system_optimization_service import (
    ShaderOptimization,
    ShaderProfile,
)


def config(root: Path) -> SimpleNamespace:
    """Cria configuração mínima isolada do RetroArch."""
    return SimpleNamespace(
        emulator_paths={"retroarch": {"shaders": root / "shaders"}},
        retroarch_native_paths={"video_shader_directory": root / "shaders"},
        retroarch_dir=root,
    )


def catalog(root: Path) -> Path:
    """Cria catálogo mínimo com shader de terceiro."""
    path = root / "shader_library.json"
    path.write_text(
        '{"shaders": [{"id": "third", "name": "Third", '
        '"reference": ":/shaders/shaders_slang/crt/third.slangp", '
        '"filename": "third.slangp", "source": "vendor/third", '
        '"source_url": "https://github.com/vendor/third", '
        '"download": {"repository": "https://github.com/vendor/third", '
        '"ref": "main", "source_subdir": "", '
        '"destination_subdir": "shaders_slang/crt", '
        '"include": ["*.slang", "*.slangp"]}}]}',
        encoding="utf-8",
    )
    return path


def test_official_shader_does_not_require_download(tmp_path: Path) -> None:
    """Shaders oficiais não são tratados como dependências de terceiros."""
    service = ShaderDependencyService(config(tmp_path), catalog(tmp_path))
    shader = ShaderOptimization("system.slangp", ":/shaders/shaders_slang/crt/system.slangp", "official")
    profile = ShaderProfile(
        "official",
        "Official",
        "system.slangp",
        shader.reference,
        "libretro/slang-shaders",
        "https://github.com/libretro/slang-shaders",
    )
    dependency = service.inspect(shader, profile)
    assert dependency.third_party is False
    assert dependency.requires_download is False
    assert dependency.source_name == "libretro/slang-shaders"
    assert service.ensure_installed(dependency) is None


def test_third_party_shader_is_reported_as_missing(tmp_path: Path) -> None:
    """Shader de terceiro ausente exige download antes da aplicação."""
    service = ShaderDependencyService(config(tmp_path), catalog(tmp_path))
    shader = ShaderOptimization("third.slangp", ":/shaders/shaders_slang/crt/third.slangp", "third")
    profile = ShaderProfile(
        "third",
        "Third",
        "third.slangp",
        shader.reference,
        "vendor/third",
        "https://github.com/vendor/third",
    )
    dependency = service.inspect(shader, profile)
    assert dependency.third_party is True
    assert dependency.installed is False
    assert dependency.requires_download is True


def test_ensure_installed_does_not_download_already_installed_shader(tmp_path: Path, monkeypatch) -> None:
    """Uma dependência já instalada não dispara novo download."""
    service = ShaderDependencyService(config(tmp_path), catalog(tmp_path))
    shader = ShaderOptimization("third.slangp", ":/shaders/shaders_slang/crt/third.slangp", "third")
    profile = ShaderProfile(
        "third",
        "Third",
        "third.slangp",
        shader.reference,
        "vendor/third",
        "https://github.com/vendor/third",
    )
    installed = ShaderStatus("third", True, 1, "https://github.com/vendor/third", "main", "abc")
    dependency = service.inspect(shader, profile)
    dependency = dependency.__class__(
        shader=dependency.shader,
        profile=dependency.profile,
        third_party=True,
        installed=True,
        status=installed,
    )

    def fail_install(*args, **kwargs):
        raise AssertionError("download inesperado")

    monkeypatch.setattr(service.manager, "install", fail_install)
    assert service.ensure_installed(dependency) == installed
