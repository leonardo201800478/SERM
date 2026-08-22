"""Serviço de estado dos emuladores para a camada de apresentação.

A GUI não descobre executáveis nem grava diretamente no SQLite. Este serviço
orquestra descoberta, persistência e leitura do estado normalizado.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.config.app_config import AppConfig
from app.core.services.emulator_discovery_service import (
    EmulatorDiscoveryOptions,
    EmulatorDiscoveryService,
    EmulatorInstallation,
)
from app.core.services.emulator_persistence_service import EmulatorPersistenceService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EmulatorStatus:
    """Estado resumido de um emulador para exibição na Home."""

    emulator: str
    executable: Path | None
    root: Path | None
    version: str | None
    status: str
    configs: tuple[dict[str, object], ...] = ()


class EmulatorStatusService:
    """Mantém a Home desacoplada da descoberta e do banco."""

    def __init__(
        self,
        config: AppConfig | None = None,
        discovery: EmulatorDiscoveryService | None = None,
        persistence: EmulatorPersistenceService | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.discovery = discovery or EmulatorDiscoveryService()
        self.persistence = persistence or EmulatorPersistenceService()

    def refresh(self) -> dict[str, EmulatorStatus]:
        """Redescobre os emuladores configurados e persiste o resultado."""
        options = EmulatorDiscoveryOptions(
            mame_executable=self.config.mame_path,
            flycast_executable=self.config.flycast_path,
            supermodel_executable=self.config.supermodel_path,
            fbneo_executable=self.config.fbneo_path,
        )
        installations = self.discovery.discover_all(options)
        try:
            self.persistence.persist(installations.values())
        except Exception:
            logger.exception("Falha ao persistir estado dos emuladores; mantendo descoberta em memória.")
        return self._to_statuses(installations)

    @staticmethod
    def _to_statuses(
        installations: dict[str, EmulatorInstallation],
    ) -> dict[str, EmulatorStatus]:
        """Converte o resultado da descoberta em modelos simples para a GUI."""
        statuses: dict[str, EmulatorStatus] = {}
        for name, installation in installations.items():
            config_statuses = tuple(
                {
                    "name": cfg.name,
                    "status": cfg.status,
                    "generated": cfg.generated,
                }
                for cfg in installation.configs
            )
            statuses[name] = EmulatorStatus(
                emulator=name,
                executable=installation.executable,
                root=installation.root,
                version=installation.version,
                status=EmulatorStatusService._installation_status(installation),
                configs=config_statuses,
            )
        return statuses

    @staticmethod
    def _installation_status(installation: EmulatorInstallation) -> str:
        """Calcula o estado apresentado na Home sem ocultar problemas."""
        if installation.executable is None:
            return "not_found"
        if any(cfg.status == "error" for cfg in installation.configs):
            return "error"
        if any(cfg.status.startswith("corrupt") for cfg in installation.configs):
            return "configuration_corrupt"
        if any(cfg.status.startswith("missing") for cfg in installation.configs):
            return "configuration_missing"
        if any(cfg.status.startswith("generated") for cfg in installation.configs):
            return "ready_generated"
        return "ready"
