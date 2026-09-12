"""Calibração visual de controles físicos do SERM V2."""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout

from ..models.input_control import ControlProfile, LogicalControl
from ..services.controller_input_probe_service import ControllerInputProbeService, ProbeEventType

logger = logging.getLogger(__name__)


class ControllerMappingDialog(QDialog):
    """Guia o usuário na associação elemento físico -> controle lógico."""

    def __init__(self, device, model_id: str, parent=None) -> None:
        super().__init__(parent)
        self.device = device
        self.model_id = model_id
        self.probe = ControllerInputProbeService()
        self.sequence = ControllerInputProbeService.default_sequence(model_id)
        self.position = 0
        self.bindings: dict[LogicalControl, tuple[str, ...]] = {}
        self._rows: list[QListWidgetItem] = []
        self.setWindowTitle(f"Mapear inputs — {device.name}")
        self.setMinimumSize(620, 500)
        self._build_ui()
        self._start_probe()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)
        title = QLabel("Mapeamento físico")
        title.setStyleSheet("font-size:15px;font-weight:650;")
        root.addWidget(title)
        vendor = f"{self.device.vendor_id:04X}" if self.device.vendor_id is not None else "----"
        product = f"{self.device.product_id:04X}" if self.device.product_id is not None else "----"
        self.info = QLabel(f"{self.device.name}  •  VID {vendor} / PID {product}")
        self.info.setStyleSheet("color:#8fa5bb;font-size:8pt;")
        root.addWidget(self.info)
        self.instruction = QLabel()
        self.instruction.setStyleSheet("font-size:12px;font-weight:600;padding:8px 4px;")
        self.instruction.setWordWrap(True)
        root.addWidget(self.instruction)
        self.detected = QLabel("Aguardando entrada física…")
        self.detected.setStyleSheet("color:#78d6b0;font-size:9pt;font-weight:600;")
        root.addWidget(self.detected)
        self.list = QListWidget()
        self.list.setStyleSheet("QListWidget{border:1px solid #293b54;border-radius:8px;background:#0c1625;} QListWidget::item{padding:5px;} QListWidget::item:selected{background:#172b42;}")
        for control in self.sequence:
            item = QListWidgetItem(f"○  {ControllerInputProbeService.logical_label(control)}")
            self.list.addItem(item)
            self._rows.append(item)
        root.addWidget(self.list, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.retry = QPushButton("Refazer atual")
        self.retry.clicked.connect(self._retry_current)
        buttons.addWidget(self.retry)
        self.cancel = QPushButton("Cancelar")
        self.cancel.clicked.connect(self.reject)
        buttons.addWidget(self.cancel)
        self.finish = QPushButton("Concluir mapeamento")
        self.finish.setEnabled(False)
        self.finish.clicked.connect(self._finish)
        buttons.addWidget(self.finish)
        root.addLayout(buttons)

    def _start_probe(self) -> None:
        instance_id = self.device.metadata.get("instance_id") if self.device.metadata else None
        if instance_id is None:
            self.instruction.setText("Este dispositivo não possui um instance_id SDL3 disponível para calibração.")
            self.retry.setEnabled(False)
            return
        try:
            self.probe.start(int(instance_id))
        except Exception as exc:
            logger.exception("[INPUT] falha ao iniciar calibração")
            self.instruction.setText(f"Não foi possível abrir o dispositivo no SDL3: {exc}")
            self.retry.setEnabled(False)
            return
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._poll)
        self.timer.start()
        self._update_instruction()

    def _poll(self) -> None:
        for event in self.probe.poll():
            if self.position >= len(self.sequence):
                return
            control = self.sequence[self.position]
            # D-pad é calibrado por direção; qualquer evento de hat nessa etapa
            # é aceito. Para botões, só Button/axis/hot são associados ao papel.
            if control.name.startswith("DPAD_") and event.element_type is not ProbeEventType.HAT:
                continue
            self.bindings[control] = (event.element_id,)
            self._rows[self.position].setText(f"✓  {ControllerInputProbeService.logical_label(control)}  →  {event.display}")
            self.detected.setText(f"Detectado: {event.display} ({event.element_id})")
            self.position += 1
            if self.position < len(self.sequence):
                self.list.setCurrentRow(self.position)
                self._update_instruction()
            else:
                self.instruction.setText("Mapeamento completo. Revise a lista e conclua.")
                self.finish.setEnabled(True)
                self.timer.stop()
                self.probe.stop()
                break

    def _update_instruction(self) -> None:
        if self.position >= len(self.sequence):
            return
        control = self.sequence[self.position]
        label = ControllerInputProbeService.logical_label(control)
        self.instruction.setText(f"Pressione ou mova agora: {label}")
        self.list.setCurrentRow(self.position)

    def _retry_current(self) -> None:
        if self.position >= len(self.sequence):
            return
        self.bindings.pop(self.sequence[self.position], None)
        try:
            if not self.probe.active:
                instance_id = self.device.metadata.get("instance_id")
                if instance_id is not None:
                    self.probe.start(int(instance_id))
            self.finish.setEnabled(False)
            self._update_instruction()
        except Exception as exc:
            self.detected.setText(f"Falha ao reabrir: {exc}")

    def _finish(self) -> None:
        self.probe.stop()
        self.accept()

    def profile(self) -> ControlProfile:
        return ControlProfile(
            profile_id=f"{self.device.hardware_key}:{self.model_id}",
            name=f"{self.device.name} — {self.model_id}",
            device_id=self.device.hardware_key,
            bindings=dict(self.bindings),
            metadata={"calibration": "interactive", "source": "SDL3 raw joystick"},
        )

    def reject(self) -> None:
        self.probe.stop()
        timer = getattr(self, "timer", None)
        if timer is not None:
            timer.stop()
        super().reject()

    def closeEvent(self, event) -> None:
        self.probe.stop()
        timer = getattr(self, "timer", None)
        if timer is not None:
            timer.stop()
        super().closeEvent(event)


__all__ = ["ControllerMappingDialog"]
