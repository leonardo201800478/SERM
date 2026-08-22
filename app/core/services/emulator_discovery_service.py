"""Descoberta segura e sem efeitos colaterais dos emuladores suportados."""
from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from app.core.services.emulator_config_service import (
    EmulatorConfigService,
    EmulatorConfigSpec,
    EnsureResult,
    validate_fbneo_dat,
    validate_fbneo_ini,
    validate_flycast_cfg,
    validate_mame_ini,
    validate_supermodel_ini,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EmulatorInstallation:
    """Representa uma instalação descoberta sem iniciar nem modificar o emulador."""

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
    """Descobre os emuladores sem executar instaladores, 7-Zip ou geradores de configuração."""

    SUPPORTED = ("mame", "flycast", "supermodel", "fbneo")

    def __init__(self, config_service: EmulatorConfigService | None = None):
        self.config_service = config_service or EmulatorConfigService()

    def discover_all(self, options: EmulatorDiscoveryOptions | None = None) -> dict[str, EmulatorInstallation]:
        """Executa a descoberta dos quatro emuladores independentemente."""
        opts = options or EmulatorDiscoveryOptions()
        result: dict[str, EmulatorInstallation] = {}
        for name, detector in (
            ("mame", self.discover_mame),
            ("flycast", self.discover_flycast),
            ("supermodel", self.discover_supermodel),
            ("fbneo", self.discover_fbneo),
        ):
            try:
                result[name] = detector(opts)
                item = result[name]
                logger.info(
                    "Emulator discovery: %s | executable=%s | root=%s | version=%s",
                    name,
                    item.executable,
                    item.root,
                    item.version,
                )
            except Exception:
                logger.exception("Emulator discovery: falha isolada | emulator=%s", name)
                result[name] = EmulatorInstallation(
                    name,
                    None,
                    None,
                    None,
                    metadata={"discovery_error": "exception"},
                )
        return result

    def discover_mame(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre MAME, valida mame.ini na raiz e obtém a versão sem abrir janela."""
        executable = self._resolve_executable(
            options.mame_executable,
            options.mame_root,
            ("mame.exe", "mame"),
        )
        root = self._root(executable, options.mame_root)
        configs: list[EnsureResult] = []
        if root:
            # MAME cria o mame.ini por padrão na RAIZ da instalação,
            # ao lado de mame.exe. Não procurar em uma pasta INI.
            path = root / "mame.ini"
            configs.append(self._ensure_config("mame", "mame.ini", path, validate_mame_ini))
        version = self._probe_version(executable, "mame")
        return EmulatorInstallation("mame", executable, root, version, tuple(configs))

    def discover_flycast(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre Flycast sem executar o emulador."""
        executable = self._resolve_executable(
            options.flycast_executable,
            options.flycast_root,
            ("flycast.exe", "flycast"),
        )
        root = self._root(executable, options.flycast_root)
        configs: list[EnsureResult] = []
        if root:
            configs.append(self._ensure_config("flycast", "emu.cfg", root / "emu.cfg", validate_flycast_cfg))
        return EmulatorInstallation("flycast", executable, root, None, tuple(configs))

    def discover_supermodel(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre Supermodel e usa Config/Supermodel.ini para a configuração."""
        executable = self._resolve_executable(
            options.supermodel_executable,
            options.supermodel_root,
            ("Supermodel.exe", "supermodel.exe", "supermodel"),
        )
        root = self._root(executable, options.supermodel_root)
        configs: list[EnsureResult] = []
        version = None
        if root:
            path = root / "Config" / "Supermodel.ini"
            configs.append(self._ensure_config("supermodel", "Supermodel.ini", path, validate_supermodel_ini))
            version = self._version_from_ini(path, "supermodel")
        return EmulatorInstallation("supermodel", executable, root, version, tuple(configs))

    def discover_fbneo(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre FBNeo usando config/fbneo64.ini e lê a versão do cabeçalho."""
        executable = self._resolve_executable(
            options.fbneo_executable,
            options.fbneo_root,
            ("fbneo64.exe", "fbneo.exe", "FBNeo.exe", "fba64.exe", "fba.exe", "fbneo"),
        )
        root = self._root(executable, options.fbneo_root)
        configs: list[EnsureResult] = []
        version = None
        if root:
            ini_path = root / "config" / "fbneo64.ini"
            configs.append(self._ensure_config("fbneo", "fbneo64.ini", ini_path, validate_fbneo_ini))
            dat_path = root / "dats" / "arcade.dat"
            if dat_path.exists():
                configs.append(self._ensure_config("fbneo", "arcade.dat", dat_path, validate_fbneo_dat))
            version = self._version_from_ini(ini_path, "fbneo")
        return EmulatorInstallation("fbneo", executable, root, version, tuple(configs))

    def _ensure_config(self, emulator: str, name: str, path: Path, validator) -> EnsureResult:
        """Somente valida a configuração durante a descoberta; nunca a gera no startup."""
        spec = EmulatorConfigSpec(
            emulator=emulator,
            name=name,
            path=path,
            generator_command=None,
            cwd=path.parent,
            validator=validator,
        )
        try:
            return self.config_service.ensure(spec)
        except (OSError, RuntimeError) as exc:
            logger.warning("[%s] falha ao validar %s: %s", emulator, path, exc)
            return EnsureResult(emulator, name, path, "error", stderr=str(exc))

    @classmethod
    def _resolve_executable(
        cls,
        configured_executable: Path | None,
        configured_root: Path | None,
        filenames: tuple[str, ...],
    ) -> Path | None:
        """Resolve somente executáveis conhecidos.

        O campo ``*_path`` pode conter uma configuração antiga apontando para um
        pacote ``.7z``/``.zip``. A implementação anterior aceitava qualquer arquivo
        como se fosse executável; em seguida o probe de versão tentava executar o
        arquivo e o Windows abria a tela de descompactação. Agora um arquivo só é
        aceito quando seu nome corresponde a um executável suportado. Se o caminho
        antigo estiver inválido, a raiz configurada é usada como fallback.
        """
        if configured_executable:
            candidate = cls._normalize_executable(configured_executable, filenames)
            if candidate:
                return candidate
            logger.warning(
                "Emulator discovery: caminho de executável inválido/obsoleto; procurando na raiz | path=%s | root=%s",
                configured_executable,
                configured_root,
            )
        if configured_root:
            return cls._normalize_executable(configured_root, filenames)
        return None

    @staticmethod
    def _root(executable: Path | None, configured: Path | None) -> Path | None:
        """Resolve a raiz preferindo o caminho explicitamente configurado."""
        if configured:
            try:
                return configured.expanduser().resolve()
            except OSError:
                logger.exception("Emulator discovery: raiz inválida | root=%s", configured)
                return configured.expanduser()
        return executable.parent if executable else None

    @staticmethod
    def _normalize_executable(path: Path | None, filenames: tuple[str, ...]) -> Path | None:
        """Aceita executável ou diretório e rejeita arquivos que não sejam executáveis conhecidos."""
        if path is None:
            return None
        try:
            candidate = path.expanduser().resolve()
            if candidate.is_file():
                # Não basta existir: somente um nome explicitamente conhecido pode
                # ser usado como processo. Isso impede executar .7z/.zip por engano.
                allowed = {name.casefold() for name in filenames if Path(name).suffix.casefold() == ".exe"}
                if candidate.name.casefold() in allowed and candidate.suffix.casefold() == ".exe":
                    return candidate
                return None
            if candidate.is_dir():
                for filename in filenames:
                    nested = candidate / filename
                    if nested.is_file() and nested.suffix.casefold() == ".exe":
                        return nested
        except OSError:
            logger.exception("Emulator discovery: caminho inválido | path=%s", path)
        return None

    @staticmethod
    def _version_from_ini(path: Path, emulator: str) -> str | None:
        """Extrai versão de cabeçalhos textuais conhecidos sem executar o emulador."""
        if not path.is_file():
            return None
        try:
            text = path.read_text(encoding="utf-8-sig", errors="ignore")
        except OSError:
            logger.exception(
                "Emulator discovery: não foi possível ler INI | emulator=%s | path=%s",
                emulator,
                path,
            )
            return None

        if emulator == "fbneo":
            match = re.search(
                r"FinalBurn\s+Neo\s+v([0-9]+(?:\.[0-9]+)+)",
                text,
                re.IGNORECASE,
            )
            if match:
                return match.group(1)

        match = re.search(
            r"(?:supermodel|version|vers[aã]o)[^0-9]*([0-9]+(?:\.[0-9]+)+[a-z]?)",
            text,
            re.IGNORECASE,
        )
        return match.group(1) if match else None

    @staticmethod
    def _probe_version(executable: Path | None, emulator: str) -> str | None:
        """Obtém a versão do MAME por CLI sem permitir execução de arquivos arbitrários."""
        if executable is None or not executable.is_file() or executable.suffix.casefold() != ".exe" or emulator != "mame":
            return None
        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = None
            if hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0

            result = subprocess.run(
                [str(executable), "-version"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                creationflags=creationflags,
                startupinfo=startupinfo,
                timeout=5,
                check=False,
                cwd=str(executable.parent),
            )
            text = (result.stdout or "").strip()
            logger.info(
                "Emulator discovery: MAME -version | returncode=%s | output=%r",
                result.returncode,
                text[:512],
            )
            # MAME normalmente retorna algo como "MAME v0.289".
            match = re.search(r"\b(?:v)?([0-9]+\.[0-9]+)\b", text, re.IGNORECASE)
            return match.group(1) if match else None
        except subprocess.TimeoutExpired:
            logger.warning("Emulator discovery: MAME -version timeout | executable=%s", executable)
            return None
        except (OSError, subprocess.SubprocessError):
            logger.exception("Emulator discovery: falha no probe MAME | executable=%s", executable)
            return None

    @classmethod
    def normalize(cls, installations: Iterable[EmulatorInstallation]) -> list[dict[str, object]]:
        """Converte instalações em estrutura estável para persistência."""
        rows: list[dict[str, object]] = []
        for item in installations:
            rows.append(
                {
                    "emulator": item.emulator,
                    "executable": str(item.executable) if item.executable else None,
                    "root": str(item.root) if item.root else None,
                    "version": item.version,
                    "configs": [
                        {
                            "name": cfg.name,
                            "path": str(cfg.path),
                            "status": cfg.status,
                            "generated": cfg.generated,
                            "backup": str(cfg.backup) if cfg.backup else None,
                        }
                        for cfg in item.configs
                    ],
                    "metadata": dict(item.metadata),
                }
            )
        return rows
