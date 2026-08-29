"""Resolução de dependências de shaders para perfis de otimização.

A GUI não precisa conhecer a origem do shader nem a forma de instalação.
Shaders oficiais do Libretro são considerados dependências já fornecidas pela
instalação normal do RetroArch; shaders de terceiros passam pelo
``ShaderManagerService`` e só são baixados quando explicitamente solicitados.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.config.app_config import AppConfig
from app.core.services.shader_manager_service import ShaderManagerService, ShaderStatus
from app.core.services.system_optimization_service import (
    ShaderOptimization,
    ShaderProfile,
)


@dataclass(frozen=True, slots=True)
class ShaderDependency:
    """Descreve o estado necessário para um shader de um perfil."""

    shader: ShaderOptimization
    profile: ShaderProfile | None
    third_party: bool
    installed: bool
    status: ShaderStatus | None

    @property
    def requires_download(self) -> bool:
        """Indica se a aplicação depende de um download de terceiro."""
        return self.third_party and not self.installed

    @property
    def source_name(self) -> str:
        """Retorna a origem legível da dependência."""
        if self.profile is None:
            return "desconhecida"
        return self.profile.source or self.profile.source_url or "desconhecida"


class ShaderDependencyService:
    """Resolve e instala dependências de shader sem misturar regras com a GUI."""

    def __init__(self, config: AppConfig, catalog_path: Path) -> None:
        """Inicializa o resolvedor usando a mesma configuração do RetroArch."""
        self.manager = ShaderManagerService(config, catalog_path)
        self.catalog_path = catalog_path

    def _catalog_profile(self, shader_id: str) -> ShaderProfile | None:
        """Converte uma entrada do catálogo em ``ShaderProfile``."""
        try:
            raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Não foi possível ler o catálogo de shaders: {self.catalog_path}") from exc
        for item in raw.get("shaders", []) if isinstance(raw, dict) else []:
            if not isinstance(item, dict) or str(item.get("id", "")).strip() != shader_id:
                continue
            return ShaderProfile(
                shader_id=shader_id,
                name=str(item.get("name", shader_id)),
                filename=str(item.get("filename", "")),
                reference=str(item.get("reference", "")),
                source=str(item.get("source", "")),
                source_url=str(item.get("source_url", "")),
                performance=str(item.get("performance", "light")),
                reflection=bool(item.get("reflection", False)),
                embedded_overlay=bool(item.get("embedded_overlay", False)),
                recommended=bool(item.get("recommended", False)),
                systems=tuple(str(value) for value in item.get("systems", []) if str(value).strip()),
                notes=str(item.get("notes", "")),
            )
        return None

    @staticmethod
    def _is_third_party(profile: ShaderProfile | None) -> bool:
        """Determina se a origem do shader é externa ao ecossistema Libretro."""
        if profile is None:
            return False
        source = profile.source.casefold().strip()
        source_url = profile.source_url.casefold().strip()
        return bool(source_url) and not source.startswith("libretro")

    def inspect(self, shader: ShaderOptimization, profile: ShaderProfile | None = None) -> ShaderDependency:
        """Audita um shader e determina se ele é de terceiro."""
        profile = profile or self._catalog_profile(shader.shader_id)
        third_party = self._is_third_party(profile)
        status = self.manager.status(shader.shader_id) if third_party else None
        return ShaderDependency(
            shader=shader,
            profile=profile,
            third_party=third_party,
            installed=bool(status and status.installed),
            status=status,
        )

    def inspect_by_id(self, shader: ShaderOptimization) -> ShaderDependency:
        """Audita um shader usando diretamente o catálogo configurado."""
        return self.inspect(shader, self._catalog_profile(shader.shader_id))

    def install(
        self,
        dependency: ShaderDependency,
        *,
        progress: Callable[[int, int], None] | None = None,
    ) -> ShaderStatus:
        """Instala uma dependência de terceiro previamente auditada."""
        if not dependency.third_party:
            raise ValueError("O shader informado não é uma dependência de terceiro instalável.")
        return self.manager.install(dependency.shader.shader_id, progress=progress)

    def ensure_installed(
        self,
        dependency: ShaderDependency,
        *,
        progress: Callable[[int, int], None] | None = None,
    ) -> ShaderStatus | None:
        """Garante a instalação somente quando a dependência for de terceiro."""
        if not dependency.third_party:
            return None
        if dependency.installed and dependency.status is not None:
            return dependency.status
        return self.install(dependency, progress=progress)


__all__ = ["ShaderDependency", "ShaderDependencyService"]
