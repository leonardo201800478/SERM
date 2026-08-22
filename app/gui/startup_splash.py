"""Splash screen de inicialização e encerramento do MAME Set Builder.

A tela é propositalmente independente da MainWindow. Ela informa ao usuário
que o aplicativo está inicializando ou encerrando enquanto as validações,
a descoberta dos emuladores e o fechamento dos recursos são executados.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QProgressBar, QVBoxLayout, QWidget


class StartupSplash(QWidget):
    """Janela compacta e sem borda usada durante startup/shutdown."""

    def __init__(self, mode: str = "startup") -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(520, 250)
        self._mode = mode
        self._build_ui()
        self._center()

    def _build_ui(self) -> None:
        """Cria a apresentação visual do splash."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        card = QFrame()
        card.setStyleSheet(
            "QFrame{background:#151515;border:1px solid #3c3c3c;border-radius:12px;}"
            "QLabel{color:#e8e8e8;}"
            "QProgressBar{height:7px;border:0;background:#292929;border-radius:3px;}"
            "QProgressBar::chunk{background:#4c9aff;border-radius:3px;}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(12)

        title = QLabel("MAME Set Builder")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        layout.addWidget(title)

        self.phase = QLabel()
        self.phase.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.phase.setFont(QFont("Segoe UI", 11))
        layout.addWidget(self.phase)

        self.detail = QLabel()
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet("color:#9d9d9d;")
        layout.addWidget(self.detail)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        self._set_mode_text()
        outer.addWidget(card)

    def _set_mode_text(self) -> None:
        """Define o texto inicial conforme a operação atual."""
        if self._mode == "shutdown":
            self.phase.setText("Encerrando aplicação…")
            self.detail.setText("Finalizando tarefas e fechando o banco de dados com segurança.")
        else:
            self.phase.setText("Inicializando…")
            self.detail.setText("Validando banco de dados, configurações e emuladores.")

    def set_phase(self, phase: str, detail: str = "") -> None:
        """Atualiza a etapa exibida ao usuário."""
        self.phase.setText(phase)
        self.detail.setText(detail)
        QApplication.processEvents()

    def _center(self) -> None:
        """Centraliza o splash no monitor principal."""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.move(geometry.center() - self.rect().center())

    @classmethod
    def startup(cls) -> "StartupSplash":
        """Cria e exibe um splash de inicialização."""
        splash = cls("startup")
        splash.show()
        QApplication.processEvents()
        return splash

    @classmethod
    def shutdown(cls) -> "StartupSplash":
        """Cria e exibe um splash de encerramento."""
        splash = cls("shutdown")
        splash.show()
        QApplication.processEvents()
        return splash
