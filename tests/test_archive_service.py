"""Testes da infraestrutura atual de arquivos compactados."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from app.core.services.archive import ArchiveError, ArchiveService


def test_detect_supported_formats(tmp_path: Path) -> None:
    """Reconhece somente ZIP, 7Z e RAR."""
    assert ArchiveService.detect_format(tmp_path / "rom.zip") == "zip"
    assert ArchiveService.detect_format(tmp_path / "rom.7z") == "7z"
    assert ArchiveService.detect_format(tmp_path / "rom.rar") == "rar"
    with pytest.raises(ArchiveError):
        ArchiveService.detect_format(tmp_path / "rom.tar")


def test_zip_create_list_extract_and_test(tmp_path: Path) -> None:
    """Criação, inspeção, integridade e extração ZIP funcionam sem ferramenta externa."""
    source = tmp_path / "source"
    source.mkdir()
    file_a = source / "game.bin"
    file_b = source / "sub" / "bios.bin"
    file_b.parent.mkdir()
    file_a.write_bytes(b"rom-data")
    file_b.write_bytes(b"bios-data")

    archive = tmp_path / "game.zip"
    ArchiveService.create_zip([file_a, file_b], archive, base_dir=source)

    assert ArchiveService.list(archive) == ["game.bin", "sub/bios.bin"]
    ArchiveService.test(archive)

    output = tmp_path / "extract"
    ArchiveService.extract(archive, output)
    assert (output / "game.bin").read_bytes() == b"rom-data"
    assert (output / "sub" / "bios.bin").read_bytes() == b"bios-data"


def test_zip_path_traversal_is_rejected(tmp_path: Path) -> None:
    """Extração nunca permite que um membro escreva fora do destino."""
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../../outside.bin", b"unsafe")

    with pytest.raises(ArchiveError, match="Caminho inseguro"):
        ArchiveService.extract(archive, tmp_path / "output")


def test_create_zip_is_atomic_on_missing_source(tmp_path: Path) -> None:
    """Falha de origem não deixa um ZIP parcial no destino final."""
    output = tmp_path / "final.zip"
    with pytest.raises(ArchiveError, match="Arquivo não encontrado"):
        ArchiveService.create_zip([tmp_path / "missing.bin"], output)
    assert not output.exists()


def test_external_formats_report_missing_backend(monkeypatch, tmp_path: Path) -> None:
    """7Z/RAR falham de forma explícita quando não há ferramenta externa."""
    monkeypatch.setattr("app.core.services.archive.archive_service.ArchiveDetector.seven_zip", lambda: None)
    monkeypatch.setattr("app.core.services.archive.archive_service.ArchiveDetector.winrar", lambda: None)

    with pytest.raises(ArchiveError, match="Nenhum extrator disponível"):
        ArchiveService.extract(tmp_path / "x.7z", tmp_path / "out")
    with pytest.raises(ArchiveError, match="Nenhum extrator disponível"):
        ArchiveService.extract(tmp_path / "x.rar", tmp_path / "out")
