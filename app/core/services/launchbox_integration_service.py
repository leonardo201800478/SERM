"""Integração LaunchBox: mapeamento de sistemas, cores e exportação XML."""
from __future__ import annotations

import json
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from app.core.services.retroarch_info_service import RetroArchInfoCore, RetroArchInfoService


@dataclass(slots=True)
class LaunchBoxCoreOption:
    """Core/emulador disponível para um sistema LaunchBox."""
    name: str
    emulator: str
    core_dll: str | None = None
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
    """Constrói o catálogo LaunchBox a partir dos .info e regras externas."""

    GROUP_ORDER = ("consoles", "portables", "computers", "arcade")
    EMULATOR_LABELS = {
        "retroarch": "RetroArch",
        "mame": "MAME",
        "flycast": "Flycast",
        "fbneo": "FBNeo",
        "supermodel": "Supermodel",
    }

    def __init__(self, project_root: Path | None = None) -> None:
        """Inicializa o serviço usando regras editáveis no diretório data."""
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.rules_path = self.project_root / "data" / "launchbox" / "command_lines.json"
        self.groups_path = self.project_root / "data" / "launchbox" / "system_groups.json"
        self.info_service = RetroArchInfoService()
        self.rules = self._load_json(self.rules_path)
        self.group_rules = self._load_json(self.groups_path)

    @staticmethod
    def _load_json(path: Path) -> dict:
        """Carrega JSON de regras sem impedir a aplicação de iniciar."""
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}

    def reload_rules(self) -> None:
        """Recarrega regras externas sem reiniciar o ARCADE MANAGER."""
        self.rules = self._load_json(self.rules_path)
        self.group_rules = self._load_json(self.groups_path)

    def scan_retroarch(self, info_directory: Path) -> list[RetroArchInfoCore]:
        """Lê todos os .info locais, mantendo-os como fonte primária."""
        return self.info_service.scan_directory(Path(info_directory))

    def build_systems(self, infos: Iterable[RetroArchInfoCore]) -> list[LaunchBoxSystem]:
        """Agrupa sistemas e mapeia todos os cores disponíveis."""
        systems: dict[str, LaunchBoxSystem] = {}
        for info in infos:
            system_id = (info.system_id or info.corename).casefold()
            group, generation = self.classify_system(system_id, info.system_name or info.display_name)
            system = systems.setdefault(
                system_id,
                LaunchBoxSystem(system_id, info.system_name or info.display_name or info.corename, group, generation),
            )
            dll = f"{info.corename}_libretro.dll"
            score = self._score_core(info)
            option = LaunchBoxCoreOption(
                name=info.display_name or info.corename,
                emulator="retroarch",
                core_dll=dll,
                score=score,
                command_line=self.command_line(info.system_name or info.display_name or info.corename, dll),
            )
            if not any(o.core_dll == option.core_dll for o in system.options):
                system.options.append(option)
        for system in systems.values():
            self._select_default(system)
        return sorted(systems.values(), key=lambda s: (self.GROUP_ORDER.index(s.group), s.generation, s.name.casefold()))

    def add_standalones(self, systems: list[LaunchBoxSystem], standalone: dict[str, list[dict]] | None = None) -> list[LaunchBoxSystem]:
        """Adiciona emuladores standalone já descobertos pelo projeto."""
        for item in standalone or []:
            system_id = str(item.get("system_id", "")).casefold()
            if not system_id:
                continue
            target = next((s for s in systems if s.system_id == system_id), None)
            if target is None:
                group, generation = self.classify_system(system_id, item.get("name", system_id))
                target = LaunchBoxSystem(system_id, item.get("name", system_id), group, generation)
                systems.append(target)
            target.options.append(LaunchBoxCoreOption(
                name=item.get("name", "Standalone"),
                emulator=item.get("emulator", "mame"),
                core_dll=None,
                score=int(item.get("score", 90)),
                command_line=self.standalone_command(item.get("emulator", "mame"), item.get("command_line", "")),
            ))
            self._select_default(target)
        return sorted(systems, key=lambda s: (self.GROUP_ORDER.index(s.group), s.generation, s.name.casefold()))

    def classify_system(self, system_id: str, name: str) -> tuple[str, str]:
        """Classifica por regras externas, com fallback sem depender do código."""
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
        """Calcula uma preferência inicial reproduzível, editável futuramente."""
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
        """Garante exatamente um favorito quando houver opções."""
        if not system.options:
            return
        best = max(enumerate(system.options), key=lambda pair: (pair[1].score, pair[1].name.casefold()))[0]
        for index, option in enumerate(system.options):
            option.default = index == best

    def command_line(self, platform: str, core_dll: str) -> str:
        """Gera parâmetros RetroArch conforme regras externas e placeholders."""
        overrides = self.rules.get("retroarch", {}).get("platform_overrides", {})
        template = overrides.get(platform) or self.rules.get("retroarch", {}).get("default", "-L \"cores/{core_dll}\"")
        return template.format(core_dll=core_dll, platform=platform)

    def standalone_command(self, emulator: str, template: str = "") -> str:
        """Obtém comando standalone do arquivo externo de regras."""
        return template or self.rules.get("standalone", {}).get(emulator, {}).get("default", "")

    def export_emulators_xml(self, launchbox_dir: Path, systems: Iterable[LaunchBoxSystem], overwrite: bool = False) -> Path:
        """Exporta um conjunto de emuladores para Data/Emulators.xml preservando entradas existentes."""
        data_dir = Path(launchbox_dir) / "Data"
        data_dir.mkdir(parents=True, exist_ok=True)
        target = data_dir / "Emulators.xml"
        if target.exists() and not overwrite:
            backup = target.with_suffix(".xml.arcademanager.bak")
            if not backup.exists():
                backup.write_bytes(target.read_bytes())
        if target.exists():
            try:
                root = ET.parse(target).getroot()
            except ET.ParseError:
                root = ET.Element("LaunchBox")
        else:
            root = ET.Element("LaunchBox")

        retroarch = self._ensure_emulator(root, "RetroArch", launchbox_dir)
        seen = set()
        for system in systems:
            for option in system.options:
                key = (system.name, option.emulator, option.core_dll)
                if key in seen:
                    continue
                seen.add(key)
                self._ensure_association(retroarch, system.name, option)
        ET.indent(root, space="  ")
        ET.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)
        return target

    @staticmethod
    def _ensure_emulator(root: ET.Element, title: str, launchbox_dir: Path) -> ET.Element:
        """Cria ou localiza o bloco do RetroArch."""
        for emulator in root.findall("Emulator"):
            if emulator.findtext("Title") == title:
                return emulator
        emulator = ET.SubElement(root, "Emulator")
        ET.SubElement(emulator, "ApplicationPath").text = "Emulators\\RetroArch\\retroarch.exe"
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
    def _ensure_association(emulator: ET.Element, platform: str, option: LaunchBoxCoreOption) -> None:
        """Adiciona uma associação LaunchBox sem duplicar plataforma/core."""
        container = emulator.find("AssociatedPlatforms")
        if container is None:
            container = ET.SubElement(emulator, "AssociatedPlatforms")
        for row in container.findall("AssociatedPlatform"):
            if row.findtext("Platform") == platform and row.findtext("Core") == (option.core_dll or ""):
                return
        row = ET.SubElement(container, "AssociatedPlatform")
        ET.SubElement(row, "Platform").text = platform
        ET.SubElement(row, "Core").text = option.core_dll or ""
        ET.SubElement(row, "DefaultCommandLine").text = option.command_line
        ET.SubElement(row, "DefaultEmulator").text = "true" if option.default else "false"


__all__ = ["LaunchBoxIntegrationService", "LaunchBoxSystem", "LaunchBoxCoreOption"]
