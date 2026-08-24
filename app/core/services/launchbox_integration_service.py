"""Integração segura com LaunchBox."""
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
        """Retorna Core ou .exe conforme o tipo de execução."""
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

    # Nomes antigos/genéricos que devem desaparecer da árvore. C64 não fica
    # aqui porque é convertido para o sistema canônico "Commodore 64".
    EXCLUDED_SYSTEM_NAMES = {
        "sega 8-bit", "sega 8 bit", "sega 8-bit (ms/gg/sg-1000)",
        "sega 8 bit (ms/gg/sg-1000)", "game boy/game boy color",
        "game boy / game boy color", "neo geo pocket (color)",
        "microsoft xbox",
    }
    EXCLUDED_CORE_TERMS = ("advanced test core", "advanced test", "advanced_test")

    REQUIRED_SYSTEMS = {
        "sega naomi": ("Sega Naomi", "arcade", "3D", ("naomi", "sega naomi")),
        "sega naomi 2": ("Sega Naomi 2", "arcade", "3D", ("naomi2", "naomi 2", "sega naomi 2")),
        "sammy atomiswave": ("Sammy Atomiswave", "arcade", "3D", ("atomiswave", "sammy atomiswave")),
        "sega system sp": ("SEGA System SP", "arcade", "3D", ("systemsp", "system sp", "sega system sp")),
        "sega model 3": ("Sega Model 3", "arcade", "3D", ("model3", "model 3", "sega model 3")),
        "sega model 2": ("Sega Model 2", "arcade", "3D", ("model2", "model 2", "sega model 2")),
        "neo geo aes": ("Neo Geo AES", "arcade", "16-bit", ("neo geo aes", "neogeo aes", "aes")),
        "nintendo wii": ("Nintendo Wii", "consoles", "128-bit+", ("wii", "nintendo wii")),
        "commodore cdtv": ("Commodore CDTV", "consoles", "16-bit", ("cdtv", "commodore cdtv")),
        "nec turbografx-16": ("NEC TurboGrafx-16", "consoles", "16-bit", ("turbografx-16", "turbografx16", "pc engine", "pcengine")),
        "nec turbografx-cd": ("NEC TurboGrafx-CD", "consoles", "16-bit", ("turbografx-cd", "turbografxcd", "pc engine cd", "pcenginecd")),
        "nintendo satellaview": ("Nintendo Satellaview", "consoles", "16-bit", ("satellaview", "nintendo satellaview")),
        "nintendo sufami": ("Nintendo Sufami", "consoles", "16-bit", ("sufami", "nintendo sufami")),
        "sega 32x": ("Sega 32X", "consoles", "16-bit", ("32x", "sega 32x")),
        "sega cd 32x": ("Sega CD 32X", "consoles", "16-bit", ("sega cd 32x", "sega32xcd", "32x cd")),
        "sega genesis": ("Sega Genesis", "consoles", "16-bit", ("genesis", "sega genesis", "megadrive", "mega drive")),
        "commodore amiga cd32": ("Commodore Amiga CD32", "consoles", "32-bit", ("amiga cd32", "commodore amiga cd32", "cd32")),
        "atari jaguar": ("Atari Jaguar", "consoles", "64-bit", ("jaguar", "atari jaguar")),
        "nintendo 64dd": ("Nintendo 64DD", "consoles", "64-bit", ("64dd", "nintendo 64dd", "n64dd")),
        "nintendo famicom disk system": ("Nintendo Famicom Disk System", "consoles", "8-bit", ("famicom disk system", "fds", "nintendo fds")),
        "sega sg-1000": ("Sega SG-1000", "consoles", "8-bit", ("sg-1000", "sg1000", "sega sg-1000")),
        "snk neo geo pocket": ("SNK Neo Geo Pocket", "portables", "16-bit", ("neo geo pocket", "neogeo pocket", "ngp")),
        "wonderswan color": ("WonderSwan Color", "portables", "16-bit", ("wonderswan color", "wonderswan_color")),
        "nintendo game boy": ("Nintendo Game Boy", "portables", "8-bit", ("game boy", "gameboy", "nintendo game boy")),
        "nintendo game boy color": ("Nintendo Game Boy Color", "portables", "8-bit", ("game boy color", "gameboy color", "gameboy_color", "nintendo game boy color")),
        "commodore amiga": ("Commodore Amiga", "computers", "16-bit", ("commodore amiga", "amiga")),
        "commodore amiga aga": ("Commodore Amiga AGA", "computers", "32-bit", ("amiga aga", "commodore amiga aga")),
        "commodore 64": ("Commodore 64", "computers", "8-bit", ("commodore 64", "c64")),
        "microsoft msx": ("Microsoft MSX", "computers", "8-bit", ("msx", "microsoft msx")),
        "sinclair zx spectrum": ("Sinclair ZX Spectrum", "computers", "8-bit", ("zx spectrum", "zxspectrum", "spectrum", "sinclair zx spectrum")),
    }

    MANDATORY_STANDALONES = (
        {"system_id": "sega naomi", "name": "Flycast Standalone", "emulator": "flycast", "score": 95},
        {"system_id": "sega naomi 2", "name": "Flycast Standalone", "emulator": "flycast", "score": 95},
        {"system_id": "sammy atomiswave", "name": "Flycast Standalone", "emulator": "flycast", "score": 95},
        {"system_id": "sega system sp", "name": "Flycast Standalone", "emulator": "flycast", "score": 95},
        {"system_id": "sega model 3", "name": "Supermodel Standalone", "emulator": "supermodel", "score": 100},
        {"system_id": "sega model 2", "name": "MAME Standalone", "emulator": "mame", "score": 100},
        {"system_id": "neo geo aes", "name": "FBNeo Standalone", "emulator": "fbneo", "score": 100},
        {"system_id": "neo geo aes", "name": "MAME Standalone", "emulator": "mame", "score": 95},
    )

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
        installation = LaunchBoxInstallation(executable, root, data_dir, data_dir / "Emulators.xml", data_dir / "Platforms.xml")
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
        return [
            {child.tag.rsplit("}", 1)[-1]: (child.text or "").strip() for child in element}
            for element in tree.getroot().iter()
            if element.tag.rsplit("}", 1)[-1].casefold() == "emulatorplatform"
        ]

    @staticmethod
    def _read_default_associations(rows: list[dict[str, str]]) -> dict[str, str]:
        """Obtém o candidato padrão por plataforma a partir do XML."""
        return {
            row["Platform"].strip().casefold(): f"{row.get('Emulator', '')}:{row.get('Core', '')}".casefold()
            for row in rows
            if row.get("Platform", "").strip() and row.get("Default", "").casefold() in {"true", "1", "yes"}
        }

    @staticmethod
    def _normalize(value: str | None) -> str:
        """Normaliza nomes para comparação de identidade."""
        return " ".join(value.replace("\\", "/").split()).casefold() if value else ""

    @staticmethod
    def _system_key(name: str) -> str:
        """Cria uma chave estável para o nome local da plataforma."""
        return " ".join(name.casefold().split())

    @classmethod
    def _canonical_system(cls, value: str) -> tuple[str, str, str] | None:
        """Resolve aliases para o nome oficial desejado pelo projeto."""
        normalized = cls._system_key(value)
        for name, group, generation, aliases in cls.REQUIRED_SYSTEMS.values():
            if normalized == cls._system_key(name) or any(normalized == cls._system_key(alias) for alias in aliases):
                return name, group, generation
        return None

    @classmethod
    def _is_excluded_system(cls, value: str) -> bool:
        """Informa se a plataforma foi explicitamente excluída."""
        return cls._system_key(value) in {cls._system_key(v) for v in cls.EXCLUDED_SYSTEM_NAMES}

    @classmethod
    def _is_excluded_core(cls, info: RetroArchInfoCore) -> bool:
        """Remove cores de teste do catálogo."""
        text = " ".join((info.corename, info.display_name, info.system_name or "", info.system_id or "")).casefold()
        return any(term in text for term in cls.EXCLUDED_CORE_TERMS)

    @classmethod
    def _find_platform(cls, name: str, systems: dict[str, LaunchBoxSystem], system_id: str | None = None, databases: Iterable[str] = ()) -> LaunchBoxSystem | None:
        """Localiza a plataforma por nome, alias, systemid ou database."""
        candidates = [name, system_id or "", *databases]
        normalized = [cls._system_key(v) for v in candidates if v]
        for candidate in candidates:
            canonical = cls._canonical_system(candidate)
            if canonical:
                normalized.append(cls._system_key(canonical[0]))
        for key in normalized:
            if key in systems:
                return systems[key]
        for system in systems.values():
            system_key = cls._system_key(system.name)
            if any(key == system_key or key in system_key or system_key in key for key in normalized):
                return system
        return None

    @classmethod
    def _deduplicate_options(cls, options: Iterable[LaunchBoxCoreOption]) -> list[LaunchBoxCoreOption]:
        """Remove duplicatas usando Emulador + opção + core/executável."""
        result: list[LaunchBoxCoreOption] = []
        seen: set[tuple[str, str, str]] = set()
        for option in options:
            target = option.core_dll or (option.executable.as_posix() if option.executable else option.name)
            key = (cls._normalize(option.emulator), cls._normalize(option.name), cls._normalize(target))
            if key not in seen:
                seen.add(key)
                result.append(option)
        return result

    def scan_retroarch(self, info_directory: Path) -> list[RetroArchInfoCore]:
        """Lê todos os .info locais do RetroArch."""
        return self.info_service.scan_directory(Path(info_directory))

    def build_systems(self, infos: Iterable[RetroArchInfoCore], installation: LaunchBoxInstallation | None = None) -> list[LaunchBoxSystem]:
        """Monta as plataformas finais aplicando exclusões, aliases e catálogo mínimo."""
        systems: dict[str, LaunchBoxSystem] = {}
        existing_platforms = installation.platforms if installation else {}
        defaults = installation.default_options if installation else {}
        core_root = self.config.get_emulator_path("retroarch", "cores")
        retroarch_exe = self.config.retroarch_path

        for platform_key, fields in existing_platforms.items():
            raw_name = fields.get("Name") or fields.get("Title") or platform_key
            if self._is_excluded_system(raw_name):
                continue
            canonical = self._canonical_system(raw_name)
            name = canonical[0] if canonical else raw_name
            group, generation = (canonical[1], canonical[2]) if canonical else self.classify_system(platform_key, raw_name)
            systems[self._system_key(name)] = LaunchBoxSystem(self._system_key(name), name, group, generation, existing=True)

        for name, group, generation, _ in self.REQUIRED_SYSTEMS.values():
            key = self._system_key(name)
            if key not in systems:
                systems[key] = LaunchBoxSystem(key, name, group, generation, existing=False)

        for info in infos:
            if self._is_excluded_core(info):
                continue
            name = info.system_name or info.display_name or info.corename
            # C64 é alias válido de Commodore 64; os demais nomes excluídos
            # continuam fora da árvore.
            if self._is_excluded_system(name) and not self._canonical_system(name):
                continue
            platform = self._find_platform(name, systems, info.system_id, info.databases)
            if platform is None:
                canonical = self._canonical_system(name) or self._canonical_system(info.system_id or "")
                if canonical:
                    platform = systems.get(self._system_key(canonical[0]))
            if platform is None:
                group, generation = self.classify_system(info.system_id or info.corename, name)
                platform = LaunchBoxSystem(self._system_key(name), name, group, generation, existing=False)
                systems[platform.system_id] = platform
            dll = f"{info.corename}_libretro.dll"
            core_path = (Path(core_root) / dll).resolve() if core_root else None
            option = LaunchBoxCoreOption(
                name=info.display_name or info.corename,
                emulator="retroarch",
                core_dll=dll,
                core_path=core_path,
                executable=retroarch_exe,
                score=self._score_core(info),
                command_line=self.command_line(platform.name, core_path),
                existing=self._core_is_existing(installation, dll, platform.name),
            )
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
        """Identidade da associação candidata."""
        target = option.core_dll or (option.executable.as_posix() if option.executable else option.name)
        return cls._normalize(option.emulator), cls._normalize(option.name), cls._normalize(target)

    @staticmethod
    def _core_is_existing(installation: LaunchBoxInstallation | None, dll: str, platform: str) -> bool:
        """Verifica se a associação específica plataforma + core já existe no XML."""
        if installation is None:
            return False
        return any(row.get("Platform", "").casefold() == platform.casefold() and row.get("Core", "").casefold() == dll.casefold() for row in installation.emulator_platforms)

    @staticmethod
    def _label(emulator: str) -> str:
        """Retorna o título conhecido do emulador."""
        return {"retroarch": "RetroArch", "mame": "MAME", "flycast": "Flycast", "fbneo": "FBNeo", "supermodel": "Supermodel"}.get(emulator, emulator)

    def add_standalones(self, systems: list[LaunchBoxSystem], standalone: list[dict] | None = None) -> list[LaunchBoxSystem]:
        """Adiciona os standalones às plataformas corretas, nunca como sistema próprio."""
        executable_map = {"mame": self.config.mame_path, "flycast": self.config.flycast_path, "fbneo": self.config.fbneo_path, "supermodel": self.config.supermodel_path}
        requested = list(standalone or []) + list(self.MANDATORY_STANDALONES)
        seen_requests: set[tuple[str, str]] = set()
        for item in requested:
            system_id = str(item.get("system_id", "")).casefold()
            emulator = str(item.get("emulator", "mame")).casefold()
            canonical = self._canonical_system(system_id)
            if canonical:
                system_id, name = self._system_key(canonical[0]), canonical[0]
            else:
                name = str(item.get("name", system_id))
            request_key = (system_id, emulator)
            if not system_id or request_key in seen_requests:
                continue
            seen_requests.add(request_key)
            target = next((s for s in systems if s.system_id == system_id), None)
            if target is None:
                group, generation = self.classify_system(system_id, name)
                target = LaunchBoxSystem(system_id, name, group, generation, existing=False)
                systems.append(target)
            option = LaunchBoxCoreOption(
                name=item.get("name", self._label(emulator)),
                emulator=emulator,
                executable=executable_map.get(emulator),
                score=int(item.get("score", 90)),
                command_line=self.standalone_command(emulator, item.get("command_line", "")),
            )
            if not any(o.key == option.key for o in target.options):
                target.options.append(option)
            self._select_default(target)
        return sorted(systems, key=lambda s: (self.GROUP_ORDER.index(s.group), s.generation.casefold(), s.name.casefold()))

    def classify_system(self, system_id: str, name: str) -> tuple[str, str]:
        """Classifica por overrides externos e fallback conservador."""
        overrides = self.group_rules.get("system_overrides", {})
        override = overrides.get(system_id, {}) or overrides.get(name, {})
        if override:
            return override.get("group", "consoles"), override.get("generation", "Outros")
        canonical = self._canonical_system(name) or self._canonical_system(system_id)
        if canonical:
            return canonical[1], canonical[2]
        text = f"{system_id} {name}".casefold()
        if any(k in text for k in ("arcade", "naomi", "atomiswave", "mame", "fbneo", "model 2", "model 3")):
            return "arcade", "Outros"
        if any(k in text for k in ("game boy", "gameboy", "game gear", "lynx", "neo geo pocket", "wonderswan", "nintendo ds", "gba", "gamepark", "psp", "vita", "pokemon mini")):
            return "portables", "Outros"
        if any(k in text for k in ("apple ii", "amstrad", "commodore", "msx", "zx spectrum", "dos", "pc-98", "x68000", "computer", "amiga", "windows")):
            return "computers", "Outros"
        return "consoles", "Outros"

    def _score_core(self, info: RetroArchInfoCore) -> int:
        """Calcula uma preferência inicial determinística."""
        text = f"{info.corename} {info.display_name}".casefold()
        score = 50
        if "accuracy" in text or "beetle" in text or "bsnes" in text or "mesen" in text:
            score += 20
        if "retroachievement" in text:
            score += 10
        if "hardware" in text or "vulkan" in text:
            score += 5
        return score

    @staticmethod
    def _select_default(system: LaunchBoxSystem) -> None:
        """Garante exatamente um padrão entre as opções do sistema."""
        if not system.options:
            return
        selected = next((o for o in system.options if o.default), None) or max(system.options, key=lambda o: (o.score, o.name.casefold()))
        for option in system.options:
            option.default = option is selected

    def set_default_option(self, system: LaunchBoxSystem, option: LaunchBoxCoreOption) -> None:
        """Define manualmente um único padrão."""
        if option not in system.options:
            raise ValueError("A opção não pertence ao sistema selecionado.")
        for candidate in system.options:
            candidate.default = candidate is option

    def command_line(self, platform: str, core_path: Path | None) -> str:
        """Obtém o command line configurado para a plataforma/core."""
        template = self.rules.get("retroarch", {}).get("platform_overrides", {}).get(platform) or self.rules.get("retroarch", {}).get("default", "-L \"{core_path}\"")
        return template.format(core_path=str(core_path) if core_path else "{core_path}", core_dll=core_path.name if core_path else "{core_dll}", platform=platform)

    def standalone_command(self, emulator: str, template: str = "") -> str:
        """Obtém o command line externo para um standalone."""
        return template or self.rules.get("standalone", {}).get(emulator, {}).get("default", "")

    def export_emulators_xml(self, launchbox_dir: Path, systems: Iterable[LaunchBoxSystem], overwrite: bool = False) -> Path:
        """Faz merge usando Emulator + EmulatorPlatform, preservando múltiplos cores."""
        data_dir = Path(launchbox_dir) / "Data"
        if not data_dir.is_dir():
            raise FileNotFoundError(f"Pasta Data não encontrada: {data_dir}")
        target = data_dir / "Emulators.xml"
        if target.exists():
            try:
                tree = ET.parse(target)
            except ET.ParseError as exc:
                raise ValueError(f"Emulators.xml inválido; nenhuma alteração foi feita: {exc}") from exc
            root = tree.getroot()
            shutil.copy2(target, target.with_name(target.name + ".arcademanager.bak"))
        else:
            root = ET.Element("LaunchBox")
            tree = ET.ElementTree(root)
        for system in systems:
            for option in system.options:
                emulator = self._find_emulator(root, self._label(option.emulator))
                if emulator is None:
                    emulator = self._create_emulator(root, self._label(option.emulator), option.executable)
                self._merge_emulator_platform(root, emulator, system.name, option)
            self._normalize_defaults(root, system)
        ET.indent(root, space="  ")
        tmp = target.with_name(target.name + ".tmp")
        tree.write(tmp, encoding="utf-8", xml_declaration=True)
        tmp.replace(target)
        return target

    @staticmethod
    def _find_emulator(root: ET.Element, title: str) -> ET.Element | None:
        """Localiza um Emulator existente pelo título."""
        return next((element for element in root if element.tag.rsplit("}", 1)[-1].casefold() == "emulator" and element.findtext("Title", "").casefold() == title.casefold()), None)

    @staticmethod
    def _create_emulator(root: ET.Element, title: str, executable: Path | None) -> ET.Element:
        """Cria somente o registro Emulator necessário."""
        emulator = ET.Element("Emulator")
        _set_child(emulator, "ID", str(uuid.uuid4()))
        _set_child(emulator, "Title", title)
        _set_child(emulator, "ApplicationPath", str(executable) if executable else "")
        _set_child(emulator, "CommandLine", "")
        _set_child(emulator, "DefaultPlatform", "")
        _set_child(emulator, "NoQuotes", "false")
        _set_child(emulator, "NoSpace", "false")
        root.append(emulator)
        return emulator

    @staticmethod
    def _emulator_id(emulator: ET.Element) -> str:
        """Retorna o ID persistido de um Emulator."""
        return emulator.findtext("ID", "").strip()

    @staticmethod
    def _merge_emulator_platform(root: ET.Element, emulator: ET.Element, platform: str, option: LaunchBoxCoreOption) -> None:
        """Insere ou atualiza uma associação sem colapsar cores diferentes."""
        emulator_id = LaunchBoxIntegrationService._emulator_id(emulator)
        if not emulator_id:
            emulator_id = str(uuid.uuid4())
            _set_child(emulator, "ID", emulator_id)
        target = None
        for row in root:
            if row.tag.rsplit("}", 1)[-1].casefold() != "emulatorplatform":
                continue
            if row.findtext("Emulator", "").casefold() != emulator_id.casefold() or row.findtext("Platform", "").casefold() != platform.casefold():
                continue
            if row.findtext("Core", "").casefold() == (option.core_dll or "").casefold():
                target = row
                break
        if target is None:
            target = ET.Element("EmulatorPlatform")
            _set_child(target, "Emulator", emulator_id)
            _set_child(target, "Platform", platform)
            _set_child(target, "CommandLine", option.command_line)
            _set_child(target, "Default", "true" if option.default else "false")
            if option.core_dll:
                _set_child(target, "Core", option.core_dll)
            root.append(target)
        else:
            _set_child(target, "CommandLine", option.command_line)
            if option.core_dll:
                _set_child(target, "Core", option.core_dll)

    @staticmethod
    def _normalize_defaults(root: ET.Element, system: LaunchBoxSystem) -> None:
        """Garante exatamente um Default=true entre os candidatos do sistema."""
        selected = next((o for o in system.options if o.default), None)
        if selected is None:
            return
        selected_emulator = LaunchBoxIntegrationService._label(selected.emulator).casefold()
        for row in root:
            if row.tag.rsplit("}", 1)[-1].casefold() != "emulatorplatform" or row.findtext("Platform", "").casefold() != system.name.casefold():
                continue
            emulator_id = row.findtext("Emulator", "").casefold()
            emulator = next((e for e in root if e.tag.rsplit("}", 1)[-1].casefold() == "emulator" and e.findtext("ID", "").casefold() == emulator_id), None)
            if emulator is None:
                continue
            selected_row = emulator.findtext("Title", "").casefold() == selected_emulator
            if selected.core_dll:
                selected_row = selected_row and row.findtext("Core", "").casefold() == selected.core_dll.casefold()
            _set_child(row, "Default", "true" if selected_row else "false")


def _set_child(parent: ET.Element, name: str, value: str) -> None:
    """Atualiza/cria um elemento XML sem remover os demais campos."""
    node = parent.find(name)
    if node is None:
        node = ET.SubElement(parent, name)
    node.text = value


__all__ = ["LaunchBoxIntegrationService", "LaunchBoxSystem", "LaunchBoxCoreOption", "LaunchBoxInstallation"]
