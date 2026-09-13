"""Diagnóstico visual e calibração de controles físicos do SERM V2."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..models.input_control import InputDeviceType
from ..services.controller_mode_service import ControllerModeService
from ..services.input_control_service import InputControlService
from ..services.mame_controller_mapping_service import MameControllerMappingService
from .controller_mapping_dialog import ControllerMappingDialog

logger = logging.getLogger(__name__)


class InputControlsPage(QWidget):
    """Apresenta inventário físico e permite calibrar seus inputs reais."""

    def __init__(self, parent=None, service: InputControlService | None = None) -> None:
        super().__init__(parent)
        self.service = service or InputControlService()
        self._mapped_profiles = {}
        self._mame_buttons: dict[str, QPushButton] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        toolbar = QFrame()
        toolbar.setObjectName("controlsToolbar")
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title = QLabel("Diagnóstico de controles")
        title.setObjectName("controlsTitle")
        subtitle = QLabel("Hardware detectado • identidade, modo, layout e calibração física")
        subtitle.setObjectName("controlsSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box, 1)
        self.refresh_button = QPushButton("↻  Detectar dispositivos")
        self.refresh_button.setObjectName("controlsRefresh")
        self.refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_button)
        root.addWidget(toolbar)
        self.status = QLabel("Nenhuma detecção executada nesta sessão.")
        self.status.setObjectName("controlsStatus")
        root.addWidget(self.status)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(8)
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)
        self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            "QFrame#controlsToolbar{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #111c2d,stop:1 #0d1727);border:1px solid #2a3b55;border-radius:9px;}"
            "QLabel#controlsTitle{color:#e7eef7;font-size:14px;font-weight:650;}QLabel#controlsSubtitle{color:#8fa5bb;font-size:8pt;}QLabel#controlsStatus{color:#8fa5bb;font-size:8pt;padding:2px 4px;}"
            "QPushButton#controlsRefresh{background:#172b42;color:#eaf5ff;border:1px solid #3e6d8b;border-radius:6px;padding:6px 11px;}QPushButton#controlsRefresh:hover{background:#1d3854;}"
            "QFrame#deviceCard{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #101c2c,stop:1 #0c1625);border:1px solid #293b54;border-radius:10px;}"
            "QFrame#deviceCard:hover{border:1px solid #42627e;}"
            "QLabel#deviceName{color:#edf4fb;font-size:11pt;font-weight:650;}QLabel#deviceMeta{color:#8fa5bb;font-size:8pt;}"
            "QLabel#deviceGood{color:#78d6b0;font-size:8pt;font-weight:600;}QLabel#deviceWarn{color:#e0c477;font-size:8pt;font-weight:600;}"
            "QLabel#deviceMode{color:#9bc9ff;font-size:8pt;font-weight:650;}QLabel#deviceBattery{color:#c7d6e6;font-size:8pt;font-weight:600;}"
            "QPushButton#mapButton{background:#162b3d;color:#dff5ff;border:1px solid #3e718c;border-radius:6px;padding:5px 9px;font-weight:600;}QPushButton#mapButton:hover{background:#1b3850;}"
            "QPushButton#mameButton{background:#183229;color:#dfffe9;border:1px solid #438265;border-radius:6px;padding:5px 9px;font-weight:600;}QPushButton#mameButton:hover{background:#1e4134;}QPushButton#mameButton:disabled{background:#111b20;color:#66777f;border-color:#29373d;}"
            "QProgressBar#batteryBar{height:7px;border:1px solid #31465f;border-radius:3px;background:#09111d;text-align:center;}"
            "QProgressBar#batteryBar::chunk{border-radius:2px;background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #4ca8ff,stop:1 #55d6c2);}"
        )

    def _clear_cards(self) -> None:
        self._mame_buttons.clear()
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _battery(self, device, box: QVBoxLayout) -> None:
        percent = device.metadata.get("battery_percent") if device.metadata else None
        state = str(device.metadata.get("battery_state", "")).replace("_", " ").strip() if device.metadata else ""
        if not isinstance(percent, int) or not 0 <= percent <= 100:
            return
        header = QHBoxLayout()
        header.setSpacing(6)
        label = QLabel(f"Bateria  {percent}%")
        label.setObjectName("deviceBattery")
        header.addWidget(label)
        if state and state not in {"unknown", "error"}:
            state_label = QLabel(state)
            state_label.setObjectName("deviceMeta")
            header.addWidget(state_label)
        header.addStretch(1)
        box.addLayout(header)
        bar = QProgressBar()
        bar.setObjectName("batteryBar")
        bar.setRange(0, 100)
        bar.setValue(percent)
        bar.setTextVisible(False)
        bar.setFixedHeight(7)
        box.addWidget(bar)

    def _open_mapper(self, device, model_id: str) -> None:
        dialog = ControllerMappingDialog(device, model_id, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            profile = dialog.profile()
            self._mapped_profiles[profile.profile_id] = profile
            self.status.setText(
                f"Mapeamento concluído: {len(profile.bindings)} entrada(s) associada(s) a {profile.name}."
            )
            button = self._mame_buttons.get(profile.profile_id)
            if button is not None:
                button.setEnabled(True)

    def _export_mame(self, profile) -> None:
        """Gera o primeiro perfil ctrlr M30 para teste direto no MAME."""
        if profile.metadata.get("physical_layout") != "8bitdo-m30":
            QMessageBox.information(self, "Perfil MAME", "A primeira integração direta está limitada ao 8BitDo M30.")
            return
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar perfil de controle do MAME",
            str(Path.home() / "m30_serm.cfg"),
            "MAME Controller (*.cfg)",
        )
        if not destination:
            return
        try:
            path = MameControllerMappingService.write_m30_ctrlr(profile, destination)
        except OSError as exc:
            QMessageBox.critical(self, "Perfil MAME", f"Não foi possível gravar o perfil:\n{exc}")
            return
        QMessageBox.information(
            self,
            "Perfil MAME gerado",
            f"Perfil criado em:\n{path}\n\nColoque o arquivo no ctrlrpath do MAME e use -ctrlr {path.stem}.",
        )
        self.status.setText(f"Perfil MAME gerado: {path.name} • 15 entradas M30, sem MODE/PAIR.")

    def _card(self, snapshot) -> QFrame:
        device = snapshot.device
        card = QFrame()
        card.setObjectName("deviceCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        box = QVBoxLayout(card)
        box.setContentsMargins(11, 10, 11, 10)
        box.setSpacing(5)

        header = QHBoxLayout()
        header.setSpacing(7)
        name = QLabel(device.name or "Dispositivo sem nome")
        name.setObjectName("deviceName")
        header.addWidget(name, 1)
        connection = device.connection.value if device.connection else "unknown"
        connection_label = QLabel(connection.upper())
        connection_label.setObjectName("deviceMode")
        header.addWidget(connection_label)
        box.addLayout(header)

        kind = device.device_type.value if isinstance(device.device_type, InputDeviceType) else str(device.device_type)
        vendor = f"{device.vendor_id:04X}" if device.vendor_id is not None else "----"
        product = f"{device.product_id:04X}" if device.product_id is not None else "----"
        meta = QLabel(f"{kind}  •  VID {vendor} / PID {product}")
        meta.setObjectName("deviceMeta")
        box.addWidget(meta)

        mode = ControllerModeService.identify(device)
        if mode is not None:
            confirmation = "confirmado" if mode.confirmed else "assinatura compatível"
            mode_label = QLabel(f"{mode.model_name}  •  {mode.mode_name}  •  {confirmation} ({mode.confidence}%)")
            mode_label.setObjectName("deviceMode")
            box.addWidget(mode_label)

        self._battery(device, box)

        layout = snapshot.layout
        profile = getattr(layout, "profile_kind", "unknown")
        buttons = getattr(layout, "buttons", 0)
        axes = getattr(layout, "axes", 0)
        hats = getattr(layout, "hats", 0)
        face_buttons = getattr(layout, "face_buttons", 0)
        detail = QLabel(f"Layout  {profile}  •  {buttons} botões ({face_buttons} face)  •  {axes} eixos  •  {hats} hats")
        detail.setObjectName("deviceMeta")
        box.addWidget(detail)

        model = getattr(snapshot.identification, "model", None)
        if model is not None:
            if getattr(layout, "has_six_face_buttons", False):
                label = QLabel("✓ 6 botões confirmados pelo catálogo")
                label.setObjectName("deviceGood")
                box.addWidget(label)
            label = QLabel(f"✓ Modelo: {model.model_name} ({snapshot.identification.confidence}%)")
            label.setObjectName("deviceGood")
            box.addWidget(label)

            actions = QHBoxLayout()
            actions.addStretch(1)
            map_button = QPushButton("⌘  Mapear inputs")
            map_button.setObjectName("mapButton")
            map_button.clicked.connect(lambda _checked=False, d=device, m=model.model_id: self._open_mapper(d, m))
            actions.addWidget(map_button)
            if model.model_id == "8bitdo-m30":
                profile_key = f"{device.hardware_key}:{model.model_id}"
                mapped = self._mapped_profiles.get(profile_key)
                mame_button = QPushButton("MAME  •  gerar ctrlr")
                mame_button.setObjectName("mameButton")
                mame_button.setEnabled(mapped is not None)
                mame_button.clicked.connect(
                    lambda _checked=False, key=profile_key: self._export_mame(self._mapped_profiles[key])
                )
                self._mame_buttons[profile_key] = mame_button
                actions.addWidget(mame_button)
            box.addLayout(actions)
        else:
            label = QLabel("○ Modelo específico não identificado; identidade física preservada")
            label.setObjectName("deviceWarn")
            box.addWidget(label)

        correlation = snapshot.correlation
        if correlation is not None:
            if correlation.ambiguous:
                label = QLabel(f"⚠ HID ↔ SDL3 ambíguo ({correlation.score})")
                label.setObjectName("deviceWarn")
            else:
                label = QLabel(f"✓ HID ↔ SDL3  {correlation.score}  •  {', '.join(correlation.reasons)}")
                label.setObjectName("deviceGood")
            box.addWidget(label)
        return card

    def refresh(self) -> None:
        self.refresh_button.setEnabled(False)
        self.status.setText("Detectando dispositivos…")
        try:
            snapshot = self.service.discover()
            self._clear_cards()
            for index, item in enumerate(snapshot.devices):
                self.grid.addWidget(self._card(item), index // 2, index % 2)
            self.status.setText(
                f"{len(snapshot.devices)} dispositivo(s) físico(s) • "
                f"{len(snapshot.logical_devices)} gamepad(s) SDL3 • "
                f"{len(snapshot.correlations)} correlação(ões)."
            )
        except Exception as exc:
            logger.exception("[INPUT] falha na detecção de controles")
            self.status.setText(f"Falha na detecção: {type(exc).__name__}: {exc}")
        finally:
            self.refresh_button.setEnabled(True)


__all__ = ["InputControlsPage"]