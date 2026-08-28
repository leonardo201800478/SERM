"""Testes do ciclo de vida local de shaders de terceiros."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.services.shader_manager_service import ShaderManagerService


def config(root: Path) -> SimpleNamespace:
    """Cria configuração mínima isolada do RetroArch."""
    return SimpleNamespace(
        emulator_paths={"retroarch": {"shaders": root / "shaders"}},
        retroarch_native_paths={"video_shader_directory": root / "shaders"},
        retroarch_dir=root,
    )


def catalog(root: Path) -> Path:
    """Cria catálogo mínimo com origem upstream."""
    path = root / "shader_library.json"
    path.write_text(json.dumps({"shaders": [{
        "id": "satpixie",
        "name": "CRT SatPixie",
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


def archive(version: str = "1") -> bytes:
    """Cria um ZIP de repositório GitHub para teste determinístico."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as package:
        package.writestr(
            "satpixie-crt-shader-main/RetroArch/shaders/shaders_slang/crt/satpixie-crt.slangp",
            f"#reference \"satpixie/main.slang\"\n; version={version}\n",
        )
        package.writestr("satpixie-crt-shader-main/RetroArch/shaders/shaders_slang/crt/satpixie/main.slang", f"shader-{version}")
    return stream.getvalue()


def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: str = "1") -> ShaderManagerService:
    """Cria o gerenciador com download upstream simulado."""
    manager = ShaderManagerService(config(tmp_path), catalog(tmp_path))
    monkeypatch.setattr(manager.downloader, "_download_archive", lambda spec: archive(version))
    return manager


def test_install_creates_manifest_and_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A instalação registra somente os arquivos realmente copiados."""
    manager = service(tmp_path, monkeypatch)
    status = manager.install("satpixie")
    assert status.installed
    assert status.file_count == 2
    assert manager._manifest_path().is_file()
    manifest = json.loads(manager._manifest_path().read_text(encoding="utf-8"))
    assert manifest["shaders"]["satpixie"]["repository"] == "https://github.com/Conkwer/satpixie-crt-shader"
    assert len(manifest["shaders"]["satpixie"]["files"]) == 2


def test_second_install_without_force_does_not_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Uma biblioteca íntegra não é baixada novamente sem force."""
    manager = service(tmp_path, monkeypatch)
    manager.install("satpixie")
    calls = 0

    def fail_download(spec):
        nonlocal calls
        calls += 1
        raise AssertionError("download inesperado")

    monkeypatch.setattr(manager.downloader, "_download_archive", fail_download)
    status = manager.install("satpixie")
    assert status.installed
    assert calls == 0


def test_update_replaces_content_and_fingerprint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Atualização força novo download e altera a impressão dos arquivos."""
    manager = service(tmp_path, monkeypatch, "1")
    first = manager.install("satpixie")
    monkeypatch.setattr(manager.downloader, "_download_archive", lambda spec: archive("2"))
    second = manager.update("satpixie")
    assert second.installed
    assert first.fingerprint != second.fingerprint
    assert "version=2" in (tmp_path / "shaders" / "shaders_slang" / "crt" / "satpixie-crt.slangp").read_text(encoding="utf-8")


def test_remove_only_deletes_tracked_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Desinstalação não remove arquivos que não pertencem ao manifesto."""
    manager = service(tmp_path, monkeypatch)
    manager.install("satpixie")
    external = tmp_path / "shaders" / "shaders_slang" / "crt" / "user.slang"
    external.parent.mkdir(parents=True, exist_ok=True)
    external.write_text("user", encoding="utf-8")
    manager.remove("satpixie")
    assert not (tmp_path / "shaders" / "shaders_slang" / "crt" / "satpixie-crt.slangp").exists()
    assert not (tmp_path / "shaders" / "shaders_slang" / "crt" / "satpixie" / "main.slang").exists()
    assert external.is_file()
    assert manager.list_installed() == []


def test_audit_detects_missing_tracked_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Auditoria identifica arquivos removidos manualmente."""
    manager = service(tmp_path, monkeypatch)
    manager.install("satpixie")
    tracked = tmp_path / "shaders" / "shaders_slang" / "crt" / "satpixie-crt.slangp"
    tracked.unlink()
    report = manager.audit("satpixie")
    assert report["installed"] is False
    assert report["missing"] == ["shaders_slang/crt/satpixie-crt.slangp"]


def test_unknown_shader_is_rejected(tmp_path: Path) -> None:
    """IDs fora do catálogo não podem ser instalados."""
    manager = ShaderManagerService(config(tmp_path), catalog(tmp_path))
    with pytest.raises(KeyError):
        manager.install("does-not-exist")
