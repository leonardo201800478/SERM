"""Criação de arquivos da reconstrução usando o executável 7-Zip.

A reconstrução usa o mesmo 7-Zip detectado pelo EmulatorManager tanto para
ZIP quanto para 7Z. Isso mantém uma única implementação externa de compressão
e permite controlar formato e nível sem alterar o scanner.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .emulator_manager import EmulatorManager


class ReconstructionArchiveError(RuntimeError):
    """Erro controlado durante a criação do arquivo reconstruído."""


class ReconstructionArchiveService:
    """Empacota os arquivos selecionados pelo plano de reconstrução com 7-Zip."""

    FORMATS = {"zip": ".zip", "7z": ".7z"}
    LEVELS = {
        "store": 0,
        "fastest": 1,
        "fast": 3,
        "normal": 5,
        "maximum": 7,
        "ultra": 9,
    }

    @classmethod
    def seven_zip(cls) -> Path:
        executable = EmulatorManager.find_7zip()
        if executable is None:
            raise ReconstructionArchiveError(
                "7-Zip não encontrado. Instale o 7-Zip ou coloque 7z.exe no PATH."
            )
        return executable

    @classmethod
    def create(
        cls,
        files: list[str | Path],
        output: str | Path,
        *,
        format: str = "zip",
        level: str = "normal",
        base_dir: str | Path | None = None,
    ) -> Path:
        """Cria atomicamente um ZIP ou 7Z com 7-Zip.

        A lista de arquivos é passada por arquivo de lista para evitar o limite
        de comprimento de linha de comando do Windows em sets grandes.
        """
        archive_format = str(format).casefold().strip()
        compression_level = str(level).casefold().strip()
        if archive_format not in cls.FORMATS:
            raise ReconstructionArchiveError(f"Formato inválido: {format}")
        if compression_level not in cls.LEVELS:
            raise ReconstructionArchiveError(f"Nível de compactação inválido: {level}")
        if not files:
            raise ReconstructionArchiveError("Nenhum arquivo foi selecionado para reconstrução.")

        executable = cls.seven_zip()
        destination = Path(output).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        base = Path(base_dir).expanduser().resolve() if base_dir else None
        normalized = [Path(item).expanduser().resolve() for item in files]
        missing = [path for path in normalized if not path.is_file()]
        if missing:
            raise ReconstructionArchiveError(
                f"Arquivo não encontrado para reconstrução: {missing[0]}"
            )

        # O arquivo temporário mantém a extensão do formato final para que o
        # próprio 7-Zip selecione o container correto sem ambiguidade.
        suffix = cls.FORMATS[archive_format]
        temp_path: Path | None = None
        list_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination.stem}-",
                suffix=suffix,
                dir=destination.parent,
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
            temp_path.unlink(missing_ok=True)

            with tempfile.NamedTemporaryFile(
                prefix="serm-rebuild-",
                suffix=".lst",
                dir=destination.parent,
                mode="w",
                encoding="utf-8",
                newline="\n",
                delete=False,
            ) as handle:
                list_path = Path(handle.name)
                for path in normalized:
                    arcname = path.relative_to(base) if base else Path(path.name)
                    handle.write(arcname.as_posix() + "\n")

            command = [
                str(executable),
                "a",
                "-y",
                f"-t{archive_format}",
                f"-mx={cls.LEVELS[compression_level]}",
                "-scsUTF-8",
                str(temp_path),
                f"@{list_path}",
            ]
            result = subprocess.run(
                command,
                cwd=str(base) if base else None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if result.returncode != 0:
                raise ReconstructionArchiveError(
                    result.stderr.strip()
                    or result.stdout.strip()
                    or f"7-Zip falhou ao criar {destination.name}"
                )

            temp_path.replace(destination)
            return destination
        finally:
            if list_path is not None:
                list_path.unlink(missing_ok=True)
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)


__all__ = ["ReconstructionArchiveError", "ReconstructionArchiveService"]
