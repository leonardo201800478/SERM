"""Registro único que conecta schema, capabilities e adapter nativo.

A GUI não deve conhecer o formato físico de cada emulador. O registro expõe
um contrato comum e mantém as implementações nativas existentes como detalhes
internos de cada adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .capabilities import EmulatorCapabilities, get_capabilities
from .config_backend import EmulatorConfigBackend
from .config_schema import Setting, get_schema
from .fbneo_config import FBNeoConfig
from .flycast_config import FlycastConfig
from .retroarch_config import RetroArchConfig
from .supermodel_config import SupermodelConfig


@dataclass(frozen=True, slots=True)
class EmulatorAdapterSpec:
    """Contrato consolidado de um emulador suportado."""

    emulator: str
    label: str
    executable: str
    config_filename: str
    config_relative_dir: str
    config_format: str
    capabilities: EmulatorCapabilities
    config_factory: Callable[[Path, Path], Any]

    def schema(self, domain: str | None = None) -> dict[str, tuple[Setting, ...]] | tuple[Setting, ...]:
        """Retorna o schema canônico inteiro ou um domínio específico."""
        schema = get_schema(self.emulator)
        if domain is None:
            return schema
        try:
            return schema[domain]
        except KeyError as exc:
            raise ValueError(f"Domínio não suportado: {self.emulator}/{domain}") from exc

    def config_path(self, install_dir: str | Path) -> Path:
        """Resolve a localização física do arquivo de configuração."""
        root = Path(install_dir).expanduser()
        if self.config_relative_dir:
            root = root / self.config_relative_dir
        return root / self.config_filename

    def create_config(self, install_dir: str | Path) -> Any:
        """Cria o adapter nativo associado à instalação informada."""
        root = Path(install_dir).expanduser()
        return self.config_factory(root, self.config_path(root))

    def backend(self, install_dir: str | Path, *, backup: bool = True) -> EmulatorConfigBackend:
        """Cria o backend genérico para formatos simples quando aplicável."""
        return EmulatorConfigBackend(self.emulator, self.config_path(install_dir), backup=backup)


def _mame_factory(root: Path, config: Path) -> EmulatorConfigBackend:
    """MAME usa o backend de arquivo enquanto o parser nativo permanece soberano."""
    return EmulatorConfigBackend("mame", config)


def _flycast_factory(root: Path, config: Path) -> FlycastConfig:
    """Cria o adapter nativo do Flycast."""
    return FlycastConfig(config)


def _supermodel_factory(root: Path, config: Path) -> SupermodelConfig:
    """Cria o adapter nativo do Supermodel a partir da raiz da instalação."""
    return SupermodelConfig(root)


def _fbneo_factory(root: Path, config: Path) -> FBNeoConfig:
    """Cria o adapter nativo do FBNeo."""
    return FBNeoConfig(config)


def _retroarch_factory(root: Path, config: Path) -> RetroArchConfig:
    """Cria o adapter nativo do RetroArch."""
    return RetroArchConfig(config)


ADAPTERS: dict[str, EmulatorAdapterSpec] = {
    "mame": EmulatorAdapterSpec("mame", "MAME", "mame.exe", "mame.ini", "", "mame-ini", get_capabilities("mame"), _mame_factory),
    "flycast": EmulatorAdapterSpec("flycast", "Flycast", "flycast.exe", "emu.cfg", "", "ini-sectioned", get_capabilities("flycast"), _flycast_factory),
    "supermodel": EmulatorAdapterSpec("supermodel", "Supermodel", "Supermodel.exe", "Supermodel.ini", "Config", "ini-sectioned", get_capabilities("supermodel"), _supermodel_factory),
    "fbneo": EmulatorAdapterSpec("fbneo", "FBNeo", "fbneo64.ini", "fbneo64.ini", "config", "key-value-space", get_capabilities("fbneo"), _fbneo_factory),
    "retroarch": EmulatorAdapterSpec("retroarch", "RetroArch", "retroarch.exe", "retroarch.cfg", "", "retroarch-cfg", get_capabilities("retroarch"), _retroarch_factory),
}


def get_adapter(emulator: str) -> EmulatorAdapterSpec:
    """Retorna o adapter consolidado de um dos cinco emuladores."""
    key = emulator.strip().lower()
    try:
        return ADAPTERS[key]
    except KeyError as exc:
        raise ValueError(f"Emulador não suportado: {emulator}") from exc


def list_adapters() -> tuple[EmulatorAdapterSpec, ...]:
    """Retorna os cinco adapters em ordem estável para a GUI e testes."""
    return tuple(ADAPTERS.values())


def schema_settings(emulator: str, domain: str) -> tuple[Setting, ...]:
    """Atalho para obter controles canônicos sem acessar o dicionário global."""
    return get_adapter(emulator).schema(domain)  # type: ignore[return-value]
