"""Catálogo LaunchBox + RetroArch sem perder plataformas ou associações."""
from __future__ import annotations

import json
import shutil
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from app.config.app_config import AppConfig
from app.core.services.retroarch_info_service import (
    RetroArchInfoCore,
    RetroArchInfoService,
)


@dataclass(slots=True)
class LaunchBoxCoreOption:
    """Core ou executável disponível para uma plataforma."""
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
        """Retorna Core ou .exe."""
        return "Core" if self.core_dll else ".exe"

    @property
    def key(self) -> str:
        """Identificador estável da opção."""
        return f"{self.emulator}:{self.core_dll or self.executable or self.name}".casefold()


@dataclass(slots=True)
class LaunchBoxSystem:
    """Plataforma individual que será apresentada ao LaunchBox."""
    system_id: str
    name: str
    group: str
    generation: str
    options: list[LaunchBoxCoreOption] = field(default_factory=list)
    existing: bool = True


@dataclass(slots=True)
class LaunchBoxInstallation:
    """Estado importado de uma instalação existente."""
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
    """Integra o catálogo RetroArch sem restringi-lo ao Platforms.xml.

    Regra de identidade:
      1. Se uma plataforma equivalente existe no LaunchBox, usa exatamente
         o nome dela.
      2. Se não existe, cria a plataforma usando o nome canônico conhecido.
      3. Se não há nome canônico conhecido, mantém o nome declarado pelo
         database/.info do RetroArch.
      4. Um core pode aparecer em várias plataformas.
      5. Apenas cores cujo DLL realmente existe no diretório configurado são
         exportados.
    """

    GROUP_ORDER = ("consoles", "portables", "computers", "arcade")

    # Aliases conhecidos do ecossistema LaunchBox/Libretro. A lista é
    # intencionalmente permissiva: ela serve para encontrar equivalentes,
    # nunca para eliminar plataformas.
    PLATFORM_ALIASES: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
        "nintendo entertainment system": ("Nintendo Entertainment System", "consoles", "8-bit", ("nes", "famicom", "nintendo - nes - famicom")),
        "nintendo famicom disk system": ("Nintendo Famicom Disk System", "consoles", "8-bit", ("fds", "famicom disk system", "nintendo - family computer disk system")),
        "super nintendo entertainment system": ("Super Nintendo Entertainment System", "consoles", "16-bit", ("snes", "super nes", "super famicom", "nintendo - snes - super famicom")),
        "nintendo 64": ("Nintendo 64", "consoles", "64-bit", ("n64", "nintendo - n64")),
        "nintendo 64dd": ("Nintendo 64DD", "consoles", "64-bit", ("64dd", "n64dd", "nintendo - nintendo 64dd")),
        "nintendo game boy": ("Nintendo Game Boy", "portables", "8-bit", ("game boy", "gameboy", "gb", "nintendo - game boy")),
        "nintendo game boy color": ("Nintendo Game Boy Color", "portables", "8-bit", ("game boy color", "gameboy color", "gbc", "nintendo - game boy color")),
        "nintendo game boy advance": ("Nintendo Game Boy Advance", "portables", "32-bit", ("gba", "game boy advance", "nintendo - game boy advance")),
        "nintendo ds": ("Nintendo DS", "portables", "32-bit", ("nds", "nintendo ds")),
        "nintendo gamecube": ("Nintendo GameCube", "consoles", "128-bit+", ("gamecube", "gc", "nintendo - gamecube")),
        "nintendo wii": ("Nintendo Wii", "consoles", "128-bit+", ("wii", "nintendo - wii")),
        "nintendo wii u": ("Nintendo Wii U", "consoles", "128-bit+", ("wiiu", "nintendo - wii u")),
        "nintendo switch": ("Nintendo Switch", "consoles", "128-bit+", ("switch", "nintendo - switch")),
        "nintendo satellaview": ("Nintendo Satellaview", "consoles", "16-bit", ("satellaview", "nintendo - satellaview")),
        "nintendo sufami": ("Nintendo Sufami", "consoles", "16-bit", ("sufami", "sufami turbo", "nintendo - sufami turbo")),
        "nintendo virtual boy": ("Nintendo Virtual Boy", "consoles", "32-bit", ("virtual boy", "vb", "nintendo - virtual boy")),
        "nintendo pokemon mini": ("Nintendo Pokemon Mini", "portables", "8-bit", ("pokemini", "pokemon mini")),
        "sega master system": ("Sega Master System", "consoles", "8-bit", ("master system", "sms", "mastersystem", "sega - master system")),
        "sega sg-1000": ("Sega SG-1000", "consoles", "8-bit", ("sg-1000", "sg1000", "sega - sg-1000")),
        "sega genesis": ("Sega Genesis", "consoles", "16-bit", ("genesis", "megadrive", "mega drive", "sega - mega drive - genesis")),
        "sega cd": ("Sega CD", "consoles", "16-bit", ("sega cd", "mega cd", "sega - mega cd - sega cd")),
        "sega 32x": ("Sega 32X", "consoles", "32-bit", ("32x", "sega - 32x")),
        "sega cd 32x": ("Sega CD 32X", "consoles", "32-bit", ("sega cd 32x", "32x cd", "sega - 32x cd")),
        "sega game gear": ("Sega Game Gear", "portables", "8-bit", ("game gear", "gamegear", "sega - game gear")),
        "sega saturn": ("Sega Saturn", "consoles", "32-bit", ("saturn", "sega - saturn")),
        "sega dreamcast": ("Sega Dreamcast", "consoles", "128-bit+", ("dreamcast", "sega - dreamcast")),
        "sega naomi": ("Sega Naomi", "arcade", "3D", ("naomi", "sega - naomi")),
        "sega naomi 2": ("Sega Naomi 2", "arcade", "3D", ("naomi2", "naomi 2", "sega - naomi 2")),
        "sammy atomiswave": ("Sammy Atomiswave", "arcade", "3D", ("atomiswave", "sammy atomiswave")),
        "sega system sp": ("SEGA System SP", "arcade", "3D", ("systemsp", "system sp", "sega system sp")),
        "sega model 2": ("Sega Model 2", "arcade", "3D", ("model2", "model 2", "sega model 2")),
        "sega model 3": ("Sega Model 3", "arcade", "3D", ("model3", "model 3", "sega model 3")),
        "neo geo aes": ("Neo Geo AES", "arcade", "16-bit", ("aes", "neo geo aes", "neogeo aes")),
        "arcade": ("Arcade", "arcade", "Outros", ("arcade", "mame", "fbneo")),
        "3do": ("3DO Interactive Multiplayer", "consoles", "32-bit", ("3do", "3do interactive multiplayer")),
        "atari 2600": ("Atari 2600", "consoles", "4-bit", ("atari2600", "2600", "atari - 2600")),
        "atari 5200": ("Atari 5200", "consoles", "8-bit", ("atari5200", "5200")),
        "atari 7800": ("Atari 7800", "consoles", "8-bit", ("atari7800", "7800")),
        "atari jaguar": ("Atari Jaguar", "consoles", "32-bit", ("jaguar", "atari - jaguar")),
        "atari jaguar cd": ("Atari Jaguar CD", "consoles", "32-bit", ("jaguar cd", "jaguarcd")),
        "atari lynx": ("Atari Lynx", "portables", "16-bit", ("lynx", "atari - lynx")),
        "colecovision": ("ColecoVision", "consoles", "8-bit", ("colecovision", "coleco - colecovision")),
        "commodore 64": ("Commodore 64", "computers", "8-bit", ("c64", "commodore - c64")),
        "commodore amiga": ("Commodore Amiga", "computers", "16-bit", ("amiga", "commodore - amiga")),
        "commodore amiga aga": ("Commodore Amiga AGA", "computers", "32-bit", ("amiga aga", "commodore - amiga aga")),
        "commodore amiga cd32": ("Commodore Amiga CD32", "consoles", "32-bit", ("cd32", "amiga cd32", "commodore - cd32")),
        "commodore cdtv": ("Commodore CDTV", "consoles", "16-bit", ("cdtv", "commodore - cdtv")),
        "microsoft msx": ("Microsoft MSX", "computers", "8-bit", ("msx", "microsoft - msx")),
        "microsoft msx2": ("Microsoft MSX2", "computers", "8-bit", ("msx2", "microsoft - msx2")),
        "sinclair zx spectrum": ("Sinclair ZX Spectrum", "computers", "8-bit", ("zx spectrum", "zxspectrum", "spectrum", "sinclair - zx spectrum")),
        "sharp x1": ("Sharp X1", "computers", "8-bit", ("x1", "sharp x1")),
        "sharp x68000": ("Sharp X68000", "computers", "16-bit", ("x68000", "sharp x68000")),
        "ms-dos": ("MS-DOS", "computers", "16-bit", ("dos", "msdos", "ms-dos")),
        "nec turbografx-16": ("NEC TurboGrafx-16", "consoles", "16-bit", ("pc engine", "pcengine", "turbografx-16", "turbografx16")),
        "nec turbografx-cd": ("NEC TurboGrafx-CD", "consoles", "16-bit", ("pc engine cd", "pcenginecd", "turbografx-cd", "turbografxcd")),
        "magnavox odyssey 2": ("Magnavox Odyssey 2", "consoles", "8-bit", ("odyssey2", "odyssey 2", "magnavox - odyssey2")),
        "philips videopac+": ("Philips Videopac+", "consoles", "8-bit", ("videopac+", "videopac", "philips - videopac+")),
        "snk neo geo cd": ("SNK Neo Geo CD", "consoles", "16-bit", ("neogeo cd", "neo geo cd")),
        "snk neo geo pocket": ("SNK Neo Geo Pocket", "portables", "16-bit", ("neo geo pocket", "neogeo pocket", "ngp")),
        "snk neo geo pocket color": ("SNK Neo Geo Pocket Color", "portables", "16-bit", ("neo geo pocket color", "neogeo pocket color", "ngpc")),
        "wonderswan": ("WonderSwan", "portables", "16-bit", ("wonderswan",)),
        "wonderswan color": ("WonderSwan Color", "portables", "16-bit", ("wonderswan color", "wonderswan_color")),
        "watara supervision": ("Watara Supervision", "portables", "8-bit", ("supervision", "watara supervision")),
        "sony playstation": ("Sony Playstation", "consoles", "32-bit", ("playstation", "psx", "ps1", "sony - playstation")),
        "sony playstation 2": ("Sony Playstation 2", "consoles", "128-bit+", ("playstation2", "ps2", "sony - playstation 2")),
        "sony playstation 3": ("Sony Playstation 3", "consoles", "128-bit+", ("playstation3", "ps3", "sony - playstation 3")),
        "windows": ("Windows", "computers", "64-bit", ("windows", "pc")),
    }

    CORE_PLATFORM_OVERRIDES = {
        "flycast": ("Sega Dreamcast", "Sega Naomi", "Sega Naomi 2", "Sammy Atomiswave", "SEGA System SP"),
        "picodrive": ("Sega Master System", "Sega Game Gear", "Sega Genesis", "Sega CD", "Sega 32X", "Sega CD 32X"),
        "puae": ("Commodore Amiga", "Commodore Amiga CD32", "Commodore CDTV"),
        "puae2021": ("Commodore Amiga", "Commodore Amiga CD32", "Commodore CDTV"),
        "o2em": ("Magnavox Odyssey 2", "Philips Videopac+"),
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
        """Inicializa o serviço."""
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.config = config or AppConfig()
        self.rules_path = self.project_root / "data" / "launchbox" / "command_lines.json"
        self.groups_path = self.project_root / "data" / "launchbox" / "system_groups.json"
        self.core_platform_path = self.project_root / "data" / "launchbox" / "core_platform_overrides.json"
        self.info_service = RetroArchInfoService()
        self.rules: dict = {}
        self.group_rules: dict = {}
        self.core_platform_overrides: dict[str, tuple[str, ...]] = {}
        self.reload_rules()

    @staticmethod
    def _load_json(path: Path) -> dict:
        """Carrega JSON externo sem interromper a aplicação."""
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {}

    def reload_rules(self) -> None:
        """Recarrega regras editáveis pelo usuário."""
        self.rules = self._load_json(self.rules_path)
        self.group_rules = self._load_json(self.groups_path)
        external = self._load_json(self.core_platform_path).get("retroarch", {})
        self.core_platform_overrides = {
            str(k).casefold(): tuple(str(v) for v in values)
            for k, values in external.items() if isinstance(values, list)
        }
        for core, platforms in self.CORE_PLATFORM_OVERRIDES.items():
            self.core_platform_overrides.setdefault(core.casefold(), platforms)

    def load_launchbox_installation(self, executable: Path) -> LaunchBoxInstallation:
        """Lê os XMLs existentes sem modificá-los."""
        executable = Path(executable).resolve()
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
        """Lê registros XML por nome."""
        tree = ET.parse(path)
        result: dict[str, dict[str, str]] = {}
        wanted = {x.casefold() for x in element_names}
        for element in tree.getroot().iter():
            if element.tag.rsplit("}", 1)[-1].casefold() not in wanted:
                continue
            fields = {child.tag.rsplit("}", 1)[-1]: (child.text or "").strip() for child in element if (child.text or "").strip()}
            name = next((fields.get(k) for k in name_fields if fields.get(k)), None)
            if name:
                result[name.casefold()] = fields
        return result

    @staticmethod
    def _read_emulator_platforms(path: Path) -> list[dict[str, str]]:
        """Lê todas as associações EmulatorPlatform."""
        tree = ET.parse(path)
        return [
            {child.tag.rsplit("}", 1)[-1]: (child.text or "").strip() for child in element}
            for element in tree.getroot().iter()
            if element.tag.rsplit("}", 1)[-1].casefold() == "emulatorplatform"
        ]

    @staticmethod
    def _read_default_associations(rows: list[dict[str, str]]) -> dict[str, str]:
        """Obtém o padrão existente por plataforma."""
        return {
            row.get("Platform", "").strip().casefold(): f"{row.get('Emulator', '')}:{row.get('Core', '')}".casefold()
            for row in rows
            if row.get("Platform", "").strip() and row.get("Default", "").casefold() in {"true", "1", "yes"}
        }

    @staticmethod
    def _key(value: str | None) -> str:
        """Normaliza nomes sem perder sua forma original para exibição."""
        return " ".join((value or "").replace("_", " ").replace("/", " ").split()).casefold()

    @classmethod
    def _canonical(cls, value: str | None) -> tuple[str, str, str] | None:
        """Resolve aliases para um nome conhecido."""
        key = cls._key(value)
        for name, group, generation, aliases in cls.PLATFORM_ALIASES.values():
            if key == cls._key(name) or key in {cls._key(a) for a in aliases}:
                return name, group, generation
        return None

    @classmethod
    def _existing_equivalent(cls, candidate: str, systems: dict[str, LaunchBoxSystem]) -> LaunchBoxSystem | None:
        """Encontra a plataforma LaunchBox equivalente, quando existir."""
        if cls._key(candidate) in systems:
            return systems[cls._key(candidate)]
        canonical = cls._canonical(candidate)
        if canonical and cls._key(canonical[0]) in systems:
            return systems[cls._key(canonical[0])]
        candidate_key = cls._key(candidate)
        for system in systems.values():
            if candidate_key == cls._key(system.name):
                return system
        return None

    def _targets(self, info: RetroArchInfoCore) -> tuple[str, ...]:
        """Obtém todas as plataformas suportadas, sem colapsá-las."""
        values: list[str] = []
        for raw in (info.system_name, info.system_id):
            if raw and raw.strip():
                values.append(raw.strip())
        values.extend(x.strip() for x in info.databases if x.strip())
        values.extend(self.core_platform_overrides.get(info.corename.casefold(), ()))
        result: list[str] = []
        for value in values:
            canonical = self._canonical(value)
            target = canonical[0] if canonical else value
            if self._key(target) not in {self._key(x) for x in result}:
                result.append(target)
        return tuple(result)

    @staticmethod
    def _excluded_core(info: RetroArchInfoCore) -> bool:
        """Exclui somente cores explicitamente identificados como teste."""
        text = " ".join((info.corename, info.display_name, info.system_name or "", info.system_id or "")).casefold()
        return "advanced test core" in text or "advanced_tests" in text

    def scan_retroarch(self, info_directory: Path) -> list[RetroArchInfoCore]:
        """Varre os arquivos .info locais."""
        return self.info_service.scan_directory(Path(info_directory))

    def _classify(self, system_id: str, name: str) -> tuple[str, str]:
        """Classifica sem alterar o nome da plataforma."""
        overrides = self.group_rule_overrides()
        for value in (name, system_id):
            override = overrides.get(value) or overrides.get(value.casefold())
            if override:
                return override.get("group", "consoles"), override.get("generation", "Outros")
        canonical = self._canonical(name) or self._canonical(system_id)
        if canonical:
            return canonical[1], canonical[2]
        text = f"{system_id} {name}".casefold()
        if any(x in text for x in ("arcade", "naomi", "atomiswave", "mame", "fbneo", "model2", "model 2", "model3", "model 3")):
            return "arcade", "Outros"
        if any(x in text for x in ("game boy", "gamegear", "game gear", "lynx", "neo geo pocket", "wonderswan", "nintendo ds", "gba", "psp", "vita", "pokemini")):
            return "portables", "Outros"
        if any(x in text for x in ("commodore", "amiga", "msx", "spectrum", "dos", "pc-98", "x68000", "computer", "windows", "sharp x1")):
            return "computers", "Outros"
        return "consoles", "Outros"

    def group_rule_overrides(self) -> dict:
        """Retorna overrides externos de agrupamento."""
        return self.group_rules.get("system_overrides", {}) or {}

    def _score(self, info: RetroArchInfoCore) -> int:
        """Calcula preferência inicial sem eliminar alternativas."""
        text = f"{info.corename} {info.display_name}".casefold()
        score = 50
        if any(x in text for x in ("accuracy", "beetle", "bsnes", "mesen")):
            score += 20
        if "retroachievement" in text:
            score += 10
        if any(x in text for x in ("vulkan", "hardware")):
            score += 5
        return score

    @staticmethod
    def _select_default(system: LaunchBoxSystem) -> None:
        """Mantém exatamente um padrão por plataforma."""
        if not system.options:
            return
        selected = next((o for o in system.options if o.default), None)
        if selected is None:
            selected = max(system.options, key=lambda o: (o.score, o.name.casefold()))
        for option in system.options:
            option.default = option is selected

    def build_systems(self, infos: Iterable[RetroArchInfoCore], installation: LaunchBoxInstallation | None = None) -> list[LaunchBoxSystem]:
        """Reconstrói o catálogo completo sem limitar-se às plataformas existentes."""
        systems: dict[str, LaunchBoxSystem] = {}
        defaults = installation.default_options if installation else {}
        core_root = self.config.get_emulator_path("retroarch", "cores")
        retroarch_exe = self.config.retroarch_path

        # 1. Preserva TODAS as plataformas já cadastradas no LaunchBox.
        if installation:
            for raw_key, fields in installation.platforms.items():
                name = fields.get("Name") or fields.get("Title") or raw_key
                group, generation = self._classify(raw_key, name)
                systems[self._key(name)] = LaunchBoxSystem(self._key(name), name, group, generation, existing=True)

        # 2. Adiciona plataformas do catálogo RetroArch que não existem no LB.
        for info in infos:
            if self._excluded_core(info):
                continue
            dll = f"{info.corename}_libretro.dll"
            core_path = Path(core_root) / dll if core_root else None
            # Um .info sem DLL instalada não deve virar opção exportável.
            if core_path is not None and not core_path.is_file():
                continue
            targets = self._targets(info)
            for target in targets:
                platform = self._existing_equivalent(target, systems)
                if platform is None:
                    canonical = self._canonical(target)
                    name = canonical[0] if canonical else target
                    group, generation = self._classify(info.system_id or info.corename, name)
                    platform = LaunchBoxSystem(self._key(name), name, group, generation, existing=False)
                    systems[platform.system_id] = platform

                option = LaunchBoxCoreOption(
                    name=info.display_name or info.corename,
                    emulator="retroarch",
                    core_dll=dll,
                    core_path=core_path.resolve() if core_path else None,
                    executable=retroarch_exe,
                    score=self._score(info),
                    command_line=self.command_line(platform.name, core_path),
                    existing=self._core_is_existing(installation, dll, platform.name),
                )
                default_key = defaults.get(platform.name.casefold(), "")
                if default_key.endswith(f":{dll}".casefold()):
                    option.default = True
                if not any(self._option_identity(x) == self._option_identity(option) for x in platform.options):
                    platform.options.append(option)

        for system in systems.values():
            system.options = self._deduplicate(system.options)
            self._select_default(system)
        return sorted(systems.values(), key=lambda s: (self.GROUP_ORDER.index(s.group) if s.group in self.GROUP_ORDER else 9, s.generation.casefold(), s.name.casefold()))

    @classmethod
    def _option_identity(cls, option: LaunchBoxCoreOption) -> tuple[str, str, str]:
        """Identidade única de uma opção."""
        target = option.core_dll or (option.executable.as_posix() if option.executable else option.name)
        return cls._key(option.emulator), cls._key(option.name), cls._key(target)

    @classmethod
    def _deduplicate(cls, options: Iterable[LaunchBoxCoreOption]) -> list[LaunchBoxCoreOption]:
        """Remove apenas duplicações reais do mesmo core/emulador."""
        result: list[LaunchBoxCoreOption] = []
        seen: set[tuple[str, str, str]] = set()
        for option in options:
            identity = cls._option_identity(option)
            if identity not in seen:
                seen.add(identity)
                result.append(option)
        return result

    @staticmethod
    def _core_is_existing(installation: LaunchBoxInstallation | None, dll: str, platform: str) -> bool:
        """Verifica associação existente no XML."""
        return bool(installation and any(
            row.get("Platform", "").casefold() == platform.casefold() and row.get("Core", "").casefold() == dll.casefold()
            for row in installation.emulator_platforms
        ))

    @staticmethod
    def _label(emulator: str) -> str:
        """Nome do emulador no LaunchBox."""
        return {"retroarch": "RetroArch", "mame": "MAME", "flycast": "Flycast", "fbneo": "FBNeo", "supermodel": "Supermodel"}.get(emulator, emulator)

    def add_standalones(self, systems: list[LaunchBoxSystem], standalone: list[dict] | None = None) -> list[LaunchBoxSystem]:
        """Adiciona os standalones sem exigir que a plataforma já exista."""
        executable_map = {"mame": self.config.mame_path, "flycast": self.config.flycast_path, "fbneo": self.config.fbneo_path, "supermodel": self.config.supermodel_path}
        requested = list(standalone or []) + list(self.MANDATORY_STANDALONES)
        for item in requested:
            emulator = str(item.get("emulator", "mame")).casefold()
            system_id = str(item.get("system_id", "")).strip()
            target_name = item.get("platform") or (self._canonical(system_id)[0] if self._canonical(system_id) else item.get("name") or system_id)
            if not target_name:
                continue
            target = next((s for s in systems if self._key(s.name) == self._key(target_name)), None)
            if target is None:
                canonical = self._canonical(str(target_name))
                name = canonical[0] if canonical else str(target_name)
                group, generation = self._classify(system_id, name)
                target = LaunchBoxSystem(self._key(name), name, group, generation, existing=False)
                systems.append(target)
            exe = executable_map.get(emulator)
            if exe is not None and not Path(exe).is_file():
                continue
            option = LaunchBoxCoreOption(name=item.get("name", self._label(emulator)), emulator=emulator, executable=exe, score=int(item.get("score", 90)), command_line=self.standalone_command(emulator, item.get("command_line", "")))
            if not any(o.key == option.key for o in target.options):
                target.options.append(option)
            self._select_default(target)
        return sorted(systems, key=lambda s: (self.GROUP_ORDER.index(s.group) if s.group in self.GROUP_ORDER else 9, s.generation.casefold(), s.name.casefold()))

    def set_default_option(self, system: LaunchBoxSystem, option: LaunchBoxCoreOption) -> None:
        """Define manualmente um único padrão."""
        if option not in system.options:
            raise ValueError("A opção não pertence ao sistema selecionado.")
        for candidate in system.options:
            candidate.default = candidate is option

    def command_line(self, platform: str, core_path: Path | None) -> str:
        """Obtém o command line externo configurado para o core."""
        template = self.rules.get("retroarch", {}).get("platform_overrides", {}).get(platform) or self.rules.get("retroarch", {}).get("default", "-L \"cores/{core_dll}\"")
        return template.format(core_path=str(core_path) if core_path else "{core_path}", core_dll=core_path.name if core_path else "{core_dll}", platform=platform)

    def standalone_command(self, emulator: str, template: str = "") -> str:
        """Obtém command line de standalone."""
        return template or self.rules.get("standalone", {}).get(emulator, {}).get("default", "")

    def export_emulators_xml(self, launchbox_dir: Path, systems: Iterable[LaunchBoxSystem], overwrite: bool = False) -> Path:
        """Faz merge no Emulators.xml existente, sem apagar configurações."""
        data_dir = Path(launchbox_dir) / "Data"
        if not data_dir.is_dir():
            raise FileNotFoundError(f"Pasta Data não encontrada: {data_dir}")
        target = data_dir / "Emulators.xml"
        if target.exists():
            tree = ET.parse(target)
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
        """Localiza o registro Emulator existente."""
        return next((e for e in root if e.tag.rsplit("}", 1)[-1].casefold() == "emulator" and e.findtext("Title", "").casefold() == title.casefold()), None)

    @staticmethod
    def _create_emulator(root: ET.Element, title: str, executable: Path | None) -> ET.Element:
        """Cria um Emulator apenas quando ele não existe."""
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
        """Retorna ID do emulador."""
        return emulator.findtext("ID", "").strip()

    @staticmethod
    def _merge_emulator_platform(root: ET.Element, emulator: ET.Element, platform: str, option: LaunchBoxCoreOption) -> None:
        """Insere/atualiza somente a associação específica."""
        emulator_id = LaunchBoxIntegrationService._emulator_id(emulator)
        if not emulator_id:
            emulator_id = str(uuid.uuid4())
            _set_child(emulator, "ID", emulator_id)
        target = next((row for row in root if row.tag.rsplit("}", 1)[-1].casefold() == "emulatorplatform" and row.findtext("Emulator", "").casefold() == emulator_id.casefold() and row.findtext("Platform", "").casefold() == platform.casefold() and row.findtext("Core", "").casefold() == (option.core_dll or "").casefold()), None)
        if target is None:
            target = ET.Element("EmulatorPlatform")
            _set_child(target, "Emulator", emulator_id)
            _set_child(target, "Platform", platform)
            root.append(target)
        _set_child(target, "CommandLine", option.command_line)
        _set_child(target, "Default", "true" if option.default else "false")
        if option.core_dll:
            _set_child(target, "Core", option.core_dll)

    @staticmethod
    def _normalize_defaults(root: ET.Element, system: LaunchBoxSystem) -> None:
        """Garante apenas um Default=true por plataforma entre opções gerenciadas."""
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
    """Atualiza ou cria elemento XML sem remover os demais."""
    node = parent.find(name)
    if node is None:
        node = ET.SubElement(parent, name)
    node.text = value


__all__ = ["LaunchBoxCoreOption", "LaunchBoxInstallation", "LaunchBoxIntegrationService", "LaunchBoxSystem"]
