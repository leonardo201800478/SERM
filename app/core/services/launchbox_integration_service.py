"""Compatibilidade pública da integração LaunchBox.

A implementação foi separada para permitir evolução do catálogo sem alterar
os imports existentes da GUI.
"""
from app.core.services.launchbox_integration_service_v2 import (
    LaunchBoxCoreOption,
    LaunchBoxInstallation,
    LaunchBoxIntegrationService,
    LaunchBoxSystem,
)

__all__ = [
    "LaunchBoxIntegrationService",
    "LaunchBoxSystem",
    "LaunchBoxCoreOption",
    "LaunchBoxInstallation",
]
