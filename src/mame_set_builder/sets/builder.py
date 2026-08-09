import logging
import time
from pathlib import Path
from typing import List, Optional, Callable
import sqlite3

from ..dependencies.resolver import DependencyResolver
from ..domain.manifest import SetManifest
from ..archives.scanner import FullsetScanner
from .copier import FileCopier
from .validator import SetValidator

logger = logging.getLogger(__name__)

class SetBuilder:
    def __init__(self, db_conn: sqlite3.Connection, mame_executable: Optional[Path] = None):
        self.conn = db_conn
        self.resolver = DependencyResolver(db_conn)
        self.scanner = FullsetScanner(db_conn)
        self.copier = FileCopier(self.scanner)
        self.validator = SetValidator(mame_executable) if mame_executable else None

    def build(self, machine_names: List[str], source_path: Path, dest_path: Path,
              profile_name: str = "Custom",
              progress_callback: Optional[Callable] = None) -> SetManifest:
        if progress_callback:
            progress_callback("Resolvendo dependências...")

        manifest = self.resolver.resolve(machine_names, profile_name, str(source_path), str(dest_path))

        if progress_callback:
            progress_callback("Copiando arquivos...")

        stats = self.copier.copy_files(
            manifest.required_files,
            source_path,
            dest_path,
            progress_callback=lambda i, total, name: progress_callback(f"Copiando {name} ({i}/{total})")
        )

        manifest.missing_files = stats.get("missing_files", [])

        if self.validator:
            if progress_callback:
                progress_callback("Validando set...")
            validation = self.validator.verify(dest_path, machine_names)
            manifest.build_status = "complete"
        else:
            manifest.build_status = "complete"

        manifest.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        return manifest