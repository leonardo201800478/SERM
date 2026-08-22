"""Descoberta e preparação das configurações dos emuladores suportados."""
from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from app.core.services.emulator_config_service import (
    EmulatorConfigService, EmulatorConfigSpec, EnsureResult,
    validate_fbneo_dat, validate_fbneo_ini, validate_flycast_cfg,
    validate_mame_ini, validate_supermodel_ini,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EmulatorInstallation:
    """Representa uma instalação descoberta sem alterar o sistema."""
    emulator: str
    executable: Path | None
    root: Path | None
    version: str | None
    configs: tuple[EnsureResult, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EmulatorDiscoveryOptions:
    """Caminhos explícitos usados para tornar a descoberta determinística."""
    mame_executable: Path | None = None
    flycast_executable: Path | None = None
    supermodel_executable: Path | None = None
    fbneo_executable: Path | None = None
    mame_root: Path | None = None
    flycast_root: Path | None = None
    supermodel_root: Path | None = None
    fbneo_root: Path | None = None


class EmulatorDiscoveryService:
    """Descobre os quatro emuladores sem abrir janelas."""
    SUPPORTED = ("mame", "flycast", "supermodel", "fbneo")

    def __init__(self, config_service: EmulatorConfigService | None = None):
        self.config_service = config_service or EmulatorConfigService()

    def discover_all(self, options: EmulatorDiscoveryOptions | None = None) -> dict[str, EmulatorInstallation]:
        """Executa a descoberta dos quatro emuladores independentemente."""
        opts = options or EmulatorDiscoveryOptions()
        result: dict[str, EmulatorInstallation] = {}
        for name, detector in (("mame", self.discover_mame), ("flycast", self.discover_flycast), ("supermodel", self.discover_supermodel), ("fbneo", self.discover_fbneo)):
            try:
                result[name] = detector(opts)
                logger.info("Emulator discovery: %s | executable=%s | root=%s | version=%s", name, result[name].executable, result[name].root, result[name].version)
            except Exception:
                logger.exception("Emulator discovery: falha isolada | emulator=%s", name)
                result[name] = EmulatorInstallation(name, None, None, None, metadata={"discovery_error": "exception"})
        return result

    def discover_mame(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre MAME e prepara mame.ini somente quando necessário."""
        executable = self._normalize_executable(options.mame_executable, ("mame.exe", "mame"))
        root = self._root(executable, options.mame_root)
        configs: list[EnsureResult] = []
        if root:
            path = root / "mame.ini"
            generator = (str(executable), "-createconfig") if executable else None
            configs.append(self._ensure_config("mame", "mame.ini", path, validate_mame_ini, generator_command=generator, cwd=root))
        return EmulatorInstallation("mame", executable, root, self._probe_version(executable, "mame"), tuple(configs))

    def discover_flycast(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre Flycast sem executar o emulador para obter versão."""
        executable = self._normalize_executable(options.flycast_executable, ("flycast.exe", "flycast"))
        root = self._root(executable, options.flycast_root)
        configs: list[EnsureResult] = []
        if root:
            configs.append(self._ensure_config("flycast", "emu.cfg", root / "emu.cfg", validate_flycast_cfg))
        return EmulatorInstallation("flycast", executable, root, self._probe_version(executable, "flycast"), tuple(configs))

    def discover_supermodel(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre Supermodel sem executar o emulador para obter versão."""
        executable = self._normalize_executable(options.supermodel_executable, ("Supermodel.exe", "supermodel.exe", "supermodel"))
        root = self._root(executable, options.supermodel_root)
        configs: list[EnsureResult] = []
        if root:
            configs.append(self._ensure_config("supermodel", "Supermodel.ini", root / "Supermodel.ini", validate_supermodel_ini))
        return EmulatorInstallation("supermodel", executable, root, self._probe_version(executable, "supermodel"), tuple(configs))

    def discover_fbneo(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre FBNeo sem usar switches de versão não documentados."""
        executable = self._normalize_executable(options.fbneo_executable, ("fbneo.exe", "FBNeo.exe", "fba64.exe", "fba.exe", "fbneo"))
        root = self._root(executable, options.fbneo_root)
        configs: list[EnsureResult] = []
        if root:
            configs.append(self._ensure_config("fbneo", "fbneo.ini", root / "config" / "fbneo.ini", validate_fbneo_ini))
            configs.append(self._ensure_config("fbneo", "arcade.dat", root / "dats" / "arcade.dat", validate_fbneo_dat))
        return EmulatorInstallation("fbneo", executable, root, self._probe_version(executable, "fbneo"), tuple(configs))

    def _ensure_config(self, emulator: str, name: str, path: Path, validator, *, generator_command: tuple[str, ...] | None = None, cwd: Path | None = None) -> EnsureResult:
        """Valida ou delega a geração de configuração explicitamente autorizada."""
        spec = EmulatorConfigSpec(emulator=emulator, name=name, path=path, generator_command=generator_command, cwd=cwd or path.parent, validator=validator)
        try:
            return self.config_service.ensure(spec)
        except (OSError, RuntimeError) as exc:
            logger.warning("[%s] falha ao preparar %s: %s", emulator, path, exc)
            return EnsureResult(emulator, name, path, "error", stderr=str(exc))

    @staticmethod
    def _root(executable: Path | None, configured: Path | None) -> Path | None:
        """Resolve a raiz preferindo o caminho explicitamente configurado."""
        if configured:
            return configured.expanduser().resolve()
        return executable.parent if executable else None

    @staticmethod
    def _normalize_executable(path: Path | None, filenames: tuple[str, ...]) -> Path | None:
        """Aceita executável ou diretório e procura nomes Windows conhecidos."""
        if path is None:
            return None
        try:
            candidate = path.expanduser().resolve()
            if candidate.is_file():
                return candidate
            if candidate.is_dir():
                for filename in filenames:
                    nested = candidate / filename
                    if nested.is_file():
                        return nested
        except OSError:
            logger.exception("Emulator discovery: caminho inválido | path=%s", path)
        return None

    @staticmethod
    def _probe_version(executable: Path | None, emulator: str) -> str | None:
        """Obtém versão somente por métodos documentados/seguros."""
        if executable is None or not executable.is_file():
            logger.info("Emulator discovery: executável não encontrado | emulator=%s", emulator)
            return None

        # Primeiro tenta metadados PE via PowerShell. Isso não inicia o emulador.
        if executable.suffix.lower() == ".exe":
            script = "$p=(Get-Item -LiteralPath $args[0] -ErrorAction Stop).VersionInfo;if($p.ProductVersion){$p.ProductVersion}else{$p.FileVersion}"
            try:
                result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script, str(executable)], capture_output=True, text=True, timeout=3, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
                value = (result.stdout or "").strip()
                match = re.search(r"([0-9]+(?:\.[0-9]+)+(?:[-+._][0-9A-Za-z.-]+)?)", value)
                if match:
                    logger.info("Emulator discovery: versão PE | emulator=%s | version=%s", emulator, match.group(1))
                    return match.group(1)
            except (OSError, subprocess.SubprocessError):
                logger.exception("Emulator discovery: falha lendo versão PE | emulator=%s", emulator)

        if emulator != "mame":
            logger.info("Emulator discovery: versão local não consultada por CLI | emulator=%s", emulator)
            return None

        try:
            result = subprocess.run([str(executable), "-version"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=5, check=False, cwd=str(executable.parent))
            text = (result.stdout or "").strip()
            logger.info("Emulator discovery: MAME -version returncode=%s output=%r", result.returncode, text[:256])
            match = re.search(r"\b([0-9]+\.[0-9]+)\b", text)
            return match.group(1) if match else None
        except (OSError, subprocess.SubprocessError):
            logger.exception("Emulator discovery: falha no probe MAME | executable=%s", executable)
            return None

    @classmethod
    def normalize(cls, installations: Iterable[EmulatorInstallation]) -> list[dict[str, object]]:
        """Converte instalações em estrutura estável para persistência."""
        rows=[]
        for item in installations:
            rows.append({"emulator":item.emulator,"executable":str(item.executable) if item.executable else None,"root":str(item.root) if item.root else None,"version":item.version,"configs":[{"name":cfg.name,"path":str(cfg.path),"status":cfg.status,"generated":cfg.generated,"backup":str(cfg.backup) if cfg.backup else None} for cfg in item.configs],"metadata":dict(item.metadata)})
        return rows
