"""Gerenciamento seguro dos arquivos de configuração dos emuladores."""
from __future__ import annotations

import configparser
import logging
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

logger = logging.getLogger(__name__)
Validator = Callable[[Path], bool]


@dataclass(frozen=True, slots=True)
class EmulatorConfigSpec:
    """Descreve um arquivo que pode ser validado e, quando solicitado, gerado."""
    emulator: str
    name: str
    path: Path
    generator_command: tuple[str, ...] | None = None
    cwd: Path | None = None
    validator: Validator | None = None


@dataclass(frozen=True, slots=True)
class EnsureResult:
    """Resultado auditável da validação/geração de uma configuração."""
    emulator: str
    name: str
    path: Path
    status: str
    generated: bool = False
    backup: Path | None = None
    stdout: str = ""
    stderr: str = ""


class EmulatorConfigService:
    """Aplica a política de preservação das configurações existentes."""
    DEFAULT_TIMEOUT = 60

    def ensure(self, spec: EmulatorConfigSpec, *, timeout: int | None = None) -> EnsureResult:
        """Valida e, se um gerador foi explicitamente configurado, gera o arquivo."""
        path = spec.path.expanduser().resolve()
        if path.is_file() and self._is_valid(spec):
            logger.debug("[%s] %s válido; geração ignorada", spec.emulator, path)
            return EnsureResult(spec.emulator, spec.name, path, "valid")
        if path.exists() and not path.is_file():
            raise IsADirectoryError(f"O caminho de configuração não é arquivo: {path}")

        reason = "missing" if not path.exists() else "corrupt"
        backup = self._backup_invalid(path) if reason == "corrupt" else None
        if not spec.generator_command:
            logger.warning("[%s] %s %s e não possui gerador configurado", spec.emulator, path, reason)
            return EnsureResult(spec.emulator, spec.name, path, f"{reason}_no_generator", backup=backup)

        stdout, stderr = self._run_generator(spec.generator_command, cwd=spec.cwd or path.parent, timeout=timeout or self.DEFAULT_TIMEOUT)
        if not path.is_file() or not self._is_valid(spec):
            raise RuntimeError(f"O gerador de {spec.emulator}/{spec.name} não produziu uma configuração válida: {path}" + (f"\nSTDERR: {stderr.strip()}" if stderr.strip() else ""))
        return EnsureResult(spec.emulator, spec.name, path, f"generated_{reason}", generated=True, backup=backup, stdout=stdout, stderr=stderr)

    @staticmethod
    def _is_valid(spec: EmulatorConfigSpec) -> bool:
        """Valida usando o validador específico ou uma validação genérica."""
        try:
            if spec.validator is not None:
                return bool(spec.validator(spec.path))
            suffix = spec.path.suffix.lower()
            if suffix == ".xml":
                ET.parse(spec.path)
                return spec.path.stat().st_size > 0
            if suffix in {".ini", ".cfg"}:
                return EmulatorConfigService._validate_ini_like(spec.path)
            if suffix == ".dat":
                return EmulatorConfigService._validate_dat(spec.path)
            return spec.path.stat().st_size > 0
        except (OSError, UnicodeError, ET.ParseError, configparser.Error, ValueError):
            return False

    @staticmethod
    def _validate_ini_like(path: Path) -> bool:
        """Valida arquivos INI/Cfg sem exigir sintaxe de INI clássico."""
        raw = path.read_bytes()
        if not raw.strip():
            return False
        text = raw.decode("utf-8-sig", errors="ignore")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return False
        return any("=" in line or line.startswith("[") or len(line.split()) >= 2 for line in lines)

    @staticmethod
    def _validate_dat(path: Path) -> bool:
        """Validação mínima e segura para DAT textual do FBNeo."""
        raw = path.read_bytes()
        if not raw.strip():
            return False
        text = raw.decode("utf-8", errors="ignore").lower()
        return any(marker in text for marker in ("game", "rom", "setname", "datfile", "finalburn"))

    @staticmethod
    def _backup_invalid(path: Path) -> Path:
        """Preserva uma configuração inválida antes de uma regeneração explícita."""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup = path.with_name(f"{path.name}.corrupt.{stamp}.bak")
        shutil.copy2(path, backup)
        return backup

    @staticmethod
    def _run_generator(command: Sequence[str], *, cwd: Path, timeout: int) -> tuple[str, str]:
        """Executa um gerador sem shell e sem janela de console no Windows."""
        cwd.mkdir(parents=True, exist_ok=True)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = None
        if hasattr(subprocess, "STARTUPINFO"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
        result = subprocess.run(list(command), cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", shell=False, creationflags=creationflags, startupinfo=startupinfo, timeout=timeout, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"Comando de geração terminou com código {result.returncode}: {' '.join(command)}\nSTDERR: {result.stderr.strip()}")
        return result.stdout, result.stderr


def validate_mame_ini(path: Path) -> bool:
    """Valida o mame.ini existente através do parser do projeto."""
    try:
        from app.mame.ini_parser import MameIniParser
        parser = MameIniParser(path)
        parser.load()
        return parser.is_loaded() and parser.get_file_info() is not None
    except (OSError, UnicodeError, ValueError):
        return False


def validate_xml(path: Path) -> bool:
    """Valida XML completo."""
    try:
        ET.parse(path)
        return path.stat().st_size > 0
    except (OSError, ET.ParseError):
        return False


def validate_flycast_cfg(path: Path) -> bool:
    """Valida emu.cfg do Flycast."""
    return EmulatorConfigService._validate_ini_like(path)


def validate_supermodel_ini(path: Path) -> bool:
    """Valida Supermodel.ini."""
    return EmulatorConfigService._validate_ini_like(path)


def validate_fbneo_ini(path: Path) -> bool:
    """Valida fbneo64.ini."""
    return EmulatorConfigService._validate_ini_like(path)


def validate_fbneo_dat(path: Path) -> bool:
    """Valida arcade.dat do FBNeo."""
    return EmulatorConfigService._validate_dat(path)
