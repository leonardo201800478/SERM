"""Descoberta segura e sem efeitos colaterais dos emuladores suportados."""
from __future__ import annotations

import logging
import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

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
    """Representa uma instalação descoberta."""
    emulator: str
    executable: Path | None
    root: Path | None
    version: str | None
    configs: tuple[EnsureResult, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EmulatorDiscoveryOptions:
    """Caminhos determinísticos dos emuladores."""
    mame_executable: Path | None = None
    flycast_executable: Path | None = None
    supermodel_executable: Path | None = None
    fbneo_executable: Path | None = None
    mame_root: Path | None = None
    flycast_root: Path | None = None
    supermodel_root: Path | None = None
    fbneo_root: Path | None = None
    generate_missing_mame_ini: bool = True


class EmulatorDiscoveryService:
    """Descobre os emuladores sem executar instaladores ou 7-Zip."""

    SUPPORTED = ("mame", "flycast", "supermodel", "fbneo")

    def __init__(self, config_service: EmulatorConfigService | None = None):
        self.config_service = config_service or EmulatorConfigService()

    def discover_all(self, options: EmulatorDiscoveryOptions | None = None) -> dict[str, EmulatorInstallation]:
        """Executa a descoberta dos quatro emuladores isoladamente."""
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
                result[name] = EmulatorInstallation(name, None, None, None, metadata={"discovery_error": "exception"})
        return result

    def discover_mame(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre o MAME pela pasta configurada e, se necessário, gera mame.ini uma única vez."""
        root = self._resolve_root(options.mame_root)
        executable: Path | None = None

        if root:
            candidate = root / "mame.exe"
            if candidate.is_file() and candidate.name.casefold() == "mame.exe":
                executable = candidate
            else:
                logger.warning("Emulator discovery: mame.exe não encontrado | root=%s", root)
        else:
            executable = self._normalize_executable(options.mame_executable, ("mame.exe",))
            root = self._root(executable, None)

        configs: list[EnsureResult] = []
        if root and executable:
            ini_path = root / "mame.ini"
            generator = None
            if options.generate_missing_mame_ini and not ini_path.exists():
                # Gera SOMENTE o mame.ini ausente, executando o mame.exe real
                # com cwd na pasta de instalação. O comando é validado como
                # executável antes da execução e nunca usa shell=True.
                generator = (str(executable), "-createconfig")
                logger.info("Emulator discovery: mame.ini ausente; geração controlada será executada | path=%s", ini_path)
            elif ini_path.exists():
                logger.info("Emulator discovery: mame.ini encontrado; preservando configuração existente | path=%s", ini_path)
            spec = EmulatorConfigSpec(
                emulator="mame",
                name="mame.ini",
                path=ini_path,
                generator_command=generator,
                cwd=root,
                validator=validate_mame_ini,
            )
            configs.append(self.config_service.ensure(spec))

        version = self._probe_mame_version(executable)
        return EmulatorInstallation(
            "mame",
            executable,
            root,
            version,
            tuple(configs),
            {"resolution": "configured_root" if options.mame_root else "legacy_executable"},
        )

    def discover_flycast(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre Flycast sem iniciar o executável."""
        executable = self._resolve_executable(options.flycast_executable, options.flycast_root, ("flycast.exe",))
        root = self._root(executable, options.flycast_root)
        configs: list[EnsureResult] = []
        if root:
            configs.append(self._ensure_config("flycast", "emu.cfg", root / "emu.cfg", validate_flycast_cfg))
        version = self._version_from_release_metadata(root, "flycast")
        return EmulatorInstallation("flycast", executable, root, version, tuple(configs))

    def discover_supermodel(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre Supermodel e identifica a versão a partir da configuração/local de release."""
        executable = self._resolve_executable(options.supermodel_executable, options.supermodel_root, ("Supermodel.exe", "supermodel.exe"))
        root = self._root(executable, options.supermodel_root)
        configs: list[EnsureResult] = []
        version = None
        if root:
            path = root / "Config" / "Supermodel.ini"
            configs.append(self._ensure_config("supermodel", "Supermodel.ini", path, validate_supermodel_ini))
            version = self._version_from_supermodel_tree(root, path)
        return EmulatorInstallation("supermodel", executable, root, version, tuple(configs))

    def discover_fbneo(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre FBNeo pelo executável e pelo config/fbneo64.ini."""
        executable = self._resolve_executable(
            options.fbneo_executable,
            options.fbneo_root,
            ("fbneo64.exe", "fbneo.exe", "FBNeo.exe", "fba64.exe", "fba.exe"),
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
        """Valida uma configuração sem gerar automaticamente, salvo o MAME explicitamente tratado."""
        spec = EmulatorConfigSpec(emulator=emulator, name=name, path=path, generator_command=None, cwd=path.parent, validator=validator)
        try:
            return self.config_service.ensure(spec)
        except (OSError, RuntimeError) as exc:
            logger.warning("[%s] falha ao validar %s: %s", emulator, path, exc)
            return EnsureResult(emulator, name, path, "error", stderr=str(exc))

    @staticmethod
    def _resolve_root(configured_root: Path | None) -> Path | None:
        """Normaliza a pasta configurada sem interpretar arquivos como executáveis."""
        if not configured_root:
            return None
        try:
            return configured_root.expanduser().resolve()
        except OSError:
            logger.exception("Emulator discovery: raiz inválida | root=%s", configured_root)
            return configured_root.expanduser()

    @classmethod
    def _resolve_executable(cls, configured_executable: Path | None, configured_root: Path | None, filenames: tuple[str, ...]) -> Path | None:
        """Resolve apenas executáveis cujo nome está na lista permitida."""
        if configured_executable:
            candidate = cls._normalize_executable(configured_executable, filenames)
            if candidate:
                return candidate
            logger.warning("Emulator discovery: caminho de executável inválido/obsoleto | path=%s | root=%s", configured_executable, configured_root)
        if configured_root:
            return cls._normalize_executable(configured_root, filenames)
        return None

    @staticmethod
    def _root(executable: Path | None, configured: Path | None) -> Path | None:
        """Retorna a raiz configurada ou a pasta do executável."""
        if configured:
            try:
                return configured.expanduser().resolve()
            except OSError:
                return configured.expanduser()
        return executable.parent if executable else None

    @staticmethod
    def _normalize_executable(path: Path | None, filenames: tuple[str, ...]) -> Path | None:
        """Aceita um executável conhecido ou uma pasta que contenha um deles."""
        if path is None:
            return None
        try:
            candidate = path.expanduser().resolve()
            allowed = {name.casefold() for name in filenames}
            if candidate.is_file():
                return candidate if candidate.suffix.casefold() == ".exe" and candidate.name.casefold() in allowed else None
            if candidate.is_dir():
                for filename in filenames:
                    nested = candidate / filename
                    if nested.is_file() and nested.name.casefold() in allowed and nested.suffix.casefold() == ".exe":
                        return nested
        except OSError:
            logger.exception("Emulator discovery: caminho inválido | path=%s", path)
        return None

    @staticmethod
    def _version_from_ini(path: Path, emulator: str) -> str | None:
        """Extrai versões de cabeçalhos textuais conhecidos."""
        if not path.is_file():
            return None
        try:
            text = path.read_text(encoding="utf-8-sig", errors="ignore")
        except OSError:
            return None
        if emulator == "fbneo":
            match = re.search(r"FinalBurn\s+Neo\s+v([0-9]+(?:\.[0-9]+)+)", text, re.IGNORECASE)
            return match.group(1) if match else None
        match = re.search(r"(?:supermodel|version|vers[aã]o)[^0-9]*([0-9]+(?:\.[0-9]+)+[a-z]?)", text, re.IGNORECASE)
        return match.group(1) if match else None

    @staticmethod
    def _version_from_supermodel_tree(root: Path, ini_path: Path) -> str | None:
        """Obtém a versão local do Supermodel por artefatos de build/release sem iniciar o emulador.

        A versão de release do Supermodel tem a forma `v0.3a-YYYYMMDD`; o sufixo
        `-git-<hash>` identifica o commit/build e não é tratado como parte da
        versão de produto. Se não houver arquivo local de release, retorna None.
        """
        candidates = (
            root / "version.txt",
            root / "VERSION",
            root / "version",
            root / "Config" / "version.txt",
        )
        pattern = re.compile(r"v?([0-9]+\.[0-9]+[a-z]-[0-9]{8})(?:-git-[0-9a-f]+)?", re.IGNORECASE)
        for candidate in candidates:
            if not candidate.is_file():
                continue
            try:
                text = candidate.read_text(encoding="utf-8-sig", errors="ignore")
            except OSError:
                continue
            match = pattern.search(text)
            if match:
                return match.group(1)
        # INI pode conter versão em pacotes/custom builds; não inventamos uma versão.
        return EmulatorDiscoveryService._version_from_ini(ini_path, "supermodel")

    @staticmethod
    def _version_from_release_metadata(root: Path | None, emulator: str) -> str | None:
        """Lê metadados locais eventualmente entregues pelo pacote do emulador."""
        if root is None:
            return None
        pattern = re.compile(r"v?([0-9]+\.[0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
        for name in ("VERSION", "version.txt", "VERSION.txt", "build.txt"):
            path = root / name
            if path.is_file():
                try:
                    match = pattern.search(path.read_text(encoding="utf-8-sig", errors="ignore"))
                    if match:
                        return match.group(1)
                except OSError:
                    pass
        return None

    @staticmethod
    def _probe_mame_version(executable: Path | None) -> str | None:
        """Obtém a versão somente do mame.exe instalado, nunca de pacotes baixados."""
        if executable is None or not executable.is_file() or executable.name.casefold() != "mame.exe":
            return None
        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = None
            if hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
            result = subprocess.run(
                [str(executable), "-noreadconfig", "-version"],
                cwd=str(executable.parent),
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
            )
            text = (result.stdout or "").strip()
            logger.info("Emulator discovery: MAME version | executable=%s | cwd=%s | returncode=%s | output=%r", executable, executable.parent, result.returncode, text[:512])
            match = re.search(r"\b(?:v)?([0-9]+\.[0-9]+)\b", text)
            return match.group(1) if match else None
        except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
            logger.exception("Emulator discovery: falha no probe MAME | executable=%s", executable)
            return None

    @classmethod
    def normalize(cls, installations: Iterable[EmulatorInstallation]) -> list[dict[str, object]]:
        """Converte instalações em estrutura estável para persistência."""
        return [
            {
                "emulator": item.emulator,
                "executable": str(item.executable) if item.executable else None,
                "root": str(item.root) if item.root else None,
                "version": item.version,
                "configs": [
                    {"name": cfg.name, "path": str(cfg.path), "status": cfg.status, "generated": cfg.generated, "backup": str(cfg.backup) if cfg.backup else None}
                    for cfg in item.configs
                ],
                "metadata": dict(item.metadata),
            }
            for item in installations
        ]
