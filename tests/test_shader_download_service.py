"""Testes do download seguro de shaders de terceiros."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.services.shader_download_service import ShaderDownloadService, ShaderDownloadSpec


def config(root: Path) -> SimpleNamespace:
    """Cria configuração mínima isolada do RetroArch."""
    return SimpleNamespace(
        emulator_paths={"retroarch": {"shaders": root / "shaders"}},
        retroarch_native_paths={"video_shader_directory": root / "shaders"},
        retroarch_dir=root,
    )


def catalog(root: Path) -> Path:
    """Cria catálogo mínimo para os testes."""
    path = root / "shader_library.json"
    path.write_text(json.dumps({"shaders": [{
        "id": "satpixie",
        "reference": ":/shaders/shaders_slang/crt/satpixie-crt.slangp",
        "download": {
            "repository": "https://github.com/Conkwer/satpixie-crt-shader",
            "ref": "main",
            "source_subdir": "RetroArch/shaders/shaders_slang/crt",
            "destination_subdir": "shaders_slang/crt",
            "include": ["*.slang", "*.slangp"],
        },
    }]}), encoding="utf-8")
    return path


def archive() -> bytes:
    """Cria ZIP semelhante ao archive de um repositório GitHub."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as package:
        package.writestr("satpixie-crt-shader-main/RetroArch/shaders/shaders_slang/crt/satpixie-crt.slangp", "#reference \"shaders/satpixie/main.slang\"\n")
        package.writestr("satpixie-crt-shader-main/RetroArch/shaders/shaders_slang/crt/shaders/satpixie/main.slang", "shader")
        package.writestr("satpixie-crt-shader-main/README.md", "documentation")
    return stream.getvalue()


def test_repository_must_be_github_https(tmp_path: Path) -> None:
    """Impede origens arbitrárias para downloads."""
    service = ShaderDownloadService(config(tmp_path), catalog(tmp_path))
    with pytest.raises(ValueError):
        service._validate_repository("https://example.com/foo/bar")


def test_install_filters_and_preserves_shader_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Somente arquivos selecionados são copiados para a árvore de shaders."""
    service = ShaderDownloadService(config(tmp_path), catalog(tmp_path))
    monkeypatch.setattr(service, "_download_archive", lambda spec: archive())
    result = service.install_from_catalog("satpixie")

    assert result.files_installed
    assert (tmp_path / "shaders" / "shaders_slang" / "crt" / "satpixie-crt.slangp").is_file()
    assert (tmp_path / "shaders" / "shaders_slang" / "crt" / "shaders" / "satpixie" / "main.slang").is_file()
    assert not (tmp_path / "shaders" / "README.md").exists()


def test_zip_path_traversal_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Um ZIP malicioso não pode escrever fora da pasta de shaders."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as package:
        package.writestr("repo-main/RetroArch/shaders/shaders_slang/crt/../../../../evil.slang", "bad")
    service = ShaderDownloadService(config(tmp_path), catalog(tmp_path))
    monkeypatch.setattr(service, "_download_archive", lambda spec: stream.getvalue())
    with pytest.raises(ValueError):
        service.install_from_catalog("satpixie")


def test_spec_accepts_only_safe_destination(tmp_path: Path) -> None:
    """O destino não pode escapar da raiz de shaders."""
    service = ShaderDownloadService(config(tmp_path), catalog(tmp_path))
    with pytest.raises(ValueError):
        service.install(ShaderDownloadSpec("x", "https://github.com/a/b", destination_subdir="../../outside"), progress=None)
