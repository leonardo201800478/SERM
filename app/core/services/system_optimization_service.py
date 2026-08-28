"""Serviço de otimização visual por sistema para RetroArch.

Arquitetura:
    Sistema
    ├── Core       -> cores suportados/preferidos
    ├── Override   -> configuração específica de cada core
    ├── Shader     -> preset Slang do sistema, compartilhado pelos cores
    └── Overlay    -> bezel/moldura externa, independente da proporção do jogo

A biblioteca de shaders aceita presets oficiais e de terceiros instalados
localmente. Por segurança, somente presets leves/médios, sem reflexos e sem
overlay embutido são elegíveis como padrão automático.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config.app_config import AppConfig

MANAGED_HEADER = "# ARCADE-MANAGER: system-optimization"
DEFAULT_SHADER_ID = "libretro-crt-guest-advanced-ntsc"


@dataclass(frozen=True, slots=True)
class CoreOptimization:
    """Configuração específica de um core para um sistema."""

    core: str
    files: dict[str, str]
    targets: dict[str, str] = field(default_factory=dict)
    preferred: bool = False


@dataclass(frozen=True, slots=True)
class ShaderProfile:
    """Metadados de um shader/preset instalável localmente."""

    shader_id: str
    name: str
    filename: str
    reference: str
    source: str
    source_url: str
    performance: str = "light"
    reflection: bool = False
    embedded_overlay: bool = False
    recommended: bool = False
    systems: tuple[str, ...] = ()
    notes: str = ""

    @property
    def safe_default(self) -> bool:
        """Indica se o shader pode ser usado automaticamente."""
        return (
            self.performance in {"light", "medium"}
            and not self.reflection
            and not self.embedded_overlay
        )


@dataclass(frozen=True, slots=True)
class ShaderOptimization:
    """Preset Slang do sistema gerado pelo Arcade Manager."""

    filename: str
    reference: str
    shader_id: str = DEFAULT_SHADER_ID

    @property
    def content(self) -> str:
        """Gera um Simple Preset Slang com uma única referência."""
        return (
            "; Arcade Manager — System Shader Preset\n"
            "; A proporção do sistema NÃO é definida pelo shader.\n"
            f"; Shader profile: {self.shader_id}\n"
            f'#reference "{self.reference}"\n'
        )


# Compatibilidade com consumidores que usavam este nome.
ShaderOptimizationProfile = ShaderProfile


@dataclass(frozen=True, slots=True)
class SystemOptimizationProfile:
    """Perfil completo: Core + Override + Shader + Overlay."""

    profile_id: str
    name: str
    description: str
    systems: tuple[str, ...]
    cores: tuple[str, ...]
    core_optimizations: dict[str, CoreOptimization]
    shader: ShaderOptimization | None = None
    overlay_asset: str | None = None
    shader_options: tuple[str, ...] = ()

    @property
    def core(self) -> str:
        """Retorna o core preferido ou o primeiro core."""
        preferred = next(
            (name for name, item in self.core_optimizations.items() if item.preferred),
            None,
        )
        return preferred or (self.cores[0] if self.cores else "")

    @property
    def files(self) -> dict[str, str]:
        """Arquivos do core preferido para compatibilidade legada."""
        item = self.core_optimizations.get(self.core)
        return dict(item.files) if item else {}

    @property
    def targets(self) -> dict[str, str]:
        """Destinos do core preferido para compatibilidade legada."""
        item = self.core_optimizations.get(self.core)
        return dict(item.targets) if item else {}


class SystemOptimizationService:
    """Carrega, valida, aplica e remove perfis RetroArch."""

    OVERLAY_CANDIDATES: dict[str, str] = {
        "sega-sg1000-fidelity-v1": "Sega-SG-1000-Bezel-16x9-2560x1440.cfg",
        "nes-fidelity-v1": "Nintendo-Entertainment-System-Bezel-16x9-2560x1440.cfg",
        "snes-fidelity-v1": "Super-Nintendo-Entertainment-System-Bezel-16x9-2560x1440.cfg",
        "master-system-fidelity-v1": "Sega-Master-System-Bezel-16x9-2560x1440.cfg",
        "mega-drive-fidelity-v1": "Sega-Genesis-16bit-Bezel-16x9-2560x1440.cfg",
        "playstation-fidelity-v1": "Sony-Playstation-Bezel-16x9-2560x1440.cfg",
        "sega-saturn-fidelity-v1": "Sega-Saturn-Bezel-16x9-2560x1440.cfg",
        "nintendo-64-fidelity-v1": "Nintendo-64-Bezel-16x9-2560x1440.cfg",
    }

    def __init__(self, project_root: Path | None = None, config: AppConfig | None = None) -> None:
        """Inicializa o serviço e carrega os catálogos."""
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.config = config or AppConfig()
        self.catalog_path = self.project_root / "data" / "launchbox" / "system_optimizations.json"
        self.shader_catalog_path = self.project_root / "data" / "launchbox" / "shader_library.json"
        self.profiles: dict[str, SystemOptimizationProfile] = {}
        self.shader_library: dict[str, ShaderProfile] = {}
        self.reload()

    @staticmethod
    def _key(value: str | None) -> str:
        """Normaliza nomes para comparação."""
        return " ".join((value or "").replace("_", " ").replace("-", " ").split()).casefold()

    @staticmethod
    def _managed_content(content: str) -> str:
        """Marca um arquivo como gerenciado pelo Arcade Manager."""
        if content.startswith(MANAGED_HEADER):
            return content.rstrip() + "\n"
        return f"{MANAGED_HEADER}\n{content.rstrip()}\n"

    @staticmethod
    def _is_managed(path: Path) -> bool:
        """Verifica se o primeiro comentário identifica o Arcade Manager."""
        if not path.is_file():
            return False
        try:
            first = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()[:1]
        except OSError:
            return False
        return bool(first) and first[0].strip() == MANAGED_HEADER

    def reload(self) -> None:
        """Recarrega os catálogos de sistemas e shaders."""
        self.profiles = {}
        self.shader_library = {}
        self._load_shader_library()
        self._load_profiles()

    def _load_shader_library(self) -> None:
        """Carrega a biblioteca de shaders e seus metadados de desempenho."""
        try:
            raw = json.loads(self.shader_catalog_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return
        for item in raw.get("shaders", []) if isinstance(raw, dict) else []:
            if not isinstance(item, dict):
                continue
            shader_id = str(item.get("id", "")).strip()
            filename = str(item.get("filename", "")).strip()
            reference = str(item.get("reference", "")).strip()
            if not shader_id or not filename or not reference:
                continue
            self.shader_library[shader_id] = ShaderProfile(
                shader_id=shader_id,
                name=str(item.get("name", shader_id)),
                filename=filename,
                reference=reference,
                source=str(item.get("source", "libretro")),
                source_url=str(item.get("source_url", "")),
                performance=str(item.get("performance", "light")),
                reflection=bool(item.get("reflection", False)),
                embedded_overlay=bool(item.get("embedded_overlay", False)),
                recommended=bool(item.get("recommended", False)),
                systems=tuple(str(v) for v in item.get("systems", [])),
                notes=str(item.get("notes", "")),
            )

    def _load_profiles(self) -> None:
        """Carrega os perfis mantendo compatibilidade com schemas anteriores."""
        try:
            raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            raw = {}
        for item in raw.get("profiles", []) if isinstance(raw, dict) else []:
            if not isinstance(item, dict):
                continue
            profile = self._parse_profile(item)
            if profile:
                self.profiles[profile.profile_id] = profile

    def _parse_profile(self, item: dict[str, Any]) -> SystemOptimizationProfile | None:
        """Converte schema novo ou legado para Core/Override/Shader/Overlay."""
        profile_id = str(item.get("id", "")).strip()
        if not profile_id:
            return None

        cores: dict[str, CoreOptimization] = {}
        raw_cores = item.get("cores", {})
        if isinstance(raw_cores, dict):
            for core_name, raw_core in raw_cores.items():
                if not isinstance(raw_core, dict):
                    continue
                core = str(core_name).strip()
                if not core:
                    continue
                files = raw_core.get("files", {})
                targets = raw_core.get("targets", {})
                cores[core] = CoreOptimization(
                    core=core,
                    files={str(k): str(v) for k, v in files.items() if k != "shader"} if isinstance(files, dict) else {},
                    targets={str(k): str(v) for k, v in targets.items() if k != "shader"} if isinstance(targets, dict) else {},
                    preferred=bool(raw_core.get("preferred", False)),
                )

        # Compatibilidade com o catálogo v2: um core por perfil.
        legacy_core = str(item.get("core", "")).strip()
        if legacy_core and legacy_core not in cores:
            files = item.get("files", {})
            targets = item.get("targets", {})
            cores[legacy_core] = CoreOptimization(
                core=legacy_core,
                files={str(k): str(v) for k, v in files.items() if k != "shader"} if isinstance(files, dict) else {},
                targets={str(k): str(v) for k, v in targets.items() if k != "shader"} if isinstance(targets, dict) else {},
                preferred=True,
            )

        return SystemOptimizationProfile(
            profile_id=profile_id,
            name=str(item.get("name", profile_id)),
            description=str(item.get("description", "")),
            systems=tuple(str(v).strip() for v in item.get("systems", []) if str(v).strip()),
            cores=tuple(cores),
            core_optimizations=cores,
            shader=self._parse_shader(item),
            overlay_asset=str(item.get("overlay_asset") or "").strip() or None,
            shader_options=tuple(str(v) for v in item.get("shader_options", [])),
        )

    def _parse_shader(self, item: dict[str, Any]) -> ShaderOptimization | None:
        """Resolve o shader escolhido sem copiar parâmetros potencialmente obsoletos."""
        raw = item.get("shader")
        shader_id = ""
        filename = ""
        reference = ""

        if isinstance(raw, str):
            shader_id = raw.strip()
        elif isinstance(raw, dict):
            shader_id = str(raw.get("id", "")).strip()
            filename = str(raw.get("filename", "")).strip()
            reference = str(raw.get("reference", "")).strip()

        if shader_id:
            selected = self.shader_library.get(shader_id)
            if selected is None:
                raise ValueError(f"Shader não cadastrado na biblioteca: {shader_id}")
            if not selected.safe_default and not bool(item.get("allow_heavy_shader", False)):
                raise ValueError(
                    f"Shader '{shader_id}' não é elegível como padrão: "
                    "possui reflexos/overlay embutido ou custo elevado."
                )
            return ShaderOptimization(selected.filename, selected.reference, selected.shader_id)

        targets = item.get("targets")
        if isinstance(targets, dict):
            target = str(targets.get("shader", "")).replace("\\", "/")
            filename = filename or Path(target).name

        if filename and reference:
            return ShaderOptimization(filename, reference, "custom")

        # Catálogo legado: preserva o nome do arquivo, mas substitui o conteúdo
        # antigo pelo Simple Preset oficial atual.
        if filename:
            selected = self.shader_library.get(DEFAULT_SHADER_ID)
            if selected:
                return ShaderOptimization(filename, selected.reference, selected.shader_id)
        return None

    def shader_options_for_system(self, system_name: str) -> list[ShaderProfile]:
        """Lista shaders seguros para um sistema, priorizando os recomendados."""
        key = self._key(system_name)
        result = []
        for shader in self.shader_library.values():
            if shader.systems and not any(self._key(system) == key for system in shader.systems):
                continue
            if shader.safe_default:
                result.append(shader)
        return sorted(result, key=lambda item: (not item.recommended, item.performance, item.name.casefold()))

    def shader_profile(self, shader_id: str) -> ShaderProfile | None:
        """Retorna metadados de um shader cadastrado."""
        return self.shader_library.get(shader_id)

    def profiles_for_system(self, system_name: str, system_id: str = "") -> list[SystemOptimizationProfile]:
        """Retorna perfis compatíveis com uma plataforma."""
        keys = {self._key(system_name), self._key(system_id)}
        return sorted(
            (profile for profile in self.profiles.values() if any(self._key(system) in keys for system in profile.systems)),
            key=lambda profile: profile.name.casefold(),
        )

    def get(self, profile_id: str) -> SystemOptimizationProfile | None:
        """Obtém um perfil por ID."""
        return self.profiles.get(profile_id)

    def _retroarch_config_root(self) -> Path:
        """Retorna a pasta config do RetroArch."""
        root = self.config.emulator_paths.get("retroarch", {}).get("config")
        if root:
            return Path(root)
        if self.config.retroarch_core_config_dir:
            return Path(self.config.retroarch_core_config_dir)
        if self.config.retroarch_dir:
            return Path(self.config.retroarch_dir) / "config"
        raise RuntimeError("Configure o RetroArch antes de aplicar uma otimização.")

    def _retroarch_root(self) -> Path:
        """Retorna a raiz do RetroArch."""
        return Path(self.config.retroarch_dir) if self.config.retroarch_dir else self._retroarch_config_root().parent

    def _shader_root(self) -> Path:
        """Retorna a pasta global de shaders."""
        native = self.config.retroarch_native_paths.get("video_shader_directory")
        if native:
            return Path(native)
        configured = self.config.emulator_paths.get("retroarch", {}).get("shaders")
        return Path(configured) if configured else self._retroarch_root() / "shaders"

    def _overlay_root(self) -> Path:
        """Retorna a pasta de overlays."""
        native = self.config.retroarch_native_paths.get("overlay_directory")
        return Path(native) if native else self._retroarch_root() / "overlays"

    def _overlay_config(self, profile: SystemOptimizationProfile) -> tuple[str | None, Path | None]:
        """Localiza o bezel 16:9, usado somente como moldura externa."""
        filename = profile.overlay_asset or self.OVERLAY_CANDIDATES.get(profile.profile_id)
        if not filename:
            return None, None
        configured = Path(filename).expanduser()
        if configured.is_absolute():
            return None, configured
        root = self._overlay_root()
        candidate = root / "2k Systems" / filename
        if not candidate.is_file():
            candidate = root / filename
        return f"overlays/2k Systems/{filename}", candidate

    @staticmethod
    def _normalize_retroarch_paths(content: str) -> str:
        """Normaliza referências de raiz RetroArch para `:/...`."""
        for old, new in (
            (":\\\\config", ":/config"),
            (":\\config", ":/config"),
            (":\\\\overlays", ":/overlays"),
            (":\\overlays", ":/overlays"),
            (":\\\\shaders", ":/shaders"),
            (":\\shaders", ":/shaders"),
        ):
            content = content.replace(old, new)
        return content

    @staticmethod
    def _remove_setting(content: str, key: str) -> str:
        """Remove todas as definições de uma chave."""
        return "\n".join(line for line in content.splitlines() if not line.strip().startswith(f"{key} ="))

    @staticmethod
    def _set_setting(content: str, key: str, value: str) -> str:
        """Substitui uma chave ou acrescenta uma nova."""
        replacement = f'{key} = "{value}"'
        output: list[str] = []
        found = False
        for line in content.splitlines():
            if line.strip().startswith(f"{key} ="):
                if not found:
                    output.append(replacement)
                    found = True
            else:
                output.append(line)
        if not found:
            output.append(replacement)
        return "\n".join(output)

    def _target_from_catalog(self, optimization: CoreOptimization, target_name: str) -> Path:
        """Resolve destino dentro de config/, bloqueando path traversal."""
        relative = optimization.targets.get(target_name)
        if not relative:
            raise KeyError(f"Destino não definido no perfil: {target_name}")
        root = self._retroarch_config_root().resolve()
        path = (root / relative).resolve()
        if root not in path.parents and path != root:
            raise ValueError(f"Destino fora da pasta de configuração: {path}")
        return path

    def _core_target(self, optimization: CoreOptimization, target_name: str) -> Path:
        """Resolve cfg/opt/rmp específico do core."""
        if target_name in optimization.targets:
            return self._target_from_catalog(optimization, target_name)
        paths = self.config.retroarch_core_paths(optimization.core)
        if target_name in {"override", "options"}:
            return paths[target_name]
        if target_name == "remap":
            return paths["remaps"].with_suffix(".rmp")
        raise KeyError(f"Destino não definido: {target_name}")

    def _shader_path(self, shader: ShaderOptimization) -> Path:
        """Resolve Sistema.slangp na pasta global shaders/."""
        root = self._shader_root().resolve()
        path = (root / shader.filename).resolve()
        if root not in path.parents and path != root:
            raise ValueError(f"Shader fora da pasta de shaders: {path}")
        return path

    def _prepare_core_files(self, profile: SystemOptimizationProfile, optimization: CoreOptimization) -> dict[Path, str]:
        """Prepara arquivos do core sem importar a proporção do overlay."""
        files = {key: self._normalize_retroarch_paths(value) for key, value in optimization.files.items()}
        if "override" not in files:
            return {self._core_target(optimization, key): value for key, value in files.items()}

        # O viewport mantém a proporção original do sistema/core.
        # O bezel 16:9 nunca deve gerar aspect_ratio_index = 21.
        override = self._remove_setting(files["override"], "aspect_ratio_index")

        if profile.shader:
            override = self._remove_setting(override, "video_shader")
            override = self._set_setting(override, "video_shader_enable", "true")
            override = self._set_setting(override, "video_shader", f":/shaders/{profile.shader.filename}")

        overlay_relative, overlay_file = self._overlay_config(profile)
        if overlay_relative and overlay_file and overlay_file.is_file():
            override = self._remove_setting(override, "input_overlay")
            override = self._remove_setting(override, "input_overlay_enable")
            override = self._set_setting(override, "input_overlay", f":/{overlay_relative}")
            override = self._set_setting(override, "input_overlay_enable", "true")

        files["override"] = override
        return {self._core_target(optimization, key): value for key, value in files.items()}

    def _preflight(self, profile: SystemOptimizationProfile) -> tuple[dict[Path, str], list[str]]:
        """Monta todos os arquivos antes de escrever qualquer um."""
        if not profile.core_optimizations:
            raise ValueError(f"Perfil sem cores configurados: {profile.profile_id}")
        prepared: dict[Path, str] = {}
        warnings: list[str] = []
        if profile.shader:
            prepared[self._shader_path(profile.shader)] = profile.shader.content
        overlay_relative, overlay_file = self._overlay_config(profile)
        if overlay_relative and not overlay_file.is_file():
            warnings.append(f"Bezel não encontrado: {overlay_file}")
        for core in profile.cores:
            prepared.update(self._prepare_core_files(profile, profile.core_optimizations[core]))
        return prepared, warnings

    def apply(self, system_name: str, system_id: str, profile_id: str, overwrite: bool = True) -> dict[str, Any]:
        """Aplica o perfil e sempre sobrescreve os arquivos definidos por ele.

        ``overwrite`` permanece na assinatura por compatibilidade. A política
        oficial é sempre sobrescrever: o perfil é a fonte de verdade dos
        arquivos que ele gerencia.
        """
        profile = self.get(profile_id)
        if profile is None:
            raise KeyError(f"Perfil de otimização não encontrado: {profile_id}")
        if profile not in self.profiles_for_system(system_name, system_id):
            raise ValueError(f"O perfil '{profile.name}' não é compatível com '{system_name}'.")

        prepared, warnings = self._preflight(profile)
        written: list[Path] = []
        for path, content in prepared.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._managed_content(content), encoding="utf-8")
            written.append(path)
        return {"profile": profile, "written": written, "backups": [], "warnings": warnings}

    def remove(self, system_name: str, system_id: str, profile_id: str) -> dict[str, Any]:
        """Remove somente arquivos do perfil marcados como gerenciados."""
        profile = self.get(profile_id)
        if profile is None:
            raise KeyError(f"Perfil de otimização não encontrado: {profile_id}")
        if profile not in self.profiles_for_system(system_name, system_id):
            raise ValueError(f"O perfil '{profile.name}' não é compatível com '{system_name}'.")

        paths: set[Path] = set()
        if profile.shader:
            paths.add(self._shader_path(profile.shader))
        for core in profile.cores:
            optimization = profile.core_optimizations[core]
            for key in optimization.files:
                paths.add(self._core_target(optimization, key))

        removed: list[Path] = []
        skipped: list[Path] = []
        for path in paths:
            if not path.exists():
                continue
            if self._is_managed(path):
                path.unlink()
                removed.append(path)
            else:
                skipped.append(path)
        return {"profile": profile, "removed": removed, "skipped": skipped, "backups": []}


__all__ = [
    "CoreOptimization",
    "ShaderProfile",
    "ShaderOptimization",
    "ShaderOptimizationProfile",
    "SystemOptimizationProfile",
    "SystemOptimizationService",
]
