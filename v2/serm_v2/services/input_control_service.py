"""Orquestração do subsistema de controles da V2.

Este serviço reúne descoberta, correlação, identificação, análise de layout e
comparação com os requisitos do MAME. Não altera configurações do emulador e
não injeta eventos de entrada.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.input_control import ControlProfile, InputDevice
from .controller_catalog_service import ControllerCatalogService, ControllerIdentification
from .input_device_correlation_service import DeviceCorrelation, InputDeviceCorrelationService
from .input_device_service import InputDeviceService
from .input_layout_analyzer import InputLayoutAnalyzer, LayoutSummary
from .mame_control_service import MameControlRequirementsParser, MameInputRequirements
from .system_control_mapper import SystemControlMapper, SystemControlMapping


@dataclass(frozen=True, slots=True)
class InputDeviceSnapshot:
    """Visão consolidada de um dispositivo físico descoberto."""

    device: InputDevice
    layout: LayoutSummary
    identification: ControllerIdentification
    correlation: DeviceCorrelation | None = None


@dataclass(frozen=True, slots=True)
class InputControlSnapshot:
    """Inventário atual das entradas disponíveis no sistema."""

    physical_devices: tuple[InputDevice, ...]
    logical_devices: tuple[InputDevice, ...]
    devices: tuple[InputDeviceSnapshot, ...]
    correlations: tuple[DeviceCorrelation, ...]


class InputControlService:
    """Fachada do pipeline de descoberta e análise de controles."""

    def __init__(
        self,
        device_service: InputDeviceService | None = None,
        correlation_service: InputDeviceCorrelationService | None = None,
        catalog_service: ControllerCatalogService | None = None,
        layout_analyzer: InputLayoutAnalyzer | None = None,
        mapper: SystemControlMapper | None = None,
    ) -> None:
        self.device_service = device_service or InputDeviceService()
        self.correlation_service = correlation_service or InputDeviceCorrelationService()
        self.catalog_service = catalog_service or ControllerCatalogService.default()
        self.layout_analyzer = layout_analyzer or InputLayoutAnalyzer()
        self.mapper = mapper or SystemControlMapper()

    def discover(self, logical_devices: tuple[InputDevice, ...] = ()) -> InputControlSnapshot:
        """Descobre hardware HID e o correlaciona com dispositivos SDL já obtidos."""
        physical = self.device_service.enumerate_hid()
        correlations = self.correlation_service.correlate(physical, logical_devices)
        by_physical = {item.physical.device_id: item for item in correlations}
        snapshots = tuple(
            InputDeviceSnapshot(
                device=device,
                layout=self.layout_analyzer.analyze(device),
                identification=self.catalog_service.identify(device),
                correlation=by_physical.get(device.device_id),
            )
            for device in physical
        )
        return InputControlSnapshot(physical, logical_devices, snapshots, correlations)

    def map_mame(
        self,
        requirements: MameInputRequirements,
        device: InputDevice,
        profile: ControlProfile | None = None,
    ) -> SystemControlMapping:
        """Compara um dispositivo com os requisitos já extraídos do MAME."""
        return self.mapper.map_mame(requirements, device, profile)

    @staticmethod
    def parse_mame_requirements(xml_path: str) -> tuple[MameInputRequirements, ...]:
        """Expõe o parser de requisitos sem acoplar a GUI ao parser XML."""
        return tuple(MameControlRequirementsParser().parse_file(xml_path))


__all__ = ["InputControlService", "InputControlSnapshot", "InputDeviceSnapshot"]
