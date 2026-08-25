"""Serviço de otimização visual por sistema para RetroArch.

Regras fundamentais:
- a proporção do sistema pertence ao viewport/core, nunca ao bezel;
- overlay 16:9 é somente a moldura externa;
- shaders são presets Slang válidos e independentes dos arquivos de core;
- aplicar um perfil sempre sobrescreve os arquivos definidos pelo perfil;
- remoção só apaga arquivos que tenham sido marcados pelo Arcade Manager.
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
    """Preset Slang compartilhado pelos cores de um sistema."""

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
        """Retorna o primeiro core para compatibilidade legada."""
        return self.cores[0] if self.cores else ""

    @property
    def files(self) -> dict[str, str]:
        """Retorna os arquivos do primeiro core para compatibilidade legada."""
        item = self.core_optimizations.get(self.core)
        return dict(item.files) if item else {}

    @property
    def targets(self) -> dict[str, str]:
        """Retorna os destinos do primeiro core para compatibilidade legada."""
        item = self.core_optimizations.get(self.core)
        return dict(item.targets) if item else {}


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

    # O preset completo oficial continua sendo fornecido pelo pacote
    # slang-shaders. O arquivo gerado pelo projeto é deliberadamente um
    # Simple Preset: uma única referência, sem parâmetros inventados.
    DEFAULT_SHADER_REFERENCE = ":/shaders/shaders_slang/crt/crt-guest-advanced-ntsc.slangp"

    def __init__(self, project_root: Path | None = None, config: AppConfig | None = None) -> None:
        """Inicializa o serviço e carrega o catálogo."""
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.config = config or AppConfig()
        self.catalog_path = self.project_root / "data" / "launchbox" / "system_optimizations.json"
        self.profiles: dict[str, SystemOptimizationProfile] = {}
        self.reload()

    @staticmethod
    def _key(value: str | None) -> str:
        """Normaliza identificadores para comparação."""
        return " ".join((value or "").replace("_", " ").replace("-", " ").split()).casefold()

    @staticmethod
    def _managed_content(content: str) -> str:
        """Adiciona a marca de propriedade aos arquivos gerenciados."""
        if content.startswith(MANAGED_HEADER):
            return content.rstrip() + "\n"
        return f"{MANAGED_HEADER}\n{content.rstrip()}\n"

    @staticmethod
    def _is_managed(path: Path) -> bool:
        """Indica se um arquivo existente foi gerado pelo Arcade Manager."""
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
        for item in raw.get("profiles", []) if isinstance(raw, dict) else []:
            if not isinstance(item, dict):
                continue
            profile = self._parse_profile(item)
            if profile:
                profiles[profile.profile_id] = profile
        self.profiles = profiles

    def _parse_profile(self, item: dict[str, Any]) -> SystemOptimizationProfile | None:
        """Converte o formato novo ou legado em perfil normalizado."""
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
                )

        # Compatibilidade com o catálogo v2 atual: um core por perfil.
        legacy_core = str(item.get("core", "")).strip()
        if legacy_core and legacy_core not in cores:
            files = item.get("files", {})
            targets = item.get("targets", {})
            cores[legacy_core] = CoreOptimization(
                core=legacy_core,
                files={str(k): str(v) for k, v in files.items() if k != "shader"} if isinstance(files, dict) else {},
                targets={str(k): str(v) for k, v in targets.items() if k != "shader"} if isinstance(targets, dict) else {},
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
        )

    @classmethod
    def _parse_shader(cls, item: dict[str, Any]) -> ShaderOptimization | None:
        """Cria um Simple Preset Slang válido para o sistema.

        O catálogo anterior continha parâmetros de versões antigas do CRT
        Guest. Alguns nomes já não existem no shader atual e podem tornar o
        preset inconsistente. Como o objetivo do arquivo é selecionar o
        preset oficial, não duplicamos nem inventamos seus parâmetros aqui.
        """
        raw = item.get("shader")
        filename = ""
        if isinstance(raw, dict):
            filename = str(raw.get("filename", "")).strip()
        if not filename:
            files = item.get("files")
            targets = item.get("targets")
            if isinstance(files, dict) and isinstance(targets, dict) and isinstance(files.get("shader"), str):
                filename = Path(str(targets.get("shader", ""))).name
        if not filename:
            # O formato legado normalmente identifica o shader pelo target.
            targets = item.get("targets")
            if isinstance(targets, dict):
                filename = Path(str(targets.get("shader", ""))).name
        if not filename:
            return None

        content = (
            "; Arcade Manager — Simple Preset\n"
            "; A proporção do sistema NÃO é definida pelo shader.\n"
            f'#reference "{cls.DEFAULT_SHADER_REFERENCE}"\n'
        )
        return ShaderOptimization(filename=filename, content=content)

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
        """Retorna a raiz física da instalação do RetroArch."""
        return Path(self.config.retroarch_dir) if self.config.retroarch_dir else self._retroarch_config_root().parent

    def _shader_root(self) -> Path:
        """Retorna a pasta global de shaders do RetroArch."""
        native = self.config.retroarch_native_paths.get("video_shader_directory")
        if native:
            return Path(native)
        configured = self.config.emulator_paths.get("retroarch", {}).get("shaders")
        return Path(configured) if configured else self._retroarch_root() / "shaders"

    def _overlay_root(self) -> Path:
        """Retorna a pasta de overlays configurada no RetroArch."""
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
        """Normaliza caminhos RetroArch para a sintaxe `:/`."""
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
        """Remove todas as definições de uma chave RetroArch."""
        return "\n".join(line for line in content.splitlines() if not line.strip().startswith(f"{key} ="))

    @staticmethod
    def _set_setting(content: str, key: str, value: str) -> str:
        """Substitui uma definição existente ou acrescenta uma nova."""
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
        """Resolve um destino do catálogo dentro de config/."""
        relative = optimization.targets.get(target_name)
        if not relative:
            raise KeyError(f"Destino não definido no perfil: {target_name}")
        root = self._retroarch_config_root().resolve()
        path = (root / relative).resolve()
        if root not in path.parents and path != root:
            raise ValueError(f"Destino fora da pasta de configuração: {path}")
        return path

    def _core_target(self, optimization: CoreOptimization, target_name: str) -> Path:
        """Resolve um arquivo específico do core."""
        if target_name in optimization.targets:
            return self._target_from_catalog(optimization, target_name)
        paths = self.config.retroarch_core_paths(optimization.core)
        if target_name in {"override", "options"}:
            return paths[target_name]
        if target_name == "remap":
            return paths["remaps"].with_suffix(".rmp")
        raise KeyError(f"Destino não definido: {target_name}")

    def _shader_path(self, shader: ShaderOptimization) -> Path:
        """Resolve o preset global diretamente em shaders/."""
        root = self._shader_root().resolve()
        path = (root / shader.filename).resolve()
        if root not in path.parents and path != root:
            raise ValueError(f"Shader fora da pasta de shaders do RetroArch: {path}")
        return path

    def _prepare_core_files(self, profile: SystemOptimizationProfile, optimization: CoreOptimization) -> dict[Path, str]:
        """Prepara os arquivos do core sem importar a proporção do overlay."""
        files = {key: self._normalize_retroarch_paths(value) for key, value in optimization.files.items()}

        if "override" in files:
            override = files["override"]

            # O viewport pertence ao sistema/core. O bezel 16:9 nunca deve
            # transformar uma máquina 4:3 em 16:9. Removemos qualquer valor
            # preexistente para que o RetroArch/core escolha a proporção nativa.
            override = self._remove_setting(override, "aspect_ratio_index")

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

    def apply(self, system_name: str, system_id: str, profile_id: str, *, overwrite: bool = True) -> dict[str, Any]:
        """Aplica o perfil e SEMPRE sobrescreve os arquivos definidos por ele.

        ``overwrite`` permanece na assinatura por compatibilidade com chamadas
        existentes, mas a política atual é deliberadamente determinística:
        qualquer arquivo-alvo existente é substituído pelo conteúdo do perfil.
        Não são criados backups.
        """
        del overwrite
        profile = self.get(profile_id)
        if profile is None:
            raise KeyError(f"Perfil de otimização não encontrado: {profile_id}")
        if profile not in self.profiles_for_system(system_name, system_id):
            raise ValueError(f"O perfil '{profile.name}' não é compatível com '{system_name}'.")

        prepared: dict[Path, str] = {}
        warnings: list[str] = []
        if profile.shader:
            prepared[self._shader_path(profile.shader)] = profile.shader.content
        for optimization in profile.core_optimizations.values():
            prepared.update(self._prepare_core_files(profile, optimization))

        # Preflight de caminhos antes de escrever: não deixa o perfil entrar
        # em uma árvore fora de config/ ou shaders/ por engano.
        for path in prepared:
            path.parent.mkdir(parents=True, exist_ok=True)

        written: list[Path] = []
        for path, content in prepared.items():
            # Sempre substitui, inclusive arquivo criado manualmente ou por
            # versão anterior do projeto. Isso é requisito do perfil.
            path.write_text(self._managed_content(content), encoding="utf-8")
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
    "ShaderOptimization",
    "SystemOptimizationProfile",
    "SystemOptimizationService",
]
