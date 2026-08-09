import shutil
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..domain.manifest import FileRequirement, FileType
from ..archives.scanner import FullsetScanner

logger = logging.getLogger(__name__)

class FileCopier:
    def __init__(self, scanner: FullsetScanner):
        self.scanner = scanner

    def copy_files(self, requirements: List[FileRequirement],
                   source_root: Path, dest_root: Path,
                   progress_callback=None) -> Dict[str, Any]:
        stats = {"copied": 0, "missing": 0, "errors": 0, "missing_files": [], "error_files": []}

        (dest_root / "roms").mkdir(parents=True, exist_ok=True)
        (dest_root / "samples").mkdir(parents=True, exist_ok=True)
        (dest_root / "software").mkdir(parents=True, exist_ok=True)

        total = len(requirements)
        for idx, req in enumerate(requirements):
            if progress_callback:
                progress_callback(idx + 1, total, req.file_name)

            found = self.scanner.find_file(req.file_name)
            if not found and req.logical_name:
                found = self.scanner.find_file(req.logical_name)
            if not found and req.crc:
                found = self._find_by_crc(req.crc)

            if not found:
                stats["missing"] += 1
                stats["missing_files"].append(req.file_name)
                continue

            source_path = Path(found["path"])
            dest_subdir = self._get_dest_subdir(req.file_type)
            dest_path = dest_root / dest_subdir / found["name"]

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                shutil.copy2(source_path, dest_path)
                stats["copied"] += 1
            except Exception as e:
                logger.error(f"Erro ao copiar {source_path}: {e}")
                stats["errors"] += 1
                stats["error_files"].append(req.file_name)

        return stats

    def _find_by_crc(self, crc: str) -> Optional[Dict[str, Any]]:
        cursor = self.scanner.conn.execute("""
            SELECT a.path, a.format, am.name, am.size, am.crc, am.sha1
            FROM archive_member am
            JOIN archive a ON am.archive_id = a.id
            WHERE am.crc = ?
            LIMIT 1
        """, (crc,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def _get_dest_subdir(self, file_type: FileType) -> str:
        if file_type in (FileType.ROM, FileType.BIOS, FileType.DEVICE, FileType.CHD, FileType.DISK):
            return "roms"
        elif file_type == FileType.SAMPLE:
            return "samples"
        return "roms"