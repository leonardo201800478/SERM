"""Descoberta e preparação das configurações dos emuladores suportados.

Este módulo separa descoberta de geração. Ele nunca sobrescreve uma
configuração válida; quando um arquivo está ausente/corrompido, delega a
regeneração ao :class:`EmulatorConfigService` somente se existir um gerador
explicitamente configurado.

A descoberta é deliberadamente conservadora: caminhos são obtidos de
instalações configuradas ou de locais convencionais, e a versão só é
considerada conhecida quando pode ser obtida de forma confiável.
"""
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
    validate_supermodel_ini,
    validate_xml,
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
    """Entradas opcionais para tornar a descoberta determinística."""

    mame_executable: Path | None = None
    flycast_executable: Path | None = None
    supermodel_executable: Path | None = None
    fbneo_executable: Path | None = None
    flycast_root: Path | None = None
    supermodel_root: Path | None = None
    fbneo_root: Path | None = None
    config_root: Path | None = None


class EmulatorDiscoveryService:
    """Descobre MAME, Flycast, Supermodel e FBNeo sem exibir janelas."""

    SUPPORTED = ("mame", "flycast", "supermodel", "fbneo")

    def __init__(self, config_service: EmulatorConfigService | None = None):
        self.config_service = config_service or EmulatorConfigService()

    def discover_all(self, options: EmulatorDiscoveryOptions | None = None) -> dict[str, EmulatorInstallation]:
        """Executa a descoberta dos quatro emuladores de forma independente."""
        opts = options or EmulatorDiscoveryOptions()
        return {
            "mame": self.discover_mame(opts),
            "flycast": self.discover_flycast(opts),
            "supermodel": self.discover_supermodel(opts),
            "fbneo": self.discover_fbneo(opts),
        }

    def discover_mame(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre MAME e valida somente o MAME.INI já existente."""
        executable = self._normalize_executable(options.mame_executable, "mame.exe")
        root = executable.parent if executable else None
        version = self._probe_version(executable)
        return EmulatorInstallation("mame", executable, root, version)

    def discover_flycast(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre Flycast e prepara `emu.cfg` apenas quando necessário."""
        executable = self._normalize_executable(options.flycast_executable, "flycast.exe")
        root = self._root(executable, options.flycast_root)
        configs: list[EnsureResult] = []
        if root:
            path = root / "emu.cfg"
            configs.append(self._ensure_config("flycast", "emu.cfg", path, validate_flycast_cfg))
        return EmulatorInstallation("flycast", executable, root, self._probe_version(executable), tuple(configs))

    def discover_supermodel(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre Supermodel e valida Supermodel.ini sem recriá-lo à força."""
        executable = self._normalize_executable(options.supermodel_executable, "Supermodel.exe")
        root = self._root(executable, options.supermodel_root)
        configs: list[EnsureResult] = []
        if root:
            path = root / "Supermodel.ini"
            configs.append(self._ensure_config("supermodel", "Supermodel.ini", path, validate_supermodel_ini))
        return EmulatorInstallation("supermodel", executable, root, self._probe_version(executable), tuple(configs))

    def discover_fbneo(self, options: EmulatorDiscoveryOptions) -> EmulatorInstallation:
        """Descobre FBNeo e valida INI/DAT existentes; não inventa DAT."""
        executable = self._normalize_executable(options.fbneo_executable, "fbneo.exe")
        root = self._root(executable, options.fbneo_root)
        configs: list[EnsureResult] = []
        if root:
            ini = root / "config" / "fbneo.ini"
            dat = root / "dats" / "arcade.dat"
            configs.append(self._ensure_config("fbneo", "fbneo.ini", ini, validate_fbneo_ini))
            configs.append(self._ensure_config("fbneo", "arcade.dat", dat, validate_fbneo_dat))
        return EmulatorInstallation("fbneo", executable, root, self._probe_version(executable), tuple(configs))

    def _ensure_config(self, emulator: str, name: str, path: Path, validator) -> EnsureResult:
        """Valida um arquivo e deixa a política de geração exclusivamente no serviço de configuração."""
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
            logger.warning("[%s] falha ao preparar %s: %s", emulator, path, exc)
            return EnsureResult(emulator, name, path, "error", stderr=str(exc))

    @staticmethod
    def _root(executable: Path | None, configured: Path | None) -> Path | None:
        """Resolve a raiz preferindo explicitamente a instalação configurada."""
        if configured:
            return configured.expanduser().resolve()
        return executable.parent if executable else None

    @staticmethod
    def _normalize_executable(path: Path | None, filename: str) -> Path | None:
        """Aceita somente executável explícito; não faz busca agressiva no disco."""
        if path is None:
            return None
        candidate = path.expanduser().resolve()
        if candidate.is_file():
            return candidate
        if candidate.is_dir():
            nested = candidate / filename
            return nested if nested.is_file() else None
        return None

    @staticmethod
    def _probe_version(executable: Path | None) -> str | None:
        """Obtém a versão silenciosamente quando o executável fornece --version."""
        if executable is None or not executable.is_file():
            return None
        try:
            result = subprocess.run(
                [str(executable), "--version"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=5,
                check=False,
            )
            text = (result.stdout or "").strip()
            if result.returncode != 0 and not text:
                return None
            match = re.search(r"\b(?:v(?:ersion)?\s*)?([0-9]+(?:\.[0-9]+){1,3})\b", text, re.I)
            return match.group(1) if match else (text[:128] if text else None)
        except (OSError, subprocess.SubprocessError):
            return None

    @classmethod
    def normalize(cls, installations: Iterable[EmulatorInstallation]) -> list[dict[str, object]]:
        """Converte resultados para uma estrutura estável para futura persistência."""
        rows: list[dict[str, object]] = []
        for item in installations:
            rows.append({
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
            })
        return rows
