"""Widget de teste rápido para HLSL/GLSL da aba de configurações MAME."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
)

from app.config.app_config import AppConfig
from app.mame.mame_ini_editor import resolve_mame_ini
from app.mame.mame_shader_test import MameShaderTestRunner


def _resolve_executable(config: AppConfig) -> Path | None:
    """Resolve mame.exe aceitando tanto caminho de executável quanto pasta."""
    if not config.mame_path:
        return None
    path = Path(config.mame_path)
    if path.is_file():
        return path
    candidate = path / "mame.exe"
    return candidate if candidate.is_file() else None


class ShaderTestDialog(QDialog):
    """Solicita a machine e duração do teste e executa o MAME isoladamente."""

    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self.tab = tab
        self.setWindowTitle("Teste rápido de shaders")
        self.setMinimumWidth(420)
        form = QFormLayout(self)
        self.machine = QLineEdit("pacman")
        self.seconds = QSpinBox()
        self.seconds.setRange(5, 300)
        self.seconds.setValue(30)
        form.addRow("Machine (short name)", self.machine)
        form.addRow("Duração (segundos)", self.seconds)
        note = QLineEdit("O teste usa uma cópia temporária do mame.ini e não altera o original.")
        note.setReadOnly(True)
        form.addRow("", note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class ShaderTestController:
    """Integra o botão de teste, ciclo de vida do processo e atualização da GUI."""

    def __init__(self, tab):
        self.tab = tab
        self.runner: MameShaderTestRunner | None = None
        self.button = QPushButton("Testar shaders rapidamente")
        self.stop_button = QPushButton("Parar teste")
        self.stop_button.setEnabled(False)
        row = QHBoxLayout()
        row.addWidget(self.button)
        row.addWidget(self.stop_button)
        self.tab.layout().addLayout(row)
        self.button.clicked.connect(self.start)
        self.stop_button.clicked.connect(self.stop)
        self.timer = QTimer(self.tab)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self._poll)

    def start(self) -> None:
        """Valida caminhos, coleta a configuração atual e inicia o teste."""
        config = AppConfig()
        executable = _resolve_executable(config)
        ini_path = resolve_mame_ini(config.mame_path, config.ini_path)
        if executable is None:
            QMessageBox.warning(self.tab, "Teste de shaders", "Configure o executável do MAME antes de testar.")
            return
        if ini_path is None or not ini_path.is_file():
            QMessageBox.warning(self.tab, "Teste de shaders", "Nenhum mame.ini válido foi encontrado.")
            return
        dialog = ShaderTestDialog(self.tab, self.tab)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.runner = MameShaderTestRunner(executable, ini_path)
            self.runner.start(dialog.machine.text(), self.tab._collect_values(), dialog.seconds.value())
        except (OSError, ValueError, RuntimeError) as exc:
            self.runner = None
            QMessageBox.critical(self.tab, "Teste de shaders", str(exc))
            return
        self.button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.tab._set_status(f"Teste de shaders em execução: {dialog.machine.text().strip()} ({dialog.seconds.value()}s).")
        self.timer.start()

    def stop(self) -> None:
        """Encerra imediatamente o MAME de teste e libera os temporários."""
        if self.runner:
            self.runner.stop()
        self.runner = None
        self.timer.stop()
        self.button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.tab._set_status("Teste de shaders encerrado.")

    def _poll(self) -> None:
        """Detecta automaticamente o encerramento normal do MAME."""
        if self.runner is None:
            return
        code = self.runner.poll()
        if code is None:
            return
        self.runner = None
        self.timer.stop()
        self.button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.tab._set_status(f"Teste de shaders finalizado (código {code}).")

    def close(self) -> None:
        """Encerra o processo antes da aba/janela ser destruída."""
        self.stop()


def install_shader_test(tab) -> ShaderTestController:
    """Instala o controlador na aba sem duplicar lógica de configuração MAME."""
    controller = ShaderTestController(tab)
    tab.shader_test_controller = controller
    return controller
