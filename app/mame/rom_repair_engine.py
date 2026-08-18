"""Reparo individual de uma ROM usando a mesma política da reconstrução."""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import zipfile
import zlib
from pathlib import Path

from app.mame.reconstruction_engine import ReconstructionMachine, ReconstructionRom

STREAM_CHUNK_SIZE = 1024 * 1024
MAX_RETRIES = 2


class SingleRomRepairEngine:
    """Repara uma única ROM sem revarrer ou modificar a origem."""

    def __init__(self, source_paths: list[str | Path], destination: str | Path, log_callback=None) -> None:
        self.source_paths = [Path(p).expanduser().resolve() for p in source_paths]
        self.destination = Path(destination).expanduser().resolve()
        self.log_callback = log_callback

    def _log(self, message: str) -> None:
        if self.log_callback:
            self.log_callback(message)

    def _allowed(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
        except OSError:
            return False
        return any(base == resolved or base in resolved.parents for base in self.source_paths)

    def _source(self, rom: ReconstructionRom) -> tuple[str, Path, str | None]:
        if not rom.source_archive:
            raise FileNotFoundError("O Scan não registrou a origem física desta ROM.")
        source = Path(rom.source_archive).expanduser()
        if not source.is_file() or not self._allowed(source):
            raise FileNotFoundError(f"Origem não encontrada ou fora das fontes configuradas: {source}")
        kind = (rom.source_kind or "zip").lower()
        if kind in {"file", "loose", "raw"}:
            return kind, source, None
        if kind in {"zip", "archive"} and rom.source_member:
            return kind, source, rom.source_member
        raise ValueError("Origem da ROM não possui tipo/membro utilizável.")

    def _stream(self, rom: ReconstructionRom, source: tuple[str, Path, str | None], staged: Path) -> None:
        kind, path, member = source
        archive = None
        handle = None
        crc = 0
        total = 0
        sha1 = hashlib.sha1()
        try:
            if kind in {"file", "loose", "raw"}:
                handle = path.open("rb")
            else:
                archive = zipfile.ZipFile(path, "r")
                info = archive.getinfo(member or "")
                if rom.expected_size > 0 and info.file_size != rom.expected_size:
                    raise ValueError("Tamanho da origem incompatível com o LISTXML.")
                if rom.expected_crc and f"{info.CRC & 0xFFFFFFFF:08x}" != rom.expected_crc:
                    raise ValueError("CRC da origem incompatível com o LISTXML.")
                handle = archive.open(info, "r")
            with staged.open("wb") as output:
                while True:
                    chunk = handle.read(STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    output.write(chunk)
                    crc = zlib.crc32(chunk, crc)
                    sha1.update(chunk)
                    total += len(chunk)
        finally:
            if handle:
                handle.close()
            if archive:
                archive.close()
        actual_crc = f"{crc & 0xFFFFFFFF:08x}"
        if rom.expected_size > 0 and total != rom.expected_size:
            raise ValueError(f"Transferência incompleta: {total}/{rom.expected_size} bytes.")
        if rom.expected_crc and actual_crc != rom.expected_crc:
            raise ValueError(f"CRC após transferência incorreto: {actual_crc}.")
        if rom.expected_sha1 and sha1.hexdigest().lower() != rom.expected_sha1.lower():
            raise ValueError("SHA-1 após transferência incorreto.")

    def repair(self, machine: ReconstructionMachine, rom: ReconstructionRom) -> Path:
        """Reconstrói o ZIP da machine contendo somente as ROMs já presentes no destino mais a ROM reparada.

        O método nunca copia o ZIP de origem. Quando o destino já possui um ZIP,
        apenas suas entradas são lidas em streaming e extras não esperados pela ROM
        selecionada não são preservados se não forem identificáveis pelo manifesto.
        """
        self.destination.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix="single_rom_", dir=str(self.destination)))
        staged_rom = staging / "selected.romtmp"
        temp_zip = staging / f".{machine.name}.zip.tmp"
        target = self.destination / f"{machine.name}.zip"
        try:
            source = self._source(rom)
            for attempt in range(1, MAX_RETRIES + 2):
                staged_rom.unlink(missing_ok=True)
                try:
                    self._log(f"[ROM] reparando {machine.name} -> {rom.rom_name} | tentativa={attempt}")
                    self._stream(rom, source, staged_rom)
                    break
                except Exception:
                    if attempt > MAX_RETRIES:
                        raise
                    self._log(f"[ROM] falha na tentativa {attempt}; repetindo {rom.rom_name}")

            # O reparo individual é transacional: preserva o ZIP existente apenas
            # como staging e substitui a entrada selecionada. O serviço completo
            # fará a limpeza definitiva de extras quando a machine for reconstruída.
            with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as output:
                if target.is_file():
                    with zipfile.ZipFile(target, "r") as existing:
                        for info in existing.infolist():
                            if info.is_dir() or info.filename == rom.rom_name:
                                continue
                            with existing.open(info, "r") as src, output.open(info.filename, "w") as dst:
                                shutil.copyfileobj(src, dst, length=STREAM_CHUNK_SIZE)
                with staged_rom.open("rb") as src, output.open(rom.rom_name, "w") as dst:
                    shutil.copyfileobj(src, dst, length=STREAM_CHUNK_SIZE)

            with zipfile.ZipFile(temp_zip, "r") as check:
                info = check.getinfo(rom.rom_name)
                if rom.expected_size > 0 and info.file_size != rom.expected_size:
                    raise ValueError("ROM publicada com tamanho incorreto.")
                if rom.expected_crc and f"{info.CRC & 0xFFFFFFFF:08x}" != rom.expected_crc:
                    raise ValueError("ROM publicada com CRC incorreto.")
                if check.testzip() is not None:
                    raise ValueError("ZIP temporário corrompido.")

            os.replace(temp_zip, target)
            self._log(f"[ROM] PUBLICADA: {target} <- {rom.rom_name}")
            return target
        finally:
            shutil.rmtree(staging, ignore_errors=True)
