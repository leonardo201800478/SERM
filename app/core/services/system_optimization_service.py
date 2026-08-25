"""Perfis de otimização por sistema para RetroArch.

A camada de otimização é deliberadamente declarativa:
- um perfil pertence a um sistema;
- um perfil pode atender vários cores;
- o shader do sistema é compartilhado por todos os cores;
- arquivos gerados pelo Arcade Manager podem ser removidos sem backup;
- arquivos existentes que não foram gerados pelo Arcade Manager nunca são
  sobrescritos silenciosamente.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config.app_config import AppConfig


MANAGED_HEADER = "# ARCADE-MANAGER: system-optimization"


@dataclass(frozen=True, slots=True)
class CoreOptimization:
    """Configuração específica de um core para um sistema."""

    core: str
    files: dict[str, str]
    targets: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ShaderOptimization:
    """Shader compartilhado por todos os cores de um sistema."""

    filename: str
    content: str


@dataclass(frozen=True, slots=True)
class SystemOptimizationProfile:
    """Perfil de otimização visual e funcional de um sistema."""

    profile_id: str
    name: str
    description: str
    systems: tuple[str, ...]
    cores: tuple[str, ...]
    core_optimizations: dict[str, CoreOptimization]
    shader: ShaderOptimization | None = None
    overlay_asset: str | None = None

    @property
    def core(self) -> str:
        """Retorna o primeiro core do perfil para compatibilidade legada."""
        return self.cores[0] if self.cores else ""

    @property
    def files(self) -> dict[str, str]:
        """Retorna os arquivos do primeiro core para compatibilidade legada."""
        if not self.cores:
            return {}
        optimization = self.core_optimizations.get(self.cores[0])
        return dict(optimization.files) if optimization else {}

    @property
    def targets(self) -> dict[str, str]:
        """Retorna os destinos do primeiro core para compatibilidade legada."""
        if not self.cores:
            return {}
        optimization = self.core_optimizations.get(self.cores[0])
        return dict(optimization.targets) if optimization else {}


class SystemOptimizationService:
    """Carrega, aplica e remove perfis de otimização do RetroArch."""

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
        """Inicializa o catálogo de perfis."""
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.config = config or AppConfig()
        self.catalog_path = self.project_root / "data" / "launchbox" / "system_optimizations.json"
        self.profiles: dict[str, SystemOptimizationProfile] = {}
        self.reload()

    @staticmethod
    def _key(value: str | None) -> str:
        """Normaliza identificadores de sistemas e cores."""
        return " ".join((value or "").replace("_", " ").replace("-", " ").split()).casefold()

    @staticmethod
    def _managed_content(content: str) -> str:
        """Adiciona a marca de propriedade aos arquivos gerenciados."""
        if content.startswith(MANAGED_HEADER):
            return content.rstrip() + "\n"
        return f"{MANAGED_HEADER}\n{content.rstrip()}\n"

    @staticmethod
    def _is_managed(path: Path) -> bool:
        """Indica se um arquivo existente pertence ao Arcade Manager."""
        if not path.is_file():
            return False
        try:
            lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except OSError:
            return False
        return bool(lines) and lines[0].strip() == MANAGED_HEADER

    def reload(self) -> None:
        """Recarrega o catálogo declarativo."""
        try:
            raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            raw = {}
        profiles: dict[str, SystemOptimizationProfile] = {}
        items = raw.get("profiles", []) if isinstance(raw, dict) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            profile = self._parse_profile(item)
            if profile:
                profiles[profile.profile_id] = profile
        self.profiles = profiles

    def _parse_profile(self, item: dict[str, Any]) -> SystemOptimizationProfile | None:
        """Converte um item JSON novo ou legado em um perfil normalizado."""
        profile_id = str(item.get("id", "")).strip()
        if not profile_id:
            return None
        systems = tuple(str(value).strip() for value in item.get("systems", []) if str(value).strip())
        core_optimizations: dict[str, CoreOptimization] = {}

        cores_raw = item.get("cores", {})
        if isinstance(cores_raw, dict):
            for core_name, raw_core in cores_raw.items():
                if not isinstance(raw_core, dict):
                    continue
                core = str(core_name).strip()
                if not core:
                    continue
                files = raw_core.get("files", {})
                targets = raw_core.get("targets", {})
                if not isinstance(files, dict):
                    files = {}
                if not isinstance(targets, dict):
                    targets = {}
                files = {str(k): str(v) for k, v in files.items() if k != "shader"}
                targets = {str(k): str(v) for k, v in targets.items() if k != "shader"}
                core_optimizations[core] = CoreOptimization(core=core, files=files, targets=targets)

        # Compatibilidade durante a migração do catálogo atual.
        legacy_core = str(item.get("core", "")).strip()
        if legacy_core and legacy_core not in core_optimizations:
            files = item.get("files", {})
            targets = item.get("targets", {})
            legacy_files = {str(k): str(v) for k, v in files.items() if k != "shader"} if isinstance(files, dict) else {}
            legacy_targets = {str(k): str(v) for k, v in targets.items() if k != "shader"} if isinstance(targets, dict) else {}
            core_optimizations[legacy_core] = CoreOptimization(core=legacy_core, files=legacy_files, targets=legacy_targets)

        return SystemOptimizationProfile(
            profile_id=profile_id,
            name=str(item.get("name", profile_id)),
            description=str(item.get("description", "")),
            systems=systems,
            cores=tuple(core_optimizations),
            core_optimizations=core_optimizations,
            shader=self._parse_shader(item),
            overlay_asset=str(item.get("overlay_asset") or "").strip() or None,
        )

    @staticmethod
    def _parse_shader(item: dict[str, Any]) -> ShaderOptimization | None:
        """Lê o shader compartilhado no formato novo ou legado."""
        shader_raw = item.get("shader")
        if isinstance(shader_raw, dict):
            filename = str(shader_raw.get("filename", "")).strip()
            content = str(shader_raw.get("content", ""))
            if filename and content:
                return ShaderOptimization(filename=filename, content=content)

        files = item.get("files")
        targets = item.get("targets")
        if isinstance(files, dict) and isinstance(targets, dict):
            content = files.get("shader")
            target = str(targets.get("shader", "")).replace("\\", "/")
            if isinstance(content, str) and content.strip() and target:
                filename = Path(target).name
                if filename:
                    return ShaderOptimization(filename=filename, content=content)
        return None

    def profiles_for_system(self, system_name: str, system_id: str = "") -> list[SystemOptimizationProfile]:
        """Retorna os perfis compatíveis com uma plataforma."""
        keys = {self._key(system_name), self._key(system_id)}
        return sorted(
            (profile for profile in self.profiles.values() if any(self._key(system) in keys for system in profile.systems)),
            key=lambda profile: profile.name.casefold(),
        )

    def get(self, profile_id: str) -> SystemOptimizationProfile | None:
        """Obtém um perfil pelo identificador estável."""
        return self.profiles.get(profile_id)

    def _retroarch_config_root(self) -> Path:
        """Retorna a pasta Config do RetroArch."""
        root = self.config.emulator_paths.get("retroarch", {}).get("config")
        if root:
            return Path(root)
        if self.config.retroarch_core_config_dir:
            return Path(self.config.retroarch_core_config_dir)
        if self.config.retroarch_dir:
            return Path(self.config.retroarch_dir) / "config"
        raise RuntimeError("Configure o RetroArch antes de aplicar uma otimização.")

    def _retroarch_root(self) -> Path:
        """Retorna a raiz física da instalação do RetroArch."""
        if self.config.retroarch_dir:
            return Path(self.config.retroarch_dir)
        return self._retroarch_config_root().parent

    def _shader_root(self) -> Path:
        """Retorna a pasta global de shaders do RetroArch."""
        native = self.config.retroarch_native_paths.get("video_shader_directory")
        if native:
            return Path(native)
        configured = self.config.emulator_paths.get("retroarch", {}).get("shaders")
        if configured:
            return Path(configured)
        return self._retroarch_root() / "shaders"

    def _overlay_root(self) -> Path:
        """Retorna a pasta de overlays configurada no RetroArch."""
        native = self.config.retroarch_native_paths.get("overlay_directory")
        if native:
            return Path(native)
        return self._retroarch_root() / "overlays"

    def _overlay_config(self, profile: SystemOptimizationProfile) -> tuple[str | None, Path | None]:
        """Localiza o bezel 16:9 correspondente ao perfil."""
        filename = profile.overlay_asset or self.OVERLAY_CANDIDATES.get(profile.profile_id)
        if not filename:
            return None, None
        configured = Path(filename).expanduser()
        if configured.is_absolute():
            return None, configured
        overlay_root = self._overlay_root()
        candidate = overlay_root / "2k Systems" / filename
        if not candidate.is_file():
            candidate = overlay_root / filename
        return f"overlays/2k Systems/{filename}", candidate

    @staticmethod
    def _normalize_retroarch_paths(content: str) -> str:
        """Normaliza referências RetroArch para o formato `:/`."""
        return (
            content.replace('= ":\\\\', '= ":/')
            .replace('= ":\\', '= ":/')
            .replace(":\\\\config", ":/config")
            .replace(":\\config", ":/config")
            .replace(":\\\\overlays", ":/overlays")
            .replace(":\\overlays", ":/overlays")
        )

    def _target_from_catalog(self, optimization: CoreOptimization, target_name: str) -> Path:
        """Resolve um destino explicitamente definido no catálogo."""
        relative = optimization.targets.get(target_name)
        if not relative:
            raise KeyError(f"Destino não definido no perfil: {target_name}")
        root = self._retroarch_config_root()
        path = (root / relative).resolve()
        root_resolved = root.resolve()
        if root_resolved not in path.parents and path != root_resolved:
            raise ValueError(f"Destino fora da pasta de configuração: {path}")
        return path

    def _core_target(self, optimization: CoreOptimization, target_name: str) -> Path:
        """Resolve um destino de core pelo catálogo ou pela árvore nativa."""
        if target_name in optimization.targets:
            return self._target_from_catalog(optimization, target_name)
        core_paths = self.config.retroarch_core_paths(optimization.core)
        if target_name in {"override", "options"}:
            return core_paths[target_name]
        if target_name == "remap":
            return core_paths["remaps"].with_suffix(".rmp")
        raise KeyError(f"Destino não definido: {target_name}")

    def _shader_path(self, shader: ShaderOptimization) -> Path:
        """Resolve o shader diretamente na pasta global de shaders."""
        root = self._shader_root().resolve()
        path = (root / shader.filename).resolve()
        if root not in path.parents and path != root:
            raise ValueError(f"Shader fora da pasta de shaders do RetroArch: {path}")
        return path

    def _write_managed(self, path: Path, content: str, overwrite: bool) -> None:
        """Escreve arquivo gerenciado sem sobrescrever arquivo externo silenciosamente."""
        if path.exists() and not self._is_managed(path) and not overwrite:
            raise FileExistsError(f"Arquivo existente não gerenciado pelo Arcade Manager: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._managed_content(content), encoding="utf-8")

    def _prepare_core_files(self, profile: SystemOptimizationProfile, optimization: CoreOptimization) -> dict[Path, str]:
        """Prepara os arquivos específicos de um core."""
        files = dict(optimization.files)
        if "override" in files:
            files["override"] = self._normalize_retroarch_paths(files["override"])

        if profile.shader and "override" in files:
            override = files["override"]
            lines = [line for line in override.splitlines() if not line.strip().startswith("video_shader =")]
            if not any(line.strip().startswith("video_shader_enable") for line in lines):
                lines.append('video_shader_enable = "true"')
            lines.append(f'video_shader = ":/shaders/{profile.shader.filename}"')
            files["override"] = "\n".join(lines)

        overlay_relative, overlay_file = self._overlay_config(profile)
        if "override" in files and overlay_relative and overlay_file and overlay_file.is_file():
            override = files["override"]
            if "input_overlay =" not in override:
                override += f'\ninput_overlay = ":/{overlay_relative}"\ninput_overlay_enable = "true"'
            files["override"] = override

        return {self._core_target(optimization, key): content for key, content in files.items()}

    def _expected_paths(self, profile: SystemOptimizationProfile) -> set[Path]:
        """Retorna todos os arquivos que o perfil pode ter criado."""
        paths: set[Path] = set()
        for optimization in profile.core_optimizations.values():
            for key in optimization.files:
                try:
                    paths.add(self._core_target(optimization, key))
                except (KeyError, RuntimeError, ValueError):
                    continue
        if profile.shader:
            paths.add(self._shader_path(profile.shader))
        return paths

    def apply(self, system_name: str, system_id: str, profile_id: str, *, overwrite: bool = False) -> dict[str, Any]:
        """Aplica um perfil a todos os cores declarados e cria o shader global."""
        profile = self.get(profile_id)
        if profile is None:
            raise KeyError(f"Perfil de otimização não encontrado: {profile_id}")
        if profile not in self.profiles_for_system(system_name, system_id):
            raise ValueError(f"O perfil '{profile.name}' não é compatível com '{system_name}'.")

        written: list[Path] = []
        warnings: list[str] = []
        prepared: dict[Path, str] = {}
        if profile.shader:
            prepared[self._shader_path(profile.shader)] = profile.shader.content
        for optimization in profile.core_optimizations.values():
            prepared.update(self._prepare_core_files(profile, optimization))

        # Preflight completo: nenhuma alteração parcial se houver colisão externa.
        if not overwrite:
            collisions = [path for path in prepared if path.exists() and not self._is_managed(path)]
            if collisions:
                raise FileExistsError(
                    "Arquivo(s) existente(s) não gerenciado(s) pelo Arcade Manager: "
                    + ", ".join(str(path) for path in sorted(collisions))
                )

        for path, content in prepared.items():
            self._write_managed(path, content, overwrite)
            written.append(path)

        _, overlay_file = self._overlay_config(profile)
        if overlay_file is not None and not overlay_file.is_file():
            warnings.append(f"Bezel não encontrado: {overlay_file}")

        return {
            "profile": profile,
            "written": written,
            "removed": [],
            "backups": [],
            "warnings": warnings,
        }

    def remove(self, system_name: str, system_id: str, profile_id: str) -> dict[str, Any]:
        """Remove somente arquivos pertencentes ao Arcade Manager."""
        profile = self.get(profile_id)
        if profile is None:
            raise KeyError(f"Perfil de otimização não encontrado: {profile_id}")
        if profile not in self.profiles_for_system(system_name, system_id):
            raise ValueError(f"O perfil '{profile.name}' não é compatível com '{system_name}'.")

        removed: list[Path] = []
        skipped: list[Path] = []
        for path in self._expected_paths(profile):
            if not path.is_file():
                continue
            if self._is_managed(path):
                path.unlink()
                removed.append(path)
            else:
                skipped.append(path)

        return {
            "profile": profile,
            "written": [],
            "removed": removed,
            "backups": [],
            "warnings": [f"Arquivo externo preservado: {path}" for path in sorted(skipped)],
        }


__all__ = [
    "CoreOptimization",
    "MANAGED_HEADER",
    "ShaderOptimization",
    "SystemOptimizationProfile",
    "SystemOptimizationService",
]
