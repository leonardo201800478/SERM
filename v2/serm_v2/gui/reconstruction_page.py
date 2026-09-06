"""Página de configuração e execução da reconstrução do SERM V2."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..services.emulator_manager import EmulatorManager
from ..services.reconstruction_archive_service import ReconstructionArchiveError, ReconstructionArchiveService


class ReconstructionPage(QWidget):
    """Recebe o scan filtrado e configura a geração dos arquivos reconstruídos."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profile: Any | None = None
        self._scan_result: Any | None = None
        self._settings = QSettings("SERM", "SERM V2")

        layout = QVBoxLayout(self)
        title = QLabel("SERM V2 — Reconstrução de ROMs")
        title.setProperty("role", "title")
        layout.addWidget(title)
        description = QLabel(
            "A reconstrução recebe somente o resultado filtrado do scan. O empacotamento "
            "é feito pelo 7-Zip, permitindo escolher o formato de saída e o nível de "
            "compactação sem executar um novo scan."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        context_box = QGroupBox("Contexto recebido")
        context_layout = QVBoxLayout(context_box)
        self.profile_label = QLabel("Perfil: nenhum")
        self.scan_label = QLabel("Scan: ainda não executado")
        self.source_label = QLabel("Fonte: —")
        for label in (self.profile_label, self.scan_label, self.source_label):
            label.setWordWrap(True)
            context_layout.addWidget(label)
        layout.addWidget(context_box)

        archive_box = QGroupBox("Compactação da reconstrução")
        archive_layout = QFormLayout(archive_box)

        self.format_combo = QComboBox()
        self.format_combo.addItem("ZIP (.zip) — padrão", "zip")
        self.format_combo.addItem("7-Zip (.7z)", "7z")

        self.level_combo = QComboBox()
        self.level_combo.addItem("Store — sem compactação", "store")
        self.level_combo.addItem("Fastest", "fastest")
        self.level_combo.addItem("Fast", "fast")
        self.level_combo.addItem("Normal — padrão", "normal")
        self.level_combo.addItem("Maximum", "maximum")
        self.level_combo.addItem("Ultra", "ultra")

        self.seven_zip_label = QLabel()
        self.seven_zip_label.setWordWrap(True)
        self._refresh_7zip_status()

        archive_layout.addRow("Formato de saída:", self.format_combo)
        archive_layout.addRow("Nível de compactação:", self.level_combo)
        archive_layout.addRow("Ferramenta:", self.seven_zip_label)
        layout.addWidget(archive_box)

        action_box = QGroupBox("Planejamento")
        action_layout = QHBoxLayout(action_box)
        self.plan_button = QPushButton("GERAR PLANO DE RECONSTRUÇÃO")
        self.plan_button.setEnabled(False)
        self.execute_button = QPushButton("EXECUTAR RECONSTRUÇÃO")
        self.execute_button.setEnabled(False)
        action_layout.addWidget(self.plan_button)
        action_layout.addWidget(self.execute_button)
        action_layout.addStretch()
        layout.addWidget(action_box)

        self.status = QLabel(
            "Aguardando um resultado persistido do scan. Quando houver um scan filtrado, "
            "o plano usará as opções de compactação acima."
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()

        self.format_combo.currentIndexChanged.connect(self._archive_options_changed)
        self.level_combo.currentIndexChanged.connect(self._archive_options_changed)
        self._load_archive_settings()

    def _settings_prefix(self) -> str:
        if isinstance(self._profile, dict):
            profile_id = str(self._profile.get("profile_id", ""))
        else:
            profile_id = str(getattr(self._profile, "profile_id", "")) if self._profile is not None else ""
        return f"reconstruction/{profile_id or 'default'}"

    def _load_archive_settings(self) -> None:
        prefix = self._settings_prefix()
        fmt = str(self._settings.value(f"{prefix}/format", "zip"))
        level = str(self._settings.value(f"{prefix}/level", "normal"))
        self._select_data(self.format_combo, fmt)
        self._select_data(self.level_combo, level)

    def _save_archive_settings(self) -> None:
        prefix = self._settings_prefix()
        self._settings.setValue(f"{prefix}/format", self.format_combo.currentData())
        self._settings.setValue(f"{prefix}/level", self.level_combo.currentData())
        self._settings.sync()

    @staticmethod
    def _select_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _archive_options_changed(self) -> None:
        self._save_archive_settings()
        fmt = str(self.format_combo.currentData())
        level = str(self.level_combo.currentData())
        suffix = ".7z" if fmt == "7z" else ".zip"
        self.status.setText(
            f"Reconstrução configurada: {suffix} | compactação={level}. "
            "O scan original permanece inalterado."
        )

    def _refresh_7zip_status(self) -> None:
        executable = EmulatorManager.find_7zip()
        if executable is None:
            self.seven_zip_label.setText("7-Zip não encontrado")
            self.seven_zip_label.setProperty("state", "error")
        else:
            self.seven_zip_label.setText(str(executable))
            self.seven_zip_label.setProperty("state", "ok")

    def set_scan_context(self, profile: Any, scan_result: Any | None = None) -> None:
        """Recebe o perfil salvo e o resultado do scan filtrado."""
        self._profile = profile
        self._scan_result = scan_result
        if isinstance(profile, dict):
            profile_name = str(profile.get("name", "Perfil"))
            profile_id = str(profile.get("profile_id", ""))
            source = str(profile.get("source", ""))
            system = str(profile.get("system", ""))
        else:
            profile_name = str(getattr(profile, "name", "Perfil"))
            profile_id = str(getattr(profile, "profile_id", ""))
            source = str(getattr(profile, "source", ""))
            system = str(getattr(profile, "system", ""))
        self.profile_label.setText(f"Perfil: {profile_name}\nID: {profile_id}")
        self.source_label.setText(f"Fonte: {source} › {system}")
        self._load_archive_settings()
        self._refresh_7zip_status()
        if scan_result is None:
            self.scan_label.setText("Scan: preparado; aguardando resultado do scanner")
            self.plan_button.setEnabled(False)
            self.execute_button.setEnabled(False)
        else:
            self.scan_label.setText(f"Scan: resultado recebido — {scan_result}")
            self.plan_button.setEnabled(True)
            self.execute_button.setEnabled(False)

    def set_scan_result(self, scan_result: Any) -> None:
        """Atualiza a reconstrução quando o motor persistir o resultado do scan."""
        if self._profile is None:
            return
        self.set_scan_context(self._profile, scan_result)
        self.status.setText("Resultado do scan recebido. O próximo passo é gerar o plano de reconstrução.")

    def archive_configuration(self) -> dict[str, str]:
        """Retorna a configuração efetiva usada pelo futuro executor."""
        return {
            "format": str(self.format_combo.currentData()),
            "level": str(self.level_combo.currentData()),
        }

    @staticmethod
    def create_archive(files: list[str], output: str, *, base_dir: str | None = None, format: str = "zip", level: str = "normal") -> str:
        """Cria um arquivo reconstruído usando o 7-Zip."""
        try:
            return str(
                ReconstructionArchiveService.create(
                    files,
                    output,
                    base_dir=base_dir,
                    format=format,
                    level=level,
                )
            )
        except ReconstructionArchiveError:
            raise

    def refresh(self) -> None:
        """Mantém o contexto e atualiza a disponibilidade do 7-Zip."""
        self._refresh_7zip_status()


__all__ = ["ReconstructionPage"]
