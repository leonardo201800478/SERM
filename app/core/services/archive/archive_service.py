"""Operações seguras e unificadas de ZIP, 7Z e RAR."""
from __future__ import annotations

import subprocess
import tempfile
import zipfile
from pathlib import Path

from .archive_detector import ArchiveDetector


class ArchiveError(RuntimeError):
    """Erro controlado em uma operação de arquivo compactado."""


class ArchiveService:
    """Abstrai inspeção, extração e criação de arquivos compactados."""

    _SUPPORTED = {".zip", ".7z", ".rar"}

    @classmethod
    def detect_format(cls, archive: str | Path) -> str:
        """Retorna ``zip``, ``7z`` ou ``rar`` pela extensão."""
        suffix = Path(archive).suffix.casefold()
        if suffix not in cls._SUPPORTED:
            raise ArchiveError(f"Formato de arquivo não suportado: {suffix or '<sem extensão>'}")
        return suffix[1:]

    @staticmethod
    def _safe_member(destination: Path, member: str) -> Path:
        """Valida um caminho interno para impedir path traversal."""
        root = destination.resolve()
        target = (root / member).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ArchiveError(f"Caminho inseguro no arquivo compactado: {member}") from exc
        return target

    @classmethod
    def list(cls, archive: str | Path) -> list[str]:
        """Lista nomes internos sem extrair o arquivo."""
        path = Path(archive)
        fmt = cls.detect_format(path)
        if fmt == "zip":
            with zipfile.ZipFile(path) as handle:
                return handle.namelist()
        tool = ArchiveDetector.seven_zip() if fmt == "7z" else ArchiveDetector.winrar()
        if tool is None:
            raise ArchiveError(f"Nenhum extrator disponível para {fmt.upper()}.")
        command = [str(tool.executable), "l", "-slt", str(path)]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if result.returncode != 0:
            raise ArchiveError(result.stderr.strip() or f"Falha ao listar {path.name}")
        names: list[str] = []
        for line in result.stdout.splitlines():
            if line.startswith("Path = "):
                name = line[7:].strip()
                if name and name != path.name:
                    names.append(name)
        return names

    @classmethod
    def test(cls, archive: str | Path) -> None:
        """Testa a integridade do arquivo compactado."""
        path = Path(archive)
        fmt = cls.detect_format(path)
        if fmt == "zip":
            with zipfile.ZipFile(path) as handle:
                bad = handle.testzip()
                if bad:
                    raise ArchiveError(f"ZIP corrompido: {bad}")
            return
        tool = ArchiveDetector.seven_zip() if fmt == "7z" else ArchiveDetector.winrar()
        if tool is None:
            raise ArchiveError(f"Nenhum verificador disponível para {fmt.upper()}.")
        command = [str(tool.executable), "t", str(path)]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if result.returncode != 0:
            raise ArchiveError(result.stderr.strip() or f"Arquivo {path.name} inválido")

    @classmethod
    def extract(cls, archive: str | Path, destination: str | Path) -> Path:
        """Extrai ZIP, 7Z ou RAR com proteção contra traversal."""
        source = Path(archive).resolve()
        target = Path(destination).resolve()
        target.mkdir(parents=True, exist_ok=True)
        fmt = cls.detect_format(source)
        if fmt == "zip":
            with zipfile.ZipFile(source) as handle:
                for info in handle.infolist():
                    cls._safe_member(target, info.filename)
                handle.extractall(target)
            return target
        tool = ArchiveDetector.seven_zip() if fmt == "7z" else ArchiveDetector.winrar()
        if tool is None:
            raise ArchiveError(f"Nenhum extrator disponível para {fmt.upper()}.")
        command = [str(tool.executable), "x", "-y", f"-o{target}", str(source)]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if result.returncode != 0:
            raise ArchiveError(result.stderr.strip() or result.stdout.strip() or f"Falha ao extrair {source.name}")
        return target

    @classmethod
    def create_zip(cls, files: list[str | Path], output: str | Path, base_dir: str | Path | None = None, compression: int = zipfile.ZIP_DEFLATED) -> Path:
        """Cria atomicamente um ZIP a partir dos arquivos fornecidos."""
        destination = Path(output).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        base = Path(base_dir).resolve() if base_dir else None

        # O arquivo temporário precisa manter a extensão do formato que será
        # validado. Caso contrário, ``test()`` rejeita o ``.tmp`` antes de
        # conseguir verificar a integridade do ZIP.
        with tempfile.NamedTemporaryFile(prefix=f".{destination.stem}-", suffix=".zip", dir=destination.parent, delete=False) as temp:
            temp_path = Path(temp.name)
        try:
            with zipfile.ZipFile(temp_path, "w", compression=compression) as handle:
                for item in files:
                    source = Path(item).resolve()
                    if not source.is_file():
                        raise ArchiveError(f"Arquivo não encontrado para ZIP: {source}")
                    arcname = source.relative_to(base) if base else Path(source.name)
                    handle.write(source, arcname.as_posix())
            cls.test(temp_path)
            temp_path.replace(destination)
            return destination
        finally:
            temp_path.unlink(missing_ok=True)

    @classmethod
    def create_7z(cls, files: list[str | Path], output: str | Path, base_dir: str | Path | None = None) -> Path:
        """Cria um 7Z com 7-Zip externo; py7zr permanece como fallback futuro."""
        tool = ArchiveDetector.seven_zip()
        if tool is None:
            raise ArchiveError("7-Zip não encontrado para criação de 7Z.")
        destination = Path(output).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        base = Path(base_dir).resolve() if base_dir else None
        sources = [str(Path(item).resolve()) for item in files]
        command = [str(tool.executable), "a", "-y", str(destination)] + sources
        cwd = str(base) if base else None
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if result.returncode != 0:
            destination.unlink(missing_ok=True)
            raise ArchiveError(result.stderr.strip() or result.stdout.strip() or "Falha ao criar 7Z")
        cls.test(destination)
        return destination
