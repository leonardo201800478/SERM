"""Testes da arquitetura atual de atualização de cores do RetroArch."""
from __future__ import annotations

from pathlib import Path

from app.core.services.retroarch_download_service import (
    RetroArchCoreInfo,
    RetroArchDownloadService,
)


def _core(name: str, crc: str) -> RetroArchCoreInfo:
    """Cria metadado remoto mínimo para os testes."""
    return RetroArchCoreInfo(
        filename=f"{name}_libretro.dll.zip",
        date="20260829",
        crc32=crc,
    )


def test_compare_marks_only_crc_mismatch_as_update(tmp_path: Path) -> None:
    """Somente DLLs com CRC divergente devem precisar de atualização."""
    current_path = tmp_path / "current_libretro.dll"
    current_path.write_bytes(b"current")
    current = _core("current", f"{RetroArchDownloadService._crc32(current_path):08x}")

    outdated_path = tmp_path / "outdated_libretro.dll"
    outdated_path.write_bytes(b"outdated-local")
    outdated = _core("outdated", "deadbeef")

    unknown = tmp_path / "custom_libretro.dll"
    unknown.write_bytes(b"custom")

    result = RetroArchDownloadService.compare_installed_cores(
        [current, outdated],
        tmp_path,
    )

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
    old_path = tmp_path / "old_libretro.dll"
    old_path.write_bytes(b"old")
    custom_path = tmp_path / "custom_libretro.dll"
    custom_path.write_bytes(b"custom")

    ok = _core("ok", f"{RetroArchDownloadService._crc32(ok_path):08x}")
    old = _core("old", "00000000")

    matched = RetroArchDownloadService.match_installed_cores([ok, old], tmp_path)

    assert [item.core_name for item in matched] == ["old"]


def test_crc_calculation_is_deterministic(tmp_path: Path) -> None:
    """O CRC usado no contrato remoto deve ser estável para o mesmo binário."""
    path = tmp_path / "core_libretro.dll"
    path.write_bytes(b"retroarch-core-test")
    first = RetroArchDownloadService._crc32(path)
    second = RetroArchDownloadService._crc32(path)
    assert first == second
