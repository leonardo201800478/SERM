"""SERM adapter for Datoso source acquisition."""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


class DatosoError(RuntimeError):
    """Raised when Datoso is unavailable or cannot fetch a source."""


@dataclass(frozen=True, slots=True)
class DatosoDownload:
    """Describe a DAT acquired through Datoso."""

    system: str
    path: Path
    sha256: str
    source: str = "datoso:nointro"


class DatosoProvider:
    """Run the official Datoso CLI without coupling SERM to its internals."""

    SEED = "nointro"
    DEFAULT_ROOT = Path("~/.datoso/dats/nointro/dats")

    def __init__(self, *, root: Path | None = None) -> None:
        """Initialize the adapter with the Datoso temporary DAT directory."""
        self.root = Path(root).expanduser() if root else self.DEFAULT_ROOT.expanduser()

    def is_available(self) -> bool:
        """Return whether the Datoso Python module can be imported."""
        try:
            __import__("datoso")
            __import__("datoso_seed_nointro")
        except ImportError:
            return False
        return True

    def doctor(self) -> subprocess.CompletedProcess[str]:
        """Run Datoso's doctor command and return its completed process."""
        return self._run("doctor", self.SEED)

    def fetch(self, system: str, destination: Path) -> DatosoDownload:
        """Fetch one No-Intro DAT through Datoso and copy it into SERM data."""
        if not system.strip():
            raise ValueError("Sistema No-Intro não pode ser vazio.")
        if not self.is_available():
            raise DatosoError(
                "Datoso não está instalado. Execute: "
                "python -m pip install -e \".[sources]\""
            )

        before = self._candidate_files()
        logger.info("[DATOSO][NO-INTRO] fetch sistema=%s", system)
        completed = self._run(self.SEED, "--fetch", "--filter", system)
        logger.info(
            "[DATOSO][NO-INTRO] retorno=%d stdout=%s",
            completed.returncode,
            completed.stdout.strip() or "<vazio>",
        )
        if completed.returncode != 0:
            raise DatosoError(
                f"Datoso falhou ao baixar '{system}' (exit={completed.returncode})."
            )

        source = self._find_new_or_updated(before, system)
        if source is None:
            raise DatosoError(
                f"Datoso concluiu sem produzir um DAT identificável para '{system}'. "
                f"Diretório verificado: {self.root}"
            )

        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        logger.info(
            "[DATOSO][NO-INTRO] OK sistema=%s origem=%s destino=%s sha256=%s",
            system,
            source,
            destination,
            digest,
        )
        return DatosoDownload(system=system, path=destination, sha256=digest)

    def _run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        """Run Datoso using the active SERM Python interpreter."""
        command = [sys.executable, "-m", "datoso", *arguments]
        env = os.environ.copy()
        logger.info("[DATOSO][CMD] %s", " ".join(command))
        return subprocess.run(
            command,
            cwd=None,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def _candidate_files(self) -> dict[Path, int]:
        """Return DAT/XML files and their modification times from Datoso's No-Intro area."""
        if not self.root.is_dir():
            return {}
        return {
            path: path.stat().st_mtime_ns
            for path in self.root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".dat", ".xml"}
        }

    def _find_new_or_updated(self, before: dict[Path, int], system: str) -> Path | None:
        """Find a newly created or modified DAT whose name matches the requested system."""
        candidates = self._candidate_files()
        system_key = self._normalize(system)
        changed = [
            path
            for path, mtime in candidates.items()
            if path not in before or mtime > before[path]
        ]
        matching = [path for path in changed if system_key in self._normalize(path.stem)]
        if matching:
            return max(matching, key=lambda path: path.stat().st_mtime_ns)
        return None

    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize names for robust matching against Datoso filenames."""
        return " ".join(value.casefold().replace("_", " ").replace("-", " ").split())
