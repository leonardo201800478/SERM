"""Registro único que conecta schema, capabilities, adapters e diretórios."""
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
from .retroarch_schema import RETROARCH_SCHEMA
from .supermodel_config import SupermodelConfig


@dataclass(frozen=True, slots=True)
class DirectorySpec:
    """Descreve um diretório de conteúdo exposto pela GUI."""
    key: str
    label: str
    native_key: str | None = None
    multiple: bool = False
    max_entries: int = 1
    relative_default: str | None = None


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
    directories: tuple[DirectorySpec, ...] = ()

    def schema(self, domain: str | None = None) -> dict[str, tuple[Setting, ...]] | tuple[Setting, ...]:
        """Retorna o schema canônico; RetroArch usa seu schema específico."""
        schema = RETROARCH_SCHEMA if self.emulator == "retroarch" else get_schema(self.emulator)
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

    def directory(self, key: str) -> DirectorySpec:
        """Retorna a definição de um diretório do emulador."""
        for item in self.directories:
            if item.key == key:
                return item
        raise ValueError(f"Diretório não suportado: {self.emulator}/{key}")

    def directory_labels(self) -> tuple[tuple[str, str], ...]:
        """Retorna pares estáveis de chave e rótulo para a GUI."""
        return tuple((item.key, item.label) for item in self.directories)


def _mame_factory(root: Path, config: Path) -> EmulatorConfigBackend:
    return EmulatorConfigBackend("mame", config)


def _flycast_factory(root: Path, config: Path) -> FlycastConfig:
    return FlycastConfig(config)


def _supermodel_factory(root: Path, config: Path) -> SupermodelConfig:
    return SupermodelConfig(root)


def _fbneo_factory(root: Path, config: Path) -> FBNeoConfig:
    return FBNeoConfig(config)


def _retroarch_factory(root: Path, config: Path) -> RetroArchConfig:
    return RetroArchConfig(config)


ADAPTERS: dict[str, EmulatorAdapterSpec] = {
    "mame": EmulatorAdapterSpec("mame", "MAME", "mame.exe", "mame.ini", "", "mame-ini", get_capabilities("mame"), _mame_factory,
        (DirectorySpec("roms", "ROMs", "rompath", True, 5), DirectorySpec("samples", "Samples", "samplepath"), DirectorySpec("artwork", "Artwork", "artpath"), DirectorySpec("cfg", "CFG", "cfgpath"), DirectorySpec("nvram", "NVRAM", "nvrampath"), DirectorySpec("states", "Save states", "statepath"), DirectorySpec("snapshots", "Snapshots", "snappath"), DirectorySpec("diff", "Diff", "diffpath"), DirectorySpec("ini", "INI", "inipath"))),
    "flycast": EmulatorAdapterSpec("flycast", "Flycast", "flycast.exe", "emu.cfg", "", "ini-sectioned", get_capabilities("flycast"), _flycast_factory,
        (DirectorySpec("roms", "ROMs", "Dreamcast.ContentPath", True, 4), DirectorySpec("bios", "BIOS", "Dreamcast.BiosPath"), DirectorySpec("vmu", "VMU", "Dreamcast.VMUPath"), DirectorySpec("saves", "Saves", "Dreamcast.SavePath"), DirectorySpec("states", "Save states", "Dreamcast.SavestatePath"), DirectorySpec("textures", "Textures", "Dreamcast.TexturePath"), DirectorySpec("boxart", "Boxart", "Dreamcast.BoxartPath"), DirectorySpec("cheats", "Cheats", "Dreamcast.CheatPath"))),
    "supermodel": EmulatorAdapterSpec("supermodel", "Supermodel", "Supermodel.exe", "Supermodel.ini", "Config", "ini-sectioned", get_capabilities("supermodel"), _supermodel_factory,
        (DirectorySpec("roms", "ROMs", "roms"), DirectorySpec("config", "Config", "config"), DirectorySpec("nvram", "NVRAM", "nvram"), DirectorySpec("saves", "Saves / save states", "saves"), DirectorySpec("assets", "Assets", "assets"))),
    "fbneo": EmulatorAdapterSpec("fbneo", "FBNeo", "fbneo64.ini", "fbneo64.ini", "config", "key-value-space", get_capabilities("fbneo"), _fbneo_factory,
        (DirectorySpec("roms", "ROMs", "roms"), DirectorySpec("bios", "BIOS / ROM suplementar", "bios"), DirectorySpec("samples", "Samples", "samples"), DirectorySpec("cheats", "Cheats", "cheats"), DirectorySpec("previews", "Previews", "previews"), DirectorySpec("titles", "Titles", "titles"), DirectorySpec("snapshots", "Snapshots", "snapshots"), DirectorySpec("history", "History", "history"), DirectorySpec("icons", "Icons", "icons"))),
    "retroarch": EmulatorAdapterSpec("retroarch", "RetroArch", "retroarch.exe", "retroarch.cfg", "", "retroarch-cfg", get_capabilities("retroarch"), _retroarch_factory,
        (DirectorySpec("cores", "Cores", relative_default="cores"), DirectorySpec("system", "System / BIOS", relative_default="system"), DirectorySpec("saves", "Saves", relative_default="saves"), DirectorySpec("states", "States", relative_default="states"), DirectorySpec("shaders", "Shaders", relative_default="shaders"), DirectorySpec("overlays", "Overlays", relative_default="overlays"), DirectorySpec("downloads", "Downloads", relative_default="downloads"))),
}


def get_adapter(emulator: str) -> EmulatorAdapterSpec:
    """Retorna o adapter consolidado de um dos cinco emuladores."""
    key = emulator.strip().lower()
    try:
        return ADAPTERS[key]
    except KeyError as exc:
        raise ValueError(f"Emulador não suportado: {emulator}") from exc


def list_adapters() -> tuple[EmulatorAdapterSpec, ...]:
    """Retorna os cinco adapters em ordem estável."""
    return tuple(ADAPTERS.values())


def schema_settings(emulator: str, domain: str) -> tuple[Setting, ...]:
    """Atalho para obter controles canônicos."""
    return get_adapter(emulator).schema(domain)  # type: ignore[return-value]
