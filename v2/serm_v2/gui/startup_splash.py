"""Splash screen 16:9 do SERM V2."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QVBoxLayout, QWidget


class StartupSplash(QWidget):
    """Splash 16:9 com arte pixel-art e barra de carregamento."""

    def __init__(self, mode: str = "startup") -> None:
        super().__init__(
            None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(1280, 720)
        self._mode = mode
        self._build_ui()
        self._center()

    def _build_ui(self) -> None:
        """Monta a tela de abertura sobre a arte 16:9."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.background = QLabel()
        self.background.setAlignment(Qt.AlignmentFlag.AlignCenter)
        asset = Path(__file__).resolve().parent.parent / "assets" / "splash_serm_v2.svg"
        if asset.is_file():
            self.background.setPixmap(QPixmap(str(asset)))
        self.background.setStyleSheet("background:#020817;")
        root.addWidget(self.background)

        overlay = QVBoxLayout(self.background)
        overlay.setContentsMargins(120, 505, 120, 48)
        overlay.addStretch()
        self.phase = QLabel()
        self.phase.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.phase.setStyleSheet(
            "color:#f4f8ff;font-family:Consolas;font-size:22px;font-weight:bold;"
        )
        overlay.addWidget(self.phase)
        self.detail = QLabel()
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail.setStyleSheet("color:#78d8ff;font-family:Consolas;font-size:13px;")
        overlay.addWidget(self.detail)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(15)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(12)
        self.progress.setStyleSheet(
            "QProgressBar{background:#071426;border:1px solid #1b8dcc;border-radius:6px;}"
            "QProgressBar::chunk{background:#20c7ff;border-radius:5px;}"
        )
        overlay.addWidget(self.progress)
        self._set_mode_text()

    def _set_mode_text(self) -> None:
        """Define o texto inicial do splash."""
        if self._mode == "shutdown":
            self.phase.setText("Encerrando SERM V2...")
            self.detail.setText("Finalizando recursos com segurança.")
        else:
            self.phase.setText("Carregando SERM V2...")
            self.detail.setText("Inicializando componentes...")

    def set_phase(self, phase: str, detail: str = "") -> None:
        """Atualiza a etapa e avança visualmente a barra."""
        self.phase.setText(phase)
        self.detail.setText(detail)
        self.progress.setValue(min(95, self.progress.value() + 20))
        QApplication.processEvents()

    def _center(self) -> None:
        """Centraliza no monitor principal."""
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            self.move(geometry.center() - self.rect().center())

    @classmethod
    def startup(cls) -> StartupSplash:
        """Cria e mostra o splash de inicialização."""
        splash = cls("startup")
        splash.show()
        QApplication.processEvents()
        return splash

    @classmethod
    def shutdown(cls) -> StartupSplash:
        """Cria e mostra o splash de encerramento."""
        splash = cls("shutdown")
        splash.show()
        QApplication.processEvents()
        return splash

    def finish(self, window: QWidget) -> None:
        """Completa a barra e encerra o splash."""
        self.progress.setValue(100)
        QApplication.processEvents()
        self.close()
        window.activateWindow()
