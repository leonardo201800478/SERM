"""Detecção centralizada de ferramentas de arquivos compactados."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ArchiveTool:
    """Ferramenta externa detectada no sistema."""

    name: str
    executable: Path
    version: str | None = None


class ArchiveDetector:
    """Localiza backends externos sem alterar PATH ou instalar software."""

    @staticmethod
    def _which(names: tuple[str, ...]) -> Path | None:
        """Retorna o primeiro executável encontrado no PATH."""
        for name in names:
            found = shutil.which(name)
            if found:
                return Path(found)
        return None

    @classmethod
    def seven_zip(cls) -> ArchiveTool | None:
        """Detecta 7z/7za no PATH e nos diretórios convencionais do Windows."""
        found = cls._which(("7z.exe", "7z", "7za.exe", "7za"))
        if found:
            return ArchiveTool("7-Zip", found)

        roots = [
            os.environ.get("ProgramW6432"),
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        relative = ("7-Zip/7z.exe", "7-Zip/7za.exe", "7-Zip/Current/7z.exe")
        for root in roots:
            if not root:
                continue
            for item in relative:
                candidate = Path(root) / item
                if candidate.is_file():
                    return ArchiveTool("7-Zip", candidate)
        return None

    @classmethod
    def winrar(cls) -> ArchiveTool | None:
        """Detecta WinRAR/UnRAR no PATH e em instalações convencionais."""
        found = cls._which(("WinRAR.exe", "winrar.exe", "unrar.exe", "unrar"))
        if found:
            return ArchiveTool("WinRAR", found)

        roots = [
            os.environ.get("ProgramW6432"),
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        relative = ("WinRAR/WinRAR.exe", "WinRAR/unrar.exe")
        for root in roots:
            if not root:
                continue
            for item in relative:
                candidate = Path(root) / item
                if candidate.is_file():
                    return ArchiveTool("WinRAR", candidate)
        return None

    @classmethod
    def all(cls) -> dict[str, ArchiveTool | None]:
        """Retorna os recursos de arquivo compactado disponíveis."""
        return {"7z": cls.seven_zip(), "rar": cls.winrar()}
