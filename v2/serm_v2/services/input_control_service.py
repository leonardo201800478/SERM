"""Orquestração do subsistema de controles da V2.

Este serviço reúne descoberta HID, SDL3, correlação, identificação, análise de
layout e comparação com os requisitos do MAME. Não altera configurações do
emulador e não injeta eventos de entrada.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace

from ..models.input_control import ControlProfile, InputDevice
from .controller_catalog_service import ControllerCatalogService, ControllerIdentification
from .input_device_correlation_service import DeviceCorrelation, InputDeviceCorrelationService
from .input_device_service import InputDeviceService
from .input_layout_analyzer import InputLayoutAnalyzer, LayoutSummary
from .mame_control_service import MameInputRequirements, MameControlService
from .sdl3_input_service import SDL3InputService
from .system_control_mapper import SystemControlMapper, SystemControlMapping

logger = logging.getLogger(__name__)
input_logger = logging.getLogger("SERM.INPUT")


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
        self._sdl3_initialized = False
        self._diagnostic_sequence = 0

    def discover(self, logical_devices: tuple[InputDevice, ...] | None = None) -> InputControlSnapshot:
        """Descobre HID e SDL3 e correlaciona as duas visões do hardware."""
        self._diagnostic_sequence += 1
        scan_id = self._diagnostic_sequence
        physical = self.device_service.enumerate_hid()
        if logical_devices is None:
            logical_devices = self._enumerate_sdl3()
        correlations = self.correlation_service.correlate(physical, logical_devices)
        self._log_discovery_diagnostics(scan_id, physical, logical_devices, correlations)
        by_physical = {item.physical.device_id: item for item in correlations}

        snapshots: list[InputDeviceSnapshot] = []
        for device in physical:
            identification = self.catalog_service.identify(device)
            layout = self.layout_analyzer.analyze(device)
            layout = self._apply_catalog_layout(layout, identification)
            snapshots.append(
                InputDeviceSnapshot(
                    device=device,
                    layout=layout,
                    identification=identification,
                    correlation=by_physical.get(device.device_id),
                )
            )

        return InputControlSnapshot(physical, logical_devices, tuple(snapshots), correlations)

    @staticmethod
    def _apply_catalog_layout(
        layout: LayoutSummary,
        identification: ControllerIdentification,
    ) -> LayoutSummary:
        """Completa o layout quando o catálogo tem uma expectativa verificada.

        O serviço principal usa ``ControllerIdentification.model``. Fakes de
        testes e integrações legadas podem expor somente outros metadados; nesse
        caso o layout observado é preservado exatamente como foi produzido pelo
        analisador, sem aplicar suposições.
        """
        model = getattr(identification, "model", None)
        if model is None:
            return layout

        changes: dict[str, object] = {}
        if getattr(layout, "buttons", 0) == 0 and model.expected_face_buttons is not None:
            changes["buttons"] = model.expected_face_buttons
            changes["face_buttons"] = model.expected_face_buttons
            changes["has_six_face_buttons"] = model.expected_face_buttons >= 6
            changes["profile_kind"] = (
                "six-button-gamepad" if model.expected_face_buttons >= 6 else layout.profile_kind
            )
        if getattr(layout, "axes", 0) == 0 and model.expected_axes is not None:
            changes["axes"] = model.expected_axes
        return replace(layout, **changes) if changes else layout

    def _log_discovery_diagnostics(
        self,
        scan_id: int,
        physical_devices: tuple[InputDevice, ...],
        logical_devices: tuple[InputDevice, ...],
        correlations: tuple[DeviceCorrelation, ...],
    ) -> None:
        """Registra uma fotografia completa de cada detecção para testes físicos.

        O diagnóstico é somente leitura. Ele preserva VID/PID, nome, fabricante,
        produto, versão, conexão, caminho, GUID SDL3 e correlação, permitindo
        comparar o mesmo controlador em diferentes modos de entrada sem inferir
        o modelo a partir de um VID compartilhado.
        """
        input_logger.info(
            "[INPUT][SCAN %03d] início | HID=%d | SDL3=%d | correlações=%d",
            scan_id,
            len(physical_devices),
            len(logical_devices),
            len(correlations),
        )
        for index, device in enumerate(physical_devices, start=1):
            input_logger.info(
                "[INPUT][SCAN %03d][HID %03d] name=%r | manufacturer=%r | product=%r | "
                "VID=%s | PID=%s | version=%s | connection=%s | bus_type=%s | "
                "usage_page=%s | usage=%s | interface=%s | serial=%r | path=%r | device_id=%r",
                scan_id,
                index,
                device.name,
                device.manufacturer,
                device.product,
                self._hex_id(device.vendor_id),
                self._hex_id(device.product_id),
                device.version,
                getattr(device.connection, "value", device.connection),
                device.bus_type,
                device.usage_page,
                device.usage,
                device.interface_number,
                device.serial,
                device.path,
                device.device_id,
            )

        for index, device in enumerate(logical_devices, start=1):
            input_logger.info(
                "[INPUT][SCAN %03d][SDL3 %03d] name=%r | VID=%s | PID=%s | version=%s | "
                "GUID=%r | path=%r | device_id=%r | instance_id=%r",
                scan_id,
                index,
                device.name,
                self._hex_id(device.vendor_id),
                self._hex_id(device.product_id),
                device.version,
                device.sdl_guid,
                device.path,
                device.device_id,
                device.metadata.get("instance_id") if device.metadata else None,
            )

        for index, correlation in enumerate(correlations, start=1):
            input_logger.info(
                "[INPUT][SCAN %03d][CORR %03d] physical=%r -> logical=%r | score=%s | "
                "ambiguous=%s | reasons=%s",
                scan_id,
                index,
                correlation.physical.device_id,
                correlation.logical.device_id,
                correlation.score,
                correlation.ambiguous,
                ",".join(correlation.reasons),
            )
        input_logger.info("[INPUT][SCAN %03d] fim", scan_id)

    @staticmethod
    def _hex_id(value: int | None) -> str:
        return f"0x{value:04X}" if value is not None else "-"

    def _enumerate_sdl3(self) -> tuple[InputDevice, ...]:
        """Inicializa SDL3 uma vez por serviço e retorna gamepads disponíveis."""
        try:
            if not self._sdl3_initialized:
                self.sdl3_input_service.initialize()
                self._sdl3_initialized = True
            return self.sdl3_input_service.enumerate()
        except (ImportError, RuntimeError, OSError) as exc:
            logger.warning("[INPUT] SDL3 indisponível durante descoberta: %s", exc)
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
