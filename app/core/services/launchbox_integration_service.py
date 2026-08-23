"""Integração segura com LaunchBox: importa estado existente e faz merge seletivo."""
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
    """Core/emulador disponível para um sistema LaunchBox."""
    name: str
    emulator: str
    core_dll: str | None = None
    core_path: Path | None = None
    executable: Path | None = None
    default: bool = False
    score: int = 0
    command_line: str = ""
    existing: bool = False


@dataclass(slots=True)
class LaunchBoxSystem:
    """Sistema agrupado em uma geração e grupo de hardware."""
    system_id: str
    name: str
    group: str
    generation: str
    options: list[LaunchBoxCoreOption] = field(default_factory=list)
    existing: bool = False


@dataclass(slots=True)
class LaunchBoxInstallation:
    """Estado já existente na instalação do LaunchBox."""
    executable: Path
    root: Path
    data_dir: Path
    emulators_xml: Path
    platforms_xml: Path
    emulators: dict[str, dict[str, str]] = field(default_factory=dict)
    platforms: dict[str, dict[str, str]] = field(default_factory=dict)
    emulators_loaded: bool = False
    platforms_loaded: bool = False


class LaunchBoxIntegrationService:
    """Importa o estado existente e só acrescenta o que estiver faltando."""

    GROUP_ORDER = ("consoles", "portables", "computers", "arcade")

    def __init__(self, project_root: Path | None = None, config: AppConfig | None = None) -> None:
        """Inicializa usando AppConfig como fonte de verdade dos executáveis."""
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
        """Carrega JSON de regras externas."""
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {}

    def reload_rules(self) -> None:
        """Recarrega regras sem modificar configurações nativas."""
        self.rules = self._load_json(self.rules_path)
        self.group_rules = self._load_json(self.groups_path)

    def load_launchbox_installation(self, executable: Path) -> LaunchBoxInstallation:
        """Localiza Data e importa Platforms.xml/Emulators.xml sem alterá-los."""
        executable = executable.resolve()
        if executable.name.casefold() != "launchbox.exe":
            raise ValueError("O arquivo selecionado deve ser LaunchBox.exe.")
        root = executable.parent
        data_dir = root / "Data"
        if not data_dir.is_dir():
            raise FileNotFoundError(f"Pasta Data não encontrada: {data_dir}")
        installation = LaunchBoxInstallation(
            executable=executable,
            root=root,
            data_dir=data_dir,
            emulators_xml=data_dir / "Emulators.xml",
            platforms_xml=data_dir / "Platforms.xml",
        )
        if installation.emulators_xml.is_file():
            installation.emulators = self._read_named_records(installation.emulators_xml, ("Emulator",), ("Title", "Name"))
            installation.emulators_loaded = True
        if installation.platforms_xml.is_file():
            installation.platforms = self._read_named_records(installation.platforms_xml, ("Platform",), ("Name", "Title"))
            installation.platforms_loaded = True
        return installation

    @staticmethod
    def _read_named_records(path: Path, element_names: tuple[str, ...], name_fields: tuple[str, ...]) -> dict[str, dict[str, str]]:
        """Lê registros de XML de forma tolerante a pequenas diferenças de schema."""
        tree = ET.parse(path)
        root = tree.getroot()
        records: dict[str, dict[str, str]] = {}
        wanted = {name.casefold() for name in element_names}
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1].casefold() not in wanted:
                continue
            fields: dict[str, str] = {}
            for child in element:
                key = child.tag.rsplit("}", 1)[-1]
                value = (child.text or "").strip()
                if value:
                    fields[key] = value
            name = next((fields.get(field) for field in name_fields if fields.get(field)), None)
            if name:
                records[name.casefold()] = fields
        return records

    def scan_retroarch(self, info_directory: Path) -> list[RetroArchInfoCore]:
        """Lê os .info locais do RetroArch."""
        return self.info_service.scan_directory(Path(info_directory))

    def build_systems(self, infos: Iterable[RetroArchInfoCore], installation: LaunchBoxInstallation | None = None) -> list[LaunchBoxSystem]:
        """Agrupa cores e marca sistemas/core já presentes no LaunchBox."""
        systems: dict[str, LaunchBoxSystem] = {}
        core_root = self.config.get_emulator_path("retroarch", "cores")
        retroarch_exe = self.config.retroarch_path
        existing_platforms = installation.platforms if installation else {}
        existing_retroarch = self._existing_core_names(installation) if installation else set()
        for info in infos:
            system_id = (info.system_id or info.corename).casefold()
            name = info.system_name or info.display_name or info.corename
            group, generation = self.classify_system(system_id, name)
            platform_key = self._platform_key(name, existing_platforms)
            system = systems.setdefault(
                system_id,
                LaunchBoxSystem(system_id, existing_platforms.get(platform_key, {}).get("Name", name), group, generation, existing=bool(platform_key)),
            )
            dll = f"{info.corename}_libretro.dll"
            core_path = (Path(core_root) / dll).resolve() if core_root else None
            option = LaunchBoxCoreOption(
                name=info.display_name or info.corename,
                emulator="retroarch",
                core_dll=dll,
                core_path=core_path,
                executable=retroarch_exe,
                score=self._score_core(info),
                command_line=self.command_line(name, core_path),
                existing=info.corename.casefold() in existing_retroarch or dll.casefold() in existing_retroarch,
            )
            if not any(o.core_dll == option.core_dll for o in system.options):
                system.options.append(option)
        for system in systems.values():
            self._select_default(system)
        return sorted(systems.values(), key=lambda s: (self.GROUP_ORDER.index(s.group), s.generation, s.name.casefold()))

    @staticmethod
    def _platform_key(name: str, platforms: dict[str, dict[str, str]]) -> str | None:
        """Encontra a plataforma local por nome exato, sem alterar seu nome."""
        return name.casefold() if name.casefold() in platforms else None

    @staticmethod
    def _existing_core_names(installation: LaunchBoxInstallation) -> set[str]:
        """Extrai cores RetroArch já configurados nas associações existentes."""
        result: set[str] = set()
        for emulator in installation.emulators.values():
            if emulator.get("Title", "").casefold() != "retroarch":
                continue
            result.update(value.casefold() for key, value in emulator.items() if key.casefold() == "core")
        try:
            tree = ET.parse(installation.emulators_xml)
            for element in tree.getroot().iter():
                tag = element.tag.rsplit("}", 1)[-1].casefold()
                if tag == "core" and element.text:
                    result.add(element.text.strip().casefold())
        except (OSError, ET.ParseError):
            pass
        return result

    def add_standalones(self, systems: list[LaunchBoxSystem], standalone: list[dict] | None = None) -> list[LaunchBoxSystem]:
        """Adiciona standalones usando os executáveis já descobertos no AppConfig."""
        executable_map = {"mame": self.config.mame_path, "flycast": self.config.flycast_path, "fbneo": self.config.fbneo_path, "supermodel": self.config.supermodel_path}
        for item in standalone or []:
            system_id = str(item.get("system_id", "")).casefold()
            if not system_id:
                continue
            target = next((s for s in systems if s.system_id == system_id), None)
            if target is None:
                group, generation = self.classify_system(system_id, item.get("name", system_id))
                target = LaunchBoxSystem(system_id, item.get("name", system_id), group, generation)
                systems.append(target)
            emulator = str(item.get("emulator", "mame")).casefold()
            executable = executable_map.get(emulator)
            target.options.append(LaunchBoxCoreOption(name=item.get("name", self._label(emulator)), emulator=emulator, executable=executable, score=int(item.get("score", 90)), command_line=self.standalone_command(emulator, item.get("command_line", "")), existing=False))
            self._select_default(target)
        return sorted(systems, key=lambda s: (self.GROUP_ORDER.index(s.group), s.generation, s.name.casefold()))

    @staticmethod
    def _label(emulator: str) -> str:
        return {"retroarch": "RetroArch", "mame": "MAME", "flycast": "Flycast", "fbneo": "FBNeo", "supermodel": "Supermodel"}.get(emulator, emulator)

    def classify_system(self, system_id: str, name: str) -> tuple[str, str]:
        """Classifica primeiro por regras externas e depois por fallback."""
        override = self.group_rules.get("system_overrides", {}).get(system_id, {})
        if override:
            return override.get("group", "consoles"), override.get("generation", "Outros")
        text = f"{system_id} {name}".casefold()
        if any(k in text for k in ("arcade", "naomi", "atomiswave", "mame", "fbneo", "model 2", "model 3")):
            return "arcade", "Outros"
        if any(k in text for k in ("game boy", "gameboy", "game gear", "lynx", "neo geo pocket", "wonderswan", "nintendo ds", "gba", "gamepark")):
            return "portables", "Outros"
        if any(k in text for k in ("apple ii", "amstrad", "commodore", "msx", "zx spectrum", "dos", "pc-98", "computer")):
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
        """Preserva um padrão existente; caso contrário escolhe o melhor score."""
        if not system.options:
            return
        existing_defaults = [o for o in system.options if o.existing and o.default]
        best = max(range(len(system.options)), key=lambda i: (system.options[i].score, system.options[i].name.casefold()))
        for option in system.options:
            option.default = False
        if existing_defaults:
            existing_defaults[0].default = True
        else:
            system.options[best].default = True

    def command_line(self, platform: str, core_path: Path | None) -> str:
        """Gera a linha RetroArch com caminho real do core."""
        template = self.rules.get("retroarch", {}).get("platform_overrides", {}).get(platform)
        if not template:
            template = self.rules.get("retroarch", {}).get("default", "-L \"{core_path}\"")
        return template.format(core_path=str(core_path) if core_path else "{core_path}", core_dll=core_path.name if core_path else "{core_dll}", platform=platform)

    def standalone_command(self, emulator: str, template: str = "") -> str:
        """Obtém command-line externo para standalone."""
        return template or self.rules.get("standalone", {}).get(emulator, {}).get("default", "")

    def export_emulators_xml(self, launchbox_dir: Path, systems: Iterable[LaunchBoxSystem], overwrite: bool = False) -> Path:
        """Faz merge não destrutivo de Emulators.xml, preservando configurações existentes."""
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
        retroarch_options = [o for s in systems for o in s.options if o.emulator == "retroarch"]
        if retroarch_options:
            emulator = self._find_emulator(root, "RetroArch")
            if emulator is None:
                emulator = self._create_emulator(root, "RetroArch", self.config.retroarch_path)
            for system in systems:
                for option in system.options:
                    if option.emulator == "retroarch" and not option.existing:
                        self._merge_association(emulator, system.name, option)
        standalone_by_emulator: dict[str, list[tuple[LaunchBoxSystem, LaunchBoxCoreOption]]] = {}
        for system in systems:
            for option in system.options:
                if option.emulator != "retroarch" and not option.existing:
                    standalone_by_emulator.setdefault(option.emulator, []).append((system, option))
        for emulator_name, entries in standalone_by_emulator.items():
            emulator = self._find_emulator(root, self._label(emulator_name))
            if emulator is None:
                emulator = self._create_emulator(root, self._label(emulator_name), entries[0][1].executable)
            for system, option in entries:
                self._merge_association(emulator, system.name, option)
        ET.indent(root, space="  ")
        tmp = target.with_name(target.name + ".tmp")
        tree.write(tmp, encoding="utf-8", xml_declaration=True)
        tmp.replace(target)
        return target

    @staticmethod
    def _find_emulator(root: ET.Element, title: str) -> ET.Element | None:
        """Localiza um emulador existente."""
        for emulator in root.iter():
            if emulator.tag.rsplit("}", 1)[-1].casefold() == "emulator" and emulator.findtext("Title", "").casefold() == title.casefold():
                return emulator
        return None

    @staticmethod
    def _create_emulator(root: ET.Element, title: str, executable: Path | None) -> ET.Element:
        """Cria apenas um novo emulador quando necessário."""
        emulator = ET.SubElement(root, "Emulator")
        ET.SubElement(emulator, "ApplicationPath").text = str(executable) if executable else ""
        ET.SubElement(emulator, "CommandLine").text = ""
        ET.SubElement(emulator, "DefaultPlatform").text = ""
        ET.SubElement(emulator, "ID").text = str(uuid.uuid4())
        ET.SubElement(emulator, "Title").text = title
        ET.SubElement(emulator, "AssociatedPlatforms")
        return emulator

    @staticmethod
    def _merge_association(emulator: ET.Element, platform: str, option: LaunchBoxCoreOption) -> None:
        """Insere uma associação ausente sem alterar outras associações."""
        container = emulator.find("AssociatedPlatforms")
        if container is None:
            container = ET.SubElement(emulator, "AssociatedPlatforms")
        for row in container:
            if row.findtext("Platform", "").casefold() == platform.casefold() and row.findtext("Core", "").casefold() == (option.core_dll or "").casefold():
                return
        target = ET.SubElement(container, "AssociatedPlatform")
        _set_child(target, "Platform", platform)
        _set_child(target, "Core", option.core_dll or "")
        _set_child(target, "DefaultCommandLine", option.command_line)
        _set_child(target, "DefaultEmulator", "true" if option.default else "false")


def _set_child(parent: ET.Element, name: str, value: str) -> None:
    """Atualiza/cria um elemento conhecido."""
    node = parent.find(name)
    if node is None:
        node = ET.SubElement(parent, name)
    node.text = value


__all__ = ["LaunchBoxIntegrationService", "LaunchBoxSystem", "LaunchBoxCoreOption", "LaunchBoxInstallation"]
