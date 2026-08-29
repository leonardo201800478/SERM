"""Testes da arquitetura atual de atualização de cores do RetroArch."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.core.services.retroarch_download_service import RetroArchCoreInfo, RetroArchDownloadService
from app.gui.widgets import retroarch_download_worker as worker_module


def _core(name: str, crc: str) -> RetroArchCoreInfo:
    """Cria metadado remoto mínimo para os testes."""
    return RetroArchCoreInfo(filename=f"{name}_libretro.dll.zip", date="20260829", crc32=crc)


def test_compare_marks_only_crc_mismatch_as_update(tmp_path: Path) -> None:
    """Somente DLLs com CRC divergente devem precisar de atualização."""
    current_path = tmp_path / "current_libretro.dll"
    current_path.write_bytes(b"current")
    current = _core("current", f"{RetroArchDownloadService._crc32(current_path):08x}")
    outdated_path = tmp_path / "outdated_libretro.dll"
    outdated_path.write_bytes(b"outdated-local")
    outdated = _core("outdated", "deadbeef")
    (tmp_path / "custom_libretro.dll").write_bytes(b"custom")

    result = RetroArchDownloadService.compare_installed_cores([current, outdated], tmp_path)
    by_name = {entry.core_name: entry for entry in result}
    assert by_name["current"].is_current
    assert not by_name["current"].needs_update
    assert by_name["outdated"].needs_update
    assert by_name["custom"].remote_crc32 is None
    assert not by_name["custom"].needs_update


def test_match_installed_cores_returns_only_outdated(tmp_path: Path) -> None:
    """A API de seleção para atualização não inclui cores atuais ou desconhecidos."""
    ok_path = tmp_path / "ok_libretro.dll"
    ok_path.write_bytes(b"ok")
    (tmp_path / "old_libretro.dll").write_bytes(b"old")
    (tmp_path / "custom_libretro.dll").write_bytes(b"custom")
    ok = _core("ok", f"{RetroArchDownloadService._crc32(ok_path):08x}")
    old = _core("old", "00000000")

    matched = RetroArchDownloadService.match_installed_cores([ok, old], tmp_path)
    assert [item.core_name for item in matched] == ["old_libretro.dll"]


def test_crc_calculation_is_deterministic(tmp_path: Path) -> None:
    """O CRC usado no contrato remoto deve ser estável para o mesmo binário."""
    path = tmp_path / "core_libretro.dll"
    path.write_bytes(b"retroarch-core-test")
    assert RetroArchDownloadService._crc32(path) == RetroArchDownloadService._crc32(path)


def test_worker_retries_failed_core_and_continues_queue(tmp_path: Path, monkeypatch) -> None:
    """Um core pode falhar três vezes sem impedir o próximo da fila."""
    cores = [_core("broken", "deadbeef"), _core("working", "cafebabe")]
    calls: list[str] = []
    attempts: dict[str, int] = {}

    class FakeService:
        def list_cores(self, _channel):
            return cores

        def download_core(self, _channel, core, _cores_dir, progress=None):
            calls.append(core.core_name)
            attempts[core.core_name] = attempts.get(core.core_name, 0) + 1
            if core.core_name == "broken":
                raise RuntimeError("falha simulada")
            return tmp_path / "working_libretro.dll"

    class FakeConfig:
        def load(self):
            pass

        def get_emulator_path(self, _emulator, _key):
            return None

    monkeypatch.setattr(worker_module, "AppConfig", FakeConfig)
    worker = worker_module.RetroArchDownloadWorker(
        operation="core", destination=tmp_path,
        core_filenames=[core.filename for core in cores],
    )
    worker._service = FakeService()
    worker._channel_override = SimpleNamespace(name="nightly", base_url="https://example.invalid/")
    worker.run()

    assert calls == ["broken"] * 3 + ["working"]
    assert attempts == {"broken": 3, "working": 1}


def test_worker_success_does_not_retry(tmp_path: Path, monkeypatch) -> None:
    """Um core instalado com sucesso deve ser processado uma única vez."""
    core = _core("working", "cafebabe")
    calls: list[str] = []

    class FakeService:
        def list_cores(self, _channel):
            return [core]

        def download_core(self, _channel, selected, _cores_dir, progress=None):
            calls.append(selected.core_name)
            return tmp_path / "working_libretro.dll"

    class FakeConfig:
        def load(self):
            pass

        def get_emulator_path(self, _emulator, _key):
            return None

    monkeypatch.setattr(worker_module, "AppConfig", FakeConfig)
    worker = worker_module.RetroArchDownloadWorker(
        operation="core", destination=tmp_path,
        core_filenames=[core.filename],
    )
    worker._service = FakeService()
    worker._channel_override = SimpleNamespace(name="nightly", base_url="https://example.invalid/")
    worker.run()

    assert calls == ["working"]
