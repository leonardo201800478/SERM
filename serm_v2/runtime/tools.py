"""Runtime discovery helpers for external applications used by SERM V2."""

from __future__ import annotations

import os
from pathlib import Path


def find_windows_executable(
    names: tuple[str, ...], extra_roots: tuple[Path, ...] = ()
) -> Path | None:
    """Find an executable on PATH or common Windows installation roots."""
    for name in names:
        candidate = _which(name)
        if candidate is not None:
            return candidate
    program_dirs = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        Path.home() / "AppData" / "Local",
    ]
    for root in (*extra_roots, *program_dirs):
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return candidate.resolve()
    return None


def _which(name: str) -> Path | None:
    """Resolve an executable using the Windows PATH without spawning a process."""
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        candidate = Path(directory) / name
        if candidate.is_file():
            return candidate.resolve()
    return None
