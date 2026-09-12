"""Orquestração do subsistema de controles da V2.

Este serviço reúne descoberta HID, SDL3, correlação, identificação, análise de
layout e comparação com os requisitos do MAME. Não altera configurações do
emulador e não injeta eventos de entrada.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.input_control import ControlProfile, InputDevice
from .controller_catalog_service import ControllerCatalogService, ControllerIdentification
from .input_device_correlation_service import DeviceCorrelation, InputDeviceCorrelationService
from .input_device_service import InputDeviceService
from .input_layout_analyzer import InputLayoutAnalyzer, LayoutSummary
from .mame_control_service import MameInputRequirements, MameControlService
from .sdl3_input_service import SDL3InputService
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
        mame_control_service: MameControlService | None = None,
        sdl3_input_service: SDL3InputService | None = None,
    ) -> None:
        self.device_service = device_service or InputDeviceService()
        self.correlation_service = correlation_service or InputDeviceCorrelationService()
        self.catalog_service = catalog_service or ControllerCatalogService.default()
        self.layout_analyzer = layout_analyzer or InputLayoutAnalyzer()
        self.mapper = mapper or SystemControlMapper()
        self.mame_control_service = mame_control_service or MameControlService()
        self.sdl3_input_service = sdl3_input_service or SDL3InputService()

    def discover(self, logical_devices: tuple[InputDevice, ...] | None = None) -> InputControlSnapshot:
        """Descobre HID e SDL3 e correlaciona as duas visões do hardware.

        Se SDL3 não estiver disponível ou não puder inicializar, a descoberta
        HID continua disponível para diagnóstico físico.
        """
        physical = self.device_service.enumerate_hid()
        if logical_devices is None:
            logical_devices = self._enumerate_sdl3()
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

    def _enumerate_sdl3(self) -> tuple[InputDevice, ...]:
        try:
            self.sdl3_input_service.initialize()
            return self.sdl3_input_service.enumerate()
        except (ImportError, RuntimeError, OSError):
            return ()

    def map_mame(
        self,
        requirements: MameInputRequirements,
        device: InputDevice,
        profile: ControlProfile | None = None,
    ) -> SystemControlMapping:
        """Compara um dispositivo com requisitos já extraídos do MAME."""
        return self.mapper.map_mame(requirements, device, profile)

    def read_mame_machine(self, xml_path: str, machine_name: str) -> MameInputRequirements | None:
        """Lê somente a máquina solicitada de um ListXML potencialmente grande."""
        return self.mame_control_service.read_machine(xml_path, machine_name)


__all__ = ["InputControlService", "InputControlSnapshot", "InputDeviceSnapshot"]
