"""Painel de log em tempo real para embutir em qualquer aba da GUI.

Resolve a lacuna onde nenhum widget da aplicação exibia os logs do
``logging`` — só existiam no arquivo ``mame-set-builder.log`` e no console.

Uso:
    self.log_panel = LogPanel(self, logger_name="")  # "" = logger raiz (tudo)
    layout.addWidget(self.log_panel)
"""

import logging
from collections import deque

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Quantas linhas manter em memória (tanto no widget quanto no buffer
# usado para reaplicar o filtro de nível sem perder histórico).
_MAX_LINES = 2000

_LEVEL_OPTIONS = [
    ("Tudo", logging.DEBUG),
    ("Info+", logging.INFO),
    ("Aviso+", logging.WARNING),
    ("Erro+", logging.ERROR),
]


class QtLogHandler(logging.Handler, QObject):
    """Handler de logging que reemite cada registro como sinal Qt.

    Herdar de QObject permite usar Signal/Slot; a emissão do sinal a partir
    de uma thread de background (ex.: import_task) é automaticamente
    enfileirada pelo Qt para a thread da GUI, então é seguro chamar
    logger.info(...) de qualquer thread.
    """

    log_record = Signal(str, int)  # (mensagem formatada, levelno)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        self.log_record.emit(msg, record.levelno)


class LogPanel(QWidget):
    def __init__(self, parent=None, logger_name: str = ""):
        """logger_name='' anexa ao logger raiz, capturando logs de todo o app."""
        super().__init__(parent)

        self._buffer: deque = deque(maxlen=_MAX_LINES)
        self._min_level = logging.DEBUG

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        title = QLabel("Log do Sistema")
        title.setStyleSheet("font-weight: bold;")
        toolbar.addWidget(title)
        toolbar.addStretch()

        toolbar.addWidget(QLabel("Nível:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems([label for label, _ in _LEVEL_OPTIONS])
        self.level_combo.setCurrentIndex(1)  # "Info+" por padrão
        self._min_level = _LEVEL_OPTIONS[1][1]
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        toolbar.addWidget(self.level_combo)

        btn_clear = QPushButton("Limpar")
        btn_clear.setFixedWidth(80)
        btn_clear.clicked.connect(self._clear)
        toolbar.addWidget(btn_clear)

        layout.addLayout(toolbar)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setMaximumBlockCount(_MAX_LINES)
        self.text_edit.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 11px;")
        self.text_edit.setPlaceholderText("Os eventos do sistema aparecerão aqui...")
        layout.addWidget(self.text_edit)

        self._logger_name = logger_name
        self._handler = QtLogHandler()
        self._handler.setLevel(logging.DEBUG)  # filtragem por nível é feita na UI, não no handler
        self._handler.log_record.connect(self._on_log_record)
        logging.getLogger(logger_name).addHandler(self._handler)

    # ------------------------------------------------------------------

    def _on_log_record(self, message: str, levelno: int) -> None:
        self._buffer.append((message, levelno))
        if levelno >= self._min_level:
            self.text_edit.appendPlainText(message)

    def _on_level_changed(self, index: int) -> None:
        self._min_level = _LEVEL_OPTIONS[index][1]
        self._rebuild_view()

    def _rebuild_view(self) -> None:
        self.text_edit.setPlainText(
            "\n".join(msg for msg, lvl in self._buffer if lvl >= self._min_level)
        )
        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _clear(self) -> None:
        self._buffer.clear()
        self.text_edit.clear()

    def detach(self) -> None:
        """Remove o handler do logger. Chamar ao fechar a janela/aba, se necessário."""
        logging.getLogger(self._logger_name).removeHandler(self._handler)
