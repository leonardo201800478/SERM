"""Diagnóstico visual de controles físicos do SERM V2."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from ..models.input_control import InputDeviceType
from ..services.input_control_service import InputControlService

logger = logging.getLogger(__name__)


class InputControlsPage(QWidget):
    """Apresenta o inventário físico sem interferir no caminho do emulador."""

    def __init__(self, parent=None, service: InputControlService | None = None) -> None:
        super().__init__(parent)
        self.service = service or InputControlService()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(8)
        toolbar = QFrame(); toolbar.setObjectName("controlsToolbar")
        layout = QHBoxLayout(toolbar); layout.setContentsMargins(10, 8, 10, 8); layout.setSpacing(8)
        title_box = QVBoxLayout(); title_box.setSpacing(1)
        title = QLabel("Diagnóstico de controles"); title.setObjectName("controlsTitle")
        subtitle = QLabel("Hardware detectado pelo SERM • sem encaminhamento de eventos"); subtitle.setObjectName("controlsSubtitle")
        title_box.addWidget(title); title_box.addWidget(subtitle); layout.addLayout(title_box, 1)
        self.refresh_button = QPushButton("↻  Detectar dispositivos"); self.refresh_button.setObjectName("controlsRefresh")
        self.refresh_button.clicked.connect(self.refresh); layout.addWidget(self.refresh_button); root.addWidget(toolbar)
        self.status = QLabel("Nenhuma detecção executada nesta sessão."); self.status.setObjectName("controlsStatus"); root.addWidget(self.status)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget(); self.grid = QGridLayout(self.container); self.grid.setContentsMargins(0, 0, 0, 0); self.grid.setHorizontalSpacing(8); self.grid.setVerticalSpacing(8)
        self.scroll.setWidget(self.container); root.addWidget(self.scroll, 1); self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            "QFrame#controlsToolbar{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #111c2d,stop:1 #0d1727);border:1px solid #2a3b55;border-radius:9px;}"
            "QLabel#controlsTitle{color:#e7eef7;font-size:14px;font-weight:650;}QLabel#controlsSubtitle{color:#8fa5bb;font-size:8pt;}QLabel#controlsStatus{color:#8fa5bb;font-size:8pt;padding:2px 4px;}"
            "QPushButton#controlsRefresh{background:#172b42;color:#eaf5ff;border:1px solid #3e6d8b;border-radius:6px;padding:6px 11px;}QPushButton#controlsRefresh:hover{background:#1d3854;}"
            "QFrame#deviceCard{background:#0d1726;border:1px solid #293b54;border-radius:9px;}QLabel#deviceName{color:#e8f0f8;font-size:11pt;font-weight:650;}QLabel#deviceMeta{color:#8fa5bb;font-size:8pt;}QLabel#deviceGood{color:#78d6b0;font-size:8pt;font-weight:600;}QLabel#deviceWarn{color:#e0c477;font-size:8pt;font-weight:600;}")

    def _clear_cards(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None: widget.deleteLater()

    def _card(self, snapshot) -> QFrame:
        device = snapshot.device
        card = QFrame(); card.setObjectName("deviceCard"); card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        box = QVBoxLayout(card); box.setContentsMargins(11, 10, 11, 10); box.setSpacing(4)
        name = QLabel(device.name or "Dispositivo sem nome"); name.setObjectName("deviceName"); box.addWidget(name)
        kind = device.device_type.value if isinstance(device.device_type, InputDeviceType) else str(device.device_type)
        connection = device.connection.value if device.connection else "unknown"
        vendor = f"{device.vendor_id:04X}" if device.vendor_id is not None else "----"
        product = f"{device.product_id:04X}" if device.product_id is not None else "----"
        meta = QLabel(f"{kind}  •  {connection}  •  VID {vendor} / PID {product}"); meta.setObjectName("deviceMeta"); box.addWidget(meta)
        identity = QLabel(f"Identidade: {device.hardware_key}"); identity.setObjectName("deviceMeta"); identity.setWordWrap(True); box.addWidget(identity)
        layout = snapshot.layout; profile = getattr(layout, "profile_kind", "unknown"); buttons = getattr(layout, "button_count", 0); axes = getattr(layout, "axis_count", 0); hats = getattr(layout, "hat_count", 0)
        detail = QLabel(f"Layout: {profile}  •  {buttons} botões  •  {axes} eixos  •  {hats} hats"); detail.setObjectName("deviceMeta"); box.addWidget(detail)
        if getattr(layout, "has_six_face_buttons", False):
            label = QLabel("✓ Seis botões de face detectados"); label.setObjectName("deviceGood"); box.addWidget(label)
        if snapshot.identification.model is not None:
            label = QLabel(f"✓ Modelo: {snapshot.identification.model.model_name} ({snapshot.identification.confidence}%)"); label.setObjectName("deviceGood"); box.addWidget(label)
        else:
            label = QLabel("○ Modelo específico não identificado; identidade física preservada"); label.setObjectName("deviceWarn"); box.addWidget(label)
        return card

    def refresh(self) -> None:
        self.refresh_button.setEnabled(False)
        self.status.setText("Detectando dispositivos…")
        try:
            snapshot = self.service.discover()
            self._clear_cards()
            for index, item in enumerate(snapshot.devices): self.grid.addWidget(self._card(item), index // 2, index % 2)
            self.status.setText(f"{len(snapshot.devices)} dispositivo(s) físico(s) detectado(s). A leitura foi realizada somente para diagnóstico.")
        except Exception as exc:
            logger.exception("[INPUT] falha na detecção de controles")
            self.status.setText(f"Falha na detecção: {type(exc).__name__}: {exc}")
        finally:
            self.refresh_button.setEnabled(True)


__all__ = ["InputControlsPage"]
