"""Integração segura com LaunchBox.

O LaunchBox mantém os emuladores e suas associações de plataformas como
registros irmãos no XML: ``Emulator`` e ``EmulatorPlatform``. O serviço
preserva esses registros existentes e só cria/atualiza o que o ARCADE
MANAGER controla.
"""
from __future__ import annotations

import json
import shutil
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from app.config.app_config import AppConfig
from app.core.services.retroarch_info_service import RetroArchInfoCore, RetroArchInfoService


@dataclass(slots=True)
class LaunchBoxCoreOption:
    """Core ou executável disponível para um sistema LaunchBox."""

    name: str
    emulator: str
    core_dll: str | None = None
    core_path: Path | None = None
    executable: Path | None = None
    default: bool = False
    score: int = 0
    command_line: str = ""
    existing: bool = False

    @property
    def kind(self) -> str:
        """Retorna ``Core`` ou ``.exe`` conforme o tipo de execução."""
        return "Core" if self.core_dll else ".exe"

    @property
    def key(self) -> str:
        """Identificador estável do candidato."""
        return f"{self.emulator}:{self.core_dll or self.executable or self.name}".casefold()


@dataclass(slots=True)
class LaunchBoxSystem:
    """Sistema real do Platforms.xml e suas opções de emulação."""

    system_id: str
    name: str
    group: str
    generation: str
    options: list[LaunchBoxCoreOption] = field(default_factory=list)
    existing: bool = True


@dataclass(slots=True)
class LaunchBoxInstallation:
    """Estado importado de uma instalação existente do LaunchBox."""

    executable: Path
    root: Path
    data_dir: Path
    emulators_xml: Path
    platforms_xml: Path
    emulators: dict[str, dict[str, str]] = field(default_factory=dict)
    platforms: dict[str, dict[str, str]] = field(default_factory=dict)
    emulator_platforms: list[dict[str, str]] = field(default_factory=list)
    default_options: dict[str, str] = field(default_factory=dict)
    emulators_loaded: bool = False
    platforms_loaded: bool = False


class LaunchBoxIntegrationService:
    """Importa, completa e exporta configurações sem reconstruir o LaunchBox."""

    GROUP_ORDER = ("consoles", "portables", "computers", "arcade")

    def __init__(self, project_root: Path | None = None, config: AppConfig | None = None) -> None:
        """Inicializa usando AppConfig como fonte dos executáveis."""
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.config = config or AppConfig()
        self.rules_path = self.project_root / "data" / "launchbox" / "command_lines.json"
        self.groups_path = self.project_root / "data" / "launchbox" / "system_groups.json"
        self.info_service = RetroArchInfoService()
        self.rules: dict = {}
        self.group_rules: dict = {}
        self.reload_rules()

    @staticmethod
    def _load_json(path: Path) -> dict:
        """Carrega um arquivo JSON externo de forma segura."""
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {}

    def reload_rules(self) -> None:
        """Recarrega regras externas sem tocar nos XMLs do LaunchBox."""
        self.rules = self._load_json(self.rules_path)
        self.group_rules = self._load_json(self.groups_path)

    def load_launchbox_installation(self, executable: Path) -> LaunchBoxInstallation:
        """Carrega Data/Platforms.xml e Data/Emulators.xml sem modificá-los."""
        executable = executable.resolve()
        if executable.name.casefold() != "launchbox.exe":
            raise ValueError("O arquivo selecionado deve ser LaunchBox.exe.")
        root = executable.parent
        data_dir = root / "Data"
        if not data_dir.is_dir():
            raise FileNotFoundError(f"Pasta Data não encontrada: {data_dir}")
        installation = LaunchBoxInstallation(executable=executable, root=root, data_dir=data_dir, emulators_xml=data_dir / "Emulators.xml", platforms_xml=data_dir / "Platforms.xml")
        if installation.emulators_xml.is_file():
            installation.emulators = self._read_named_records(installation.emulators_xml, ("Emulator",), ("Title", "Name"))
            installation.emulator_platforms = self._read_emulator_platforms(installation.emulators_xml)
            installation.default_options = self._read_default_associations(installation.emulator_platforms)
            installation.emulators_loaded = True
        if installation.platforms_xml.is_file():
            installation.platforms = self._read_named_records(installation.platforms_xml, ("Platform",), ("Name", "Title"))
            installation.platforms_loaded = True
        return installation

    @staticmethod
    def _read_named_records(path: Path, element_names: tuple[str, ...], name_fields: tuple[str, ...]) -> dict[str, dict[str, str]]:
        """Lê registros XML preservando somente os campos textuais."""
        tree = ET.parse(path)
        records: dict[str, dict[str, str]] = {}
        wanted = {name.casefold() for name in element_names}
        for element in tree.getroot().iter():
            if element.tag.rsplit("}", 1)[-1].casefold() not in wanted:
                continue
            fields = {child.tag.rsplit("}", 1)[-1]: (child.text or "").strip() for child in element if (child.text or "").strip()}
            name = next((fields.get(field) for field in name_fields if fields.get(field)), None)
            if name:
                records[name.casefold()] = fields
        return records

    @staticmethod
    def _read_emulator_platforms(path: Path) -> list[dict[str, str]]:
        """Lê EmulatorPlatform como registros irmãos dos Emulator."""
        tree = ET.parse(path)
        result: list[dict[str, str]] = []
        for element in tree.getroot().iter():
            if element.tag.rsplit("}", 1)[-1].casefold() != "emulatorplatform":
                continue
            result.append({child.tag.rsplit("}", 1)[-1]: (child.text or "").strip() for child in element})
        return result

    @staticmethod
    def _read_default_associations(rows: list[dict[str, str]]) -> dict[str, str]:
        """Obtém o candidato padrão por plataforma a partir do XML."""
        result: dict[str, str] = {}
        for row in rows:
            platform = row.get("Platform", "").strip()
            if not platform:
                continue
            if row.get("Default", "").casefold() in {"true", "1", "yes"}:
                result[platform.casefold()] = f"{row.get('Emulator', '')}:{row.get('Core', '')}".casefold()
        return result

    @staticmethod
    def _normalize(value: str | None) -> str:
        """Normaliza nomes para comparação de identidade sem alterar o valor original."""
        if not value:
            return ""
        return " ".join(value.replace("\\", "/").split()).casefold()

    @classmethod
    def _association_key(cls, row: dict[str, str]) -> tuple[str, str, str]:
        """Chave única de uma associação LaunchBox: emulador + plataforma + core/executável."""
        emulator = row.get("Emulator", "") or row.get("EmulatorId", "")
        platform = row.get("Platform", "")
        core = row.get("Core", "") or row.get("CoreDll", "") or row.get("CorePath", "")
        return cls._normalize(emulator), cls._normalize(platform), cls._normalize(core)

    @classmethod
    def _deduplicate_options(cls, options: Iterable[LaunchBoxCoreOption]) -> list[LaunchBoxCoreOption]:
        """Remove duplicatas da GUI usando Emulador + Sistema + Core como identidade."""
        result: list[LaunchBoxCoreOption] = []
        seen: set[tuple[str, str, str]] = set()
        for option in options:
            key = (cls._normalize(option.emulator), cls._normalize(option.name), cls._normalize(option.core_dll or option.executable.as_posix() if option.executable else option.name))
            if key in seen:
                continue
            seen.add(key)
            result.append(option)
        return result

    def scan_retroarch(self, info_directory: Path) -> list[RetroArchInfoCore]:
        """Lê todos os .info locais do RetroArch."""
        return self.info_service.scan_directory(Path(info_directory))

    def build_systems(self, infos: Iterable[RetroArchInfoCore], installation: LaunchBoxInstallation | None = None) -> list[LaunchBoxSystem]:
        """Começa por TODOS os sistemas do Platforms.xml e adiciona cada core uma única vez."""
        systems: dict[str, LaunchBoxSystem] = {}
        existing_platforms = installation.platforms if installation else {}
        defaults = installation.default_options if installation else {}
        core_root = self.config.get_emulator_path("retroarch", "cores")
        retroarch_exe = self.config.retroarch_path

        for platform_key, fields in existing_platforms.items():
            name = fields.get("Name") or fields.get("Title") or platform_key
            group, generation = self.classify_system(platform_key, name)
            systems[self._system_key(name)] = LaunchBoxSystem(system_id=self._system_key(name), name=name, group=group, generation=generation, existing=True)

        for info in infos:
            name = info.system_name or info.display_name or info.corename
            platform = self._find_platform(name, systems, info.system_id, info.databases)
            if platform is None:
                group, generation = self.classify_system(info.system_id or info.corename, name)
                platform = LaunchBoxSystem(system_id=self._system_key(name), name=name, group=group, generation=generation, existing=False)
                systems[platform.system_id] = platform
            dll = f"{info.corename}_libretro.dll"
            core_path = (Path(core_root) / dll).resolve() if core_root else None
            option = LaunchBoxCoreOption(name=info.display_name or info.corename, emulator="retroarch", core_dll=dll, core_path=core_path, executable=retroarch_exe, score=self._score_core(info), command_line=self.command_line(platform.name, core_path), existing=self._core_is_existing(installation, dll, platform.name))
            default_key = defaults.get(platform.name.casefold(), "")
            if default_key.endswith(f":{dll}".casefold()):
                option.default = True
            if not any(self._option_identity(existing) == self._option_identity(option) for existing in platform.options):
                platform.options.append(option)

        for system in systems.values():
            system.options = self._deduplicate_options(system.options)
            self._select_default(system)
        return sorted(systems.values(), key=lambda s: (self.GROUP_ORDER.index(s.group), s.generation.casefold(), s.name.casefold()))

    @classmethod
    def _option_identity(cls, option: LaunchBoxCoreOption) -> tuple[str, str, str]:
        """Identidade da associação candidata, independente do texto exibido na GUI."""
        target = option.core_dll or (option.executable.as_posix() if option.executable else option.name)
        return cls._normalize(option.emulator), cls._normalize(option.name), cls._normalize(target)

    @staticmethod
    def _system_key(name: str) -> str:
        """Cria uma chave estável para o nome local da plataforma."""
        return " ".join(name.casefold().split())

    @classmethod
    def _find_platform(cls, name: str, systems: dict[str, LaunchBoxSystem], system_id: str | None = None, databases: Iterable[str] = ()) -> LaunchBoxSystem | None:
        """Localiza a plataforma por nome, systemid ou database antes de criar uma nova."""
        candidates = [name, system_id or "", *databases]
        normalized = [cls._system_key(value) for value in candidates if value]
        for key in normalized:
            if key in systems:
                return systems[key]
        for system in systems.values():
            system_key = cls._system_key(system.name)
            if any(key == system_key or key in system_key or system_key in key for key in normalized):
                return system
        return None
