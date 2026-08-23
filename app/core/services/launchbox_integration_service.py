"""Integração segura com LaunchBox: catálogo, caminhos reais e merge XML."""
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


@dataclass(slots=True)
class LaunchBoxSystem:
    """Sistema agrupado em uma geração e grupo de hardware."""
    system_id: str
    name: str
    group: str
    generation: str
    options: list[LaunchBoxCoreOption] = field(default_factory=list)


class LaunchBoxIntegrationService:
    """Constrói o catálogo e altera LaunchBox somente por merge seletivo."""

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

    def scan_retroarch(self, info_directory: Path) -> list[RetroArchInfoCore]:
        """Lê os .info locais do RetroArch."""
        return self.info_service.scan_directory(Path(info_directory))

    def build_systems(self, infos: Iterable[RetroArchInfoCore]) -> list[LaunchBoxSystem]:
        """Agrupa sistemas e mapeia cores usando o diretório real de cores."""
        systems: dict[str, LaunchBoxSystem] = {}
        core_root = self.config.get_emulator_path("retroarch", "cores")
        retroarch_exe = self.config.retroarch_path
        for info in infos:
            system_id = (info.system_id or info.corename).casefold()
            group, generation = self.classify_system(system_id, info.system_name or info.display_name)
            system = systems.setdefault(
                system_id,
                LaunchBoxSystem(system_id, info.system_name or info.display_name or info.corename, group, generation),
            )
            dll = f"{info.corename}_libretro.dll"
            core_path = (Path(core_root) / dll).resolve() if core_root else None
            score = self._score_core(info)
            option = LaunchBoxCoreOption(
                name=info.display_name or info.corename,
                emulator="retroarch",
                core_dll=dll,
                core_path=core_path,
                executable=retroarch_exe,
                score=score,
                command_line=self.command_line(info.system_name or info.display_name or info.corename, core_path),
            )
            if not any(o.core_dll == option.core_dll for o in system.options):
                system.options.append(option)
        for system in systems.values():
            self._select_default(system)
        return sorted(systems.values(), key=lambda s: (self.GROUP_ORDER.index(s.group), s.generation, s.name.casefold()))

    def add_standalones(self, systems: list[LaunchBoxSystem], standalone: list[dict] | None = None) -> list[LaunchBoxSystem]:
        """Adiciona standalones usando os executáveis já descobertos no AppConfig."""
        executable_map = {
            "mame": self.config.mame_path,
            "flycast": self.config.flycast_path,
            "fbneo": self.config.fbneo_path,
            "supermodel": self.config.supermodel_path,
        }
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
            target.options.append(LaunchBoxCoreOption(
                name=item.get("name", self._label(emulator)),
                emulator=emulator,
                executable=executable,
                score=int(item.get("score", 90)),
                command_line=self.standalone_command(emulator, item.get("command_line", "")),
            ))
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
        """Garante exatamente uma opção padrão quando existem opções."""
        if not system.options:
            return
        best = max(range(len(system.options)), key=lambda i: (system.options[i].score, system.options[i].name.casefold()))
        for i, option in enumerate(system.options):
            option.default = i == best

    def command_line(self, platform: str, core_path: Path | None) -> str:
        """Gera a linha RetroArch com caminho real do core, sem assumir pasta fixa."""
        template = self.rules.get("retroarch", {}).get("platform_overrides", {}).get(platform)
        if not template:
            template = self.rules.get("retroarch", {}).get("default", "-L \"{core_path}\"")
        return template.format(core_path=str(core_path) if core_path else "{core_path}", core_dll=core_path.name if core_path else "{core_dll}", platform=platform)

    def standalone_command(self, emulator: str, template: str = "") -> str:
        """Obtém command-line externo para standalone."""
        return template or self.rules.get("standalone", {}).get(emulator, {}).get("default", "")

    def export_emulators_xml(self, launchbox_dir: Path, systems: Iterable[LaunchBoxSystem], overwrite: bool = False) -> Path:
        """Faz merge não destrutivo de Emulators.xml, preservando tudo que já existe."""
        data_dir = Path(launchbox_dir) / "Data"
        data_dir.mkdir(parents=True, exist_ok=True)
        target = data_dir / "Emulators.xml"
        if target.exists():
            try:
                tree = ET.parse(target)
            except ET.ParseError as exc:
                raise ValueError(f"Emulators.xml inválido; nenhuma alteração foi feita: {exc}") from exc
            root = tree.getroot()
            backup = target.with_name(target.name + ".arcademanager.bak")
            shutil.copy2(target, backup)
        else:
            root = ET.Element("LaunchBox")
            tree = ET.ElementTree(root)

        retroarch_options = [o for s in systems for o in s.options if o.emulator == "retroarch"]
        if retroarch_options:
            emulator = self._find_emulator(root, "RetroArch")
            if emulator is None:
                emulator = self._create_emulator(root, "RetroArch", self.config.retroarch_path)
            else:
                self._patch_application_path(emulator, self.config.retroarch_path)
            for system in systems:
                for option in system.options:
                    if option.emulator == "retroarch":
                        self._merge_association(emulator, system.name, option)

        standalone_by_emulator: dict[str, list[tuple[LaunchBoxSystem, LaunchBoxCoreOption]]] = {}
        for system in systems:
            for option in system.options:
                if option.emulator != "retroarch":
                    standalone_by_emulator.setdefault(option.emulator, []).append((system, option))
        for emulator_name, entries in standalone_by_emulator.items():
            emulator = self._find_emulator(root, self._label(emulator_name))
            exe = entries[0][1].executable
            if emulator is None:
                emulator = self._create_emulator(root, self._label(emulator_name), exe)
            else:
                self._patch_application_path(emulator, exe)
            for system, option in entries:
                self._merge_association(emulator, system.name, option)

        ET.indent(root, space="  ")
        tmp = target.with_name(target.name + ".tmp")
        tree.write(tmp, encoding="utf-8", xml_declaration=True)
        tmp.replace(target)
        return target

    @staticmethod
    def _find_emulator(root: ET.Element, title: str) -> ET.Element | None:
        """Localiza um emulador existente sem depender da ordem do XML."""
        for emulator in root.findall("Emulator"):
            if emulator.findtext("Title", "").casefold() == title.casefold():
                return emulator
        return None

    @staticmethod
    def _patch_application_path(emulator: ET.Element, executable: Path | None) -> None:
        """Atualiza ApplicationPath somente quando o executável real foi descoberto."""
        if executable is None:
            return
        node = emulator.find("ApplicationPath")
        if node is None:
            node = ET.SubElement(emulator, "ApplicationPath")
        node.text = str(executable)

    @staticmethod
    def _create_emulator(root: ET.Element, title: str, executable: Path | None) -> ET.Element:
        """Cria somente um novo bloco quando o LaunchBox ainda não o possui."""
        emulator = ET.SubElement(root, "Emulator")
        ET.SubElement(emulator, "ApplicationPath").text = str(executable) if executable else ""
        ET.SubElement(emulator, "CommandLine").text = ""
        ET.SubElement(emulator, "DefaultPlatform").text = ""
        ET.SubElement(emulator, "ID").text = str(uuid.uuid4())
        ET.SubElement(emulator, "Title").text = title
        ET.SubElement(emulator, "NoQuotes").text = "false"
        ET.SubElement(emulator, "NoSpace").text = "false"
        ET.SubElement(emulator, "HideConsole").text = "true"
        ET.SubElement(emulator, "FileNameWithoutExtensionAndPath").text = "false"
        ET.SubElement(emulator, "AutoExtract").text = "false"
        ET.SubElement(emulator, "AssociatedPlatforms")
        return emulator

    @staticmethod
    def _merge_association(emulator: ET.Element, platform: str, option: LaunchBoxCoreOption) -> None:
        """Insere ou atualiza somente a associação correspondente, preservando as demais."""
        container = emulator.find("AssociatedPlatforms")
        if container is None:
            container = ET.SubElement(emulator, "AssociatedPlatforms")
        target = None
        for row in container.findall("AssociatedPlatform"):
            if row.findtext("Platform", "").casefold() == platform.casefold() and row.findtext("Core", "").casefold() == (option.core_dll or "").casefold():
                target = row
                break
        if target is None:
            target = ET.SubElement(container, "AssociatedPlatform")
        _set_child(target, "Platform", platform)
        _set_child(target, "Core", option.core_dll or "")
        _set_child(target, "DefaultCommandLine", option.command_line)
        _set_child(target, "DefaultEmulator", "true" if option.default else "false")


def _set_child(parent: ET.Element, name: str, value: str) -> None:
    """Atualiza/cria somente um elemento conhecido, sem remover nós desconhecidos."""
    node = parent.find(name)
    if node is None:
        node = ET.SubElement(parent, name)
    node.text = value


__all__ = ["LaunchBoxIntegrationService", "LaunchBoxSystem", "LaunchBoxCoreOption"]
