from __future__ import annotations

import logging
import zipfile
import zlib
from collections.abc import Callable
from pathlib import Path

from app.mame.physical_rom_scanner import PhysicalRomScanner

logger = logging.getLogger(__name__)


def _scan_zip_resilient(self: PhysicalRomScanner, path: Path, expected: dict[tuple[str, int], list[dict]], scan_id: int, cancelled: Callable[[], bool] | None) -> dict:
    """Processa todos os membros; corrupção de um membro não aborta o ZIP."""
    result = self._empty_result()
    try:
        with zipfile.ZipFile(path, "r") as archive:
            for info in archive.infolist():
                self._check_cancelled(cancelled)
                if info.is_dir():
                    continue
                result["members"] += 1
                try:
                    with archive.open(info, "r") as stream:
                        size, crc, sha1 = self._hash_stream(stream, cancelled)
                except (OSError, EOFError, RuntimeError, zipfile.BadZipFile, zlib.error) as exc:
                    result["read_errors"] += 1
                    self._record(scan_id, None, path, info.filename, "zip", 0, "", "", "read_error", 0, f"{type(exc).__name__}: {exc}")
                    result["records"] += 1
                    logger.warning("Membro ZIP ilegível: %s!%s — %s", path, info.filename, exc)
                    continue
                result["bytes_read"] += size
                result["records"] += self._record_matches(scan_id, path, info.filename, "zip", size, crc, sha1, expected.get((crc, size), []), result)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        result["read_errors"] += 1
        self._record(scan_id, None, path, None, "zip", 0, "", "", "archive_error", 0, f"{type(exc).__name__}: {exc}")
        result["records"] += 1
        logger.warning("ZIP ilegível: %s — %s", path, exc)
    return result


PhysicalRomScanner._scan_zip = _scan_zip_resilient
