"""Perfis de otimização por sistema para RetroArch.

A otimização de sistema é uma camada declarativa acima dos mecanismos nativos
 do RetroArch. Cada perfil descreve arquivos completos que podem ser aplicados
à instalação configurada, sem modificar o retroarch.cfg global.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config.app_config import AppConfig


@dataclass(frozen=True, slots=True)
class SystemOptimizationProfile:
    """Perfil pronto de configuração visual, core, controles e overlay."""

    profile_id: str
    name: str
    description: str
    systems: tuple[str, ...]
    core: str
    files: dict[str, str]
    targets: dict[str, str]
    overlay_asset: str | None = None


class SystemOptimizationService:
    """Carrega e aplica perfis declarativos de otimização do sistema.

    Os arquivos são escritos nos diretórios nativos do RetroArch definidos
    pelo AppConfig. Antes de substituir um arquivo existente, é criado um
    backup ``.arcademanager.bak``. O retroarch.cfg global nunca é alterado.

    A instalação também normaliza referências RetroArch com ``:/`` e injeta
    automaticamente o bezel 2K Systems correspondente quando ele existe.
    """

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
        """Normaliza identificadores de sistemas e perfis."""
        return " ".join((value or "").replace("_", " ").replace("-", " ").split()).casefold()

    def reload(self) -> None:
        """Recarrega o catálogo declarativo sem interromper a aplicação."""
        try:
            raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            raw = {}
        profiles: dict[str, SystemOptimizationProfile] = {}
        for item in raw.get("profiles", []) if isinstance(raw, dict) else []:
            if not isinstance(item, dict):
                continue
            profile_id = str(item.get("id", "")).strip()
            if not profile_id:
                continue
            systems = tuple(str(value) for value in item.get("systems", []) if str(value).strip())
            files = item.get("files", {})
            targets = item.get("targets", {})
            if not isinstance(files, dict) or not isinstance(targets, dict):
                continue
            profiles[profile_id] = SystemOptimizationProfile(
                profile_id=profile_id,
                name=str(item.get("name", profile_id)),
                description=str(item.get("description", "")),
                systems=systems,
                core=str(item.get("core", "")),
                files={str(k): str(v) for k, v in files.items()},
                targets={str(k): str(v) for k, v in targets.items()},
                overlay_asset=str(item.get("overlay_asset")) if item.get("overlay_asset") else None,
            )
        self.profiles = profiles

    def profiles_for_system(self, system_name: str, system_id: str = "") -> list[SystemOptimizationProfile]:
        """Retorna os perfis compatíveis com uma plataforma."""
        keys = {self._key(system_name), self._key(system_id)}
        result = [
            profile for profile in self.profiles.values()
            if any(self._key(system) in keys for system in profile.systems)
        ]
        return sorted(result, key=lambda profile: profile.name.casefold())

    def get(self, profile_id: str) -> SystemOptimizationProfile | None:
        """Obtém um perfil pelo identificador estável."""
        return self.profiles.get(profile_id)

    def _retroarch_config_root(self) -> Path:
        """Retorna o diretório Config do RetroArch configurado no projeto."""
        root = self.config.emulator_paths.get("retroarch", {}).get("config")
        if root:
            return Path(root)
        if self.config.retroarch_core_config_dir:
            return Path(self.config.retroarch_core_config_dir)
        if self.config.retroarch_dir:
            return Path(self.config.retroarch_dir) / "config"
        raise RuntimeError("Configure o RetroArch antes de aplicar uma otimização de sistema.")

    def _retroarch_root(self) -> Path:
        """Retorna a raiz física da instalação do RetroArch."""
        if self.config.retroarch_dir:
            return Path(self.config.retroarch_dir)
        config_root = self._retroarch_config_root()
        if config_root.name.casefold() == "config":
            return config_root.parent
        return config_root

    def _overlay_root(self) -> Path:
        """Retorna a pasta de overlays configurada no RetroArch."""
        native = self.config.retroarch_native_paths.get("overlay_directory")
        if native:
            return Path(native)
        return self._retroarch_root() / "overlays"

    def _overlay_config(self, profile: SystemOptimizationProfile) -> tuple[str | None, Path | None]:
        """Localiza o bezel 16:9 correspondente ao perfil.

        A coleção usada pelo projeto fica em ``overlays/2k Systems``. O método
        aceita também um caminho explícito em ``overlay_asset`` para futuros
        perfis que não sigam essa convenção.
        """
        filename = profile.overlay_asset or self.OVERLAY_CANDIDATES.get(profile.profile_id)
        if not filename:
            return None, None

        configured = Path(filename).expanduser()
        if configured.is_absolute():
            candidate = configured
            relative = None
        else:
            overlay_root = self._overlay_root()
            candidate = overlay_root / "2k Systems" / filename
            if not candidate.is_file():
                candidate = overlay_root / filename
            relative = Path("overlays") / "2k Systems" / filename

        if not candidate.is_file():
            return relative.as_posix() if relative else None, candidate
        return relative.as_posix() if relative else None, candidate

    @staticmethod
    def _normalize_retroarch_paths(content: str) -> str:
        """Corrige raízes RetroArch escritas como ``:\\`` para o formato ``:/``.

        O formato ``:/`` é a sintaxe de raiz documentada pelo RetroArch e é
        necessário para referências como ``:/config/...`` e ``:/overlays/...``.
        """
        return (
            content
            .replace("= \":\\\\", '= ":/')
            .replace("= \"\\\\", '= ":/')
            .replace(":\\\\config", ":/config")
            .replace(":\\\\overlays", ":/overlays")
            .replace(":\\config", ":/config")
            .replace(":\\overlays", ":/overlays")
        )

    def _prepare_files(
        self,
        profile: SystemOptimizationProfile,
    ) -> tuple[dict[str, str], list[str]]:
        """Prepara arquivos do perfil e injeta o overlay quando disponível."""
        files = dict(profile.files)
        warnings: list[str] = []

        for key, content in list(files.items()):
            files[key] = self._normalize_retroarch_paths(content)

        overlay_relative, overlay_file = self._overlay_config(profile)
        if overlay_file is not None and not overlay_file.is_file():
            warnings.append(f"Bezel não encontrado: {overlay_file}")

        if overlay_relative and "override" in files and overlay_file and overlay_file.is_file():
            override = files["override"]
            if "input_overlay" not in override:
                override = (
                    override.rstrip()
                    + f'\ninput_overlay = ":/{overlay_relative.replace(chr(92), "/")}"'
                    + '\ninput_overlay_enable = "true"'
                )
            files["override"] = override
        elif overlay_relative and "override" in files:
            warnings.append(f"Bezel esperado não encontrado: {overlay_file}")

        return files, warnings

    def _target_path(self, profile: SystemOptimizationProfile, target_name: str) -> Path:
        """Resolve um destino relativo à árvore nativa do RetroArch."""
        relative = profile.targets.get(target_name)
        if not relative:
            raise KeyError(f"Destino não definido no perfil: {target_name}")
        root = self._retroarch_config_root()
        path = (root / relative).resolve()
        if root.resolve() not in path.parents and path != root.resolve():
            raise ValueError(f"Destino fora da pasta de configuração do RetroArch: {path}")
        return path

    @staticmethod
    def _backup(path: Path) -> Path | None:
        """Cria backup do arquivo existente, sem sobrescrever o backup anterior."""
        if not path.is_file():
            return None
        backup = path.with_name(path.name + ".arcademanager.bak")
        if backup.exists():
            index = 2
            while path.with_name(f"{path.name}.arcademanager.bak{index}").exists():
                index += 1
            backup = path.with_name(f"{path.name}.arcademanager.bak{index}")
        shutil.copy2(path, backup)
        return backup

    def apply(self, system_name: str, system_id: str, profile_id: str) -> dict[str, Any]:
        """Aplica um perfil e retorna os arquivos criados, backups e avisos."""
        profile = self.get(profile_id)
        if profile is None:
            raise KeyError(f"Perfil de otimização não encontrado: {profile_id}")
        if not self.profiles_for_system(system_name, system_id) or profile not in self.profiles_for_system(system_name, system_id):
            raise ValueError(f"O perfil '{profile.name}' não é compatível com '{system_name}'.")

        files, warnings = self._prepare_files(profile)
        written: list[Path] = []
        backups: list[Path] = []

        for file_key, content in files.items():
            target = self._target_path(profile, file_key)
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = self._backup(target)
            if backup:
                backups.append(backup)
            target.write_text(content.rstrip() + "\n", encoding="utf-8")
            written.append(target)

        return {
            "profile": profile,
            "written": written,
            "backups": backups,
            "warnings": warnings,
        }


__all__ = ["SystemOptimizationProfile", "SystemOptimizationService"]
