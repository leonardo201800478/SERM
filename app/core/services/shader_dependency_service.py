"""Resolução de dependências de shaders para perfis de otimização."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.config.app_config import AppConfig
from app.core.services.shader_manager_service import ShaderManagerService, ShaderStatus
from app.core.services.system_optimization_service import ShaderOptimization, ShaderProfile


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


class ShaderDependencyService:
    """Resolve e instala dependências de shader sem misturar regras com a GUI."""

    def __init__(self, config: AppConfig, catalog_path) -> None:
        """Inicializa o resolvedor usando a mesma configuração do RetroArch."""
        self.manager = ShaderManagerService(config, catalog_path)

    def inspect(self, shader: ShaderOptimization, profile: ShaderProfile | None) -> ShaderDependency:
        """Audita um shader e determina se ele é de terceiro."""
        third_party = bool(profile and profile.source_url and not profile.source.casefold().startswith("libretro"))
        status = self.manager.status(shader.shader_id) if third_party else None
        return ShaderDependency(
            shader=shader,
            profile=profile,
            third_party=third_party,
            installed=bool(status and status.installed),
            status=status,
        )

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


__all__ = ["ShaderDependency", "ShaderDependencyService"]
