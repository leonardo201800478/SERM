"""Resolução de dependências de shaders para perfis de otimização.

A GUI não precisa conhecer a origem do shader nem a forma de instalação.
Shaders oficiais do Libretro são considerados dependências já fornecidas pela
instalação normal do RetroArch; shaders de terceiros passam pelo
``ShaderManagerService`` e só são baixados quando explicitamente solicitados.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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

    @staticmethod
    def _is_third_party(profile: ShaderProfile | None) -> bool:
        """Determina se a origem do shader é externa ao ecossistema Libretro."""
        if profile is None:
            return False
        source = profile.source.casefold().strip()
        source_url = profile.source_url.casefold().strip()
        return bool(source_url) and not source.startswith("libretro")

    def inspect(self, shader: ShaderOptimization, profile: ShaderProfile | None) -> ShaderDependency:
        """Audita um shader e determina se ele é de terceiro."""
        third_party = self._is_third_party(profile)
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

    def ensure_installed(
        self,
        dependency: ShaderDependency,
        *,
        progress: Callable[[int, int], None] | None = None,
    ) -> ShaderStatus | None:
        """Garante a instalação somente quando a dependência for de terceiro.

        Para shaders oficiais não há qualquer operação de filesystem ou download;
        o método retorna ``None`` porque a dependência é satisfeita pela instalação
        normal do RetroArch.
        """
        if not dependency.third_party:
            return None
        if dependency.installed and dependency.status is not None:
            return dependency.status
        return self.install(dependency, progress=progress)


__all__ = ["ShaderDependency", "ShaderDependencyService"]
