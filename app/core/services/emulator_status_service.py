"""Serviço de estado dos emuladores para a camada de apresentação."""
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
from app.core.services.emulator_version_service import (
    EmulatorVersionInfo,
    EmulatorVersionService,
)

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
    """Mantém a Home desacoplada da descoberta, versões e banco."""

    def __init__(
        self,
        config: AppConfig | None = None,
        discovery: EmulatorDiscoveryService | None = None,
        persistence: EmulatorPersistenceService | None = None,
        version_service: EmulatorVersionService | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.discovery = discovery or EmulatorDiscoveryService()
        self.persistence = persistence or EmulatorPersistenceService()
        self.version_service = version_service or EmulatorVersionService()

    def refresh(self) -> dict[str, EmulatorStatus]:
        """Redescobre instalações localmente, sem consultar releases remotos."""
        options = EmulatorDiscoveryOptions(
            mame_executable=self.config.mame_path,
            flycast_executable=self.config.flycast_path,
            supermodel_executable=self.config.supermodel_path,
            fbneo_executable=self.config.fbneo_path,
            mame_root=self.config.mame_dir,
            flycast_root=self.config.flycast_dir,
            supermodel_root=self.config.supermodel_dir,
            fbneo_root=self.config.fbneo_dir,
        )
        logger.info(
            "Emulator status: paths | mame=%s | flycast=%s | supermodel=%s | fbneo=%s",
            options.mame_executable,
            options.flycast_executable,
            options.supermodel_executable,
            options.fbneo_executable,
        )
        installations = self.discovery.discover_all(options)
        try:
            self.persistence.persist(installations.values())
        except Exception:
            logger.exception("Emulator status: falha ao persistir estado; mantendo descoberta em memória")
        statuses = self._to_statuses(installations)
        for name, status in statuses.items():
            logger.info(
                "Emulator status: %s | state=%s | executable=%s | root=%s | version=%s",
                name,
                status.status,
                status.executable,
                status.root,
                status.version,
            )
        return statuses

    def check_available_versions(self, statuses: dict[str, EmulatorStatus] | None = None) -> dict[str, EmulatorVersionInfo]:
        """Consulta os releases oficiais somente quando explicitamente solicitado.

        Este método é propositalmente separado de ``refresh()`` para que a
        abertura da Home nunca dependa de rede ou de uma API externa.
        """
        current = statuses or self.refresh()
        result: dict[str, EmulatorVersionInfo] = {}
        for name in ("mame", "flycast", "supermodel", "fbneo"):
            status = current.get(name)
            installed = status.version if status else None
            root = status.root if status else None
            result[name] = self.version_service.check(name, installed=installed, root=root)
            item = result[name]
            logger.info(
                "Emulator status: version check | emulator=%s | installed=%s | available=%s | state=%s | release=%s",
                name,
                item.installed,
                item.available,
                item.status,
                item.release_tag,
            )
        return result

    def _to_statuses(self, installations: dict[str, EmulatorInstallation]) -> dict[str, EmulatorStatus]:
        """Converte descoberta em modelos simples para a GUI.

        Quando o emulador não expõe uma versão local confiável, utiliza a
        última versão confirmada pelo próprio aplicativo durante uma instalação
        ou atualização. Isso é particularmente importante para Flycast e
        Supermodel, evitando perder na Home uma versão que já foi identificada
        no download apenas porque o executável não possui uma CLI de versão.
        """
        statuses: dict[str, EmulatorStatus] = {}
        for name, installation in installations.items():
            configs = tuple(
                {"name": cfg.name, "status": cfg.status, "generated": cfg.generated}
                for cfg in installation.configs
            )
            detected_version = installation.version or getattr(self.config, f"{name}_version", None)
            if installation.version is None and detected_version:
                logger.info(
                    "Emulator status: usando versão persistida | emulator=%s | version=%s",
                    name,
                    detected_version,
                )
            statuses[name] = EmulatorStatus(
                name,
                installation.executable,
                installation.root,
                detected_version,
                EmulatorStatusService._installation_status(installation),
                configs,
            )
        return statuses

    @staticmethod
    def _installation_status(installation: EmulatorInstallation) -> str:
        """Calcula o estado apresentado na Home."""
        if installation.executable is None:
            if any(cfg.status == "valid" for cfg in installation.configs):
                return "executable_missing"
            if any(cfg.status.startswith("corrupt") for cfg in installation.configs):
                return "configuration_corrupt"
            if any(cfg.status.startswith("missing") for cfg in installation.configs):
                return "configuration_missing"
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
