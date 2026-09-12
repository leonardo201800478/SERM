"""Monitor visual de conexão/desconexão de controles físicos."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QMessageBox, QWidget

from ..models.input_control import InputDevice, InputDeviceType
from ..services.controller_mode_service import ControllerModeMatch, ControllerModeService
from ..services.input_device_service import InputDeviceService

logger = logging.getLogger(__name__)


class InputConnectionMonitor(QObject):
    """Detecta mudanças de controles por polling HID, sem injetar eventos."""

    INTERVAL_MS = 1500

    def __init__(self, parent: QWidget, device_service: InputDeviceService | None = None) -> None:
        super().__init__(parent)
        self.parent_widget = parent
        self.device_service = device_service or InputDeviceService()
        self.timer = QTimer(self)
        self.timer.setInterval(self.INTERVAL_MS)
        self.timer.timeout.connect(self.poll)
        self._known: dict[str, InputDevice] = {}
        self._baseline_ready = False

    @staticmethod
    def _is_controller(device: InputDevice) -> bool:
        if device.device_type in {
            InputDeviceType.GAMEPAD,
            InputDeviceType.ARCADE_STICK,
            InputDeviceType.FIGHTING_CONTROLLER,
            InputDeviceType.STEERING_WHEEL,
            InputDeviceType.FLIGHT_CONTROLLER,
            InputDeviceType.DANCE_PAD,
        }:
            return True
        return device.usage_page == 1 and device.usage in {4, 5}

    def _inventory(self) -> dict[str, InputDevice]:
        devices = self.device_service.enumerate_hid()
        inventory: dict[str, InputDevice] = {}
        for device in devices:
            if not self._is_controller(device):
                continue
            inventory[device.hardware_key] = device
        return inventory

    def start(self) -> None:
        """Cria a linha de base silenciosa e inicia a observação."""
        try:
            self._known = self._inventory()
            self._baseline_ready = True
            self.timer.start()
            logger.info("[INPUT][HOTPLUG] monitor iniciado | controles=%d", len(self._known))
        except Exception:
            logger.exception("[INPUT][HOTPLUG] falha ao criar linha de base")

    def stop(self) -> None:
        self.timer.stop()

    def poll(self) -> None:
        try:
            current = self._inventory()
            if not self._baseline_ready:
                self._known = current
                self._baseline_ready = True
                return

            connected = [current[key] for key in current.keys() - self._known.keys()]
            disconnected = [self._known[key] for key in self._known.keys() - current.keys()]
            self._known = current

            for device in connected:
                self._notify(device, connected=True)
            for device in disconnected:
                self._notify(device, connected=False)
        except Exception:
            logger.exception("[INPUT][HOTPLUG] falha durante polling")

    def _notify(self, device: InputDevice, *, connected: bool) -> None:
        state = "conectado" if connected else "desconectado"
        match = ControllerModeService.identify_m30(device)
        logger.info(
            "[INPUT][HOTPLUG] %s | name=%r | VID=%04X | PID=%04X | connection=%s | m30=%s",
            state,
            device.name,
            device.vendor_id or 0,
            device.product_id or 0,
            device.connection.value,
            match.mode_name if match else "-",
        )
        if connected:
            self._show_connected(device, match)
        else:
            self._show_disconnected(device, match)

    def _show_connected(self, device: InputDevice, match: ControllerModeMatch | None) -> None:
        box = QMessageBox(self.parent_widget)
        box.setWindowTitle("Controle conectado")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(self._headline(device, match, connected=True))
        box.setInformativeText(self._connection_details(device, match))
        if match is not None:
            box.setDetailedText(self._m30_details(match))
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.show()
        box.raise_()
        box.activateWindow()
        self._keep_dialog(box)

    def _show_disconnected(self, device: InputDevice, match: ControllerModeMatch | None) -> None:
        box = QMessageBox(self.parent_widget)
        box.setWindowTitle("Controle desconectado")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(self._headline(device, match, connected=False))
        box.setInformativeText(self._connection_details(device, match))
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.show()
        box.raise_()
        box.activateWindow()
        self._keep_dialog(box)

    @staticmethod
    def _keep_dialog(dialog: QMessageBox) -> None:
        # Mantém a referência até o usuário fechar o popup sem bloquear o
        # loop principal da aplicação.
        dialog.setAttribute(dialog.WidgetAttribute.WA_DeleteOnClose, True)
        setattr(dialog, "_serm_hotplug_dialog", True)
        dialog.destroyed.connect(lambda: None)

    @staticmethod
    def _headline(device: InputDevice, match: ControllerModeMatch | None, *, connected: bool) -> str:
        action = "conectado" if connected else "desconectado"
        if match is None:
            return f"{device.name or 'Controle'} {action}."
        confirmation = "confirmado" if match.confirmed else "assinatura compatível"
        return f"{match.model_name} — {match.mode_name} ({confirmation}) {action}."

    @staticmethod
    def _connection_details(device: InputDevice, match: ControllerModeMatch | None) -> str:
        vendor = f"{device.vendor_id:04X}" if device.vendor_id is not None else "----"
        product = f"{device.product_id:04X}" if device.product_id is not None else "----"
        details = [
            f"Conexão: {device.connection.value}",
            f"VID/PID: {vendor}:{product}",
        ]
        if match is not None:
            details.append(f"Modo detectado: {match.mode_name} • confiança {match.confidence}%")
            if not match.confirmed:
                details.append("A assinatura é compartilhada com outros controles; confirme o modelo se necessário.")
        return "\n".join(details)

    @staticmethod
    def _m30_details(match: ControllerModeMatch) -> str:
        instructions = ControllerModeService.m30_instructions()
        lines = [
            "COMANDOS DO 8BITDO M30",
            "",
            *instructions,
            "",
            f"Modo atual: {match.mode_name}",
            f"Assinatura: {match.signature}",
            f"Indicador: {match.led_hint}",
            "",
            "O SERM apenas identifica o modo; não envia comandos ao controle e não cria driver virtual.",
        ]
        return "\n".join(lines)


__all__ = ["InputConnectionMonitor"]
