"""Qt logging bridge and live console used by the SERM V2 GUI."""

from __future__ import annotations

import logging
from collections import deque

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget


class _QtLogEmitter(QObject):
    record_emitted = Signal(str, str)


class QtLogHandler(logging.Handler):
    """Forward Python logging records to Qt while retaining recent messages."""

    def __init__(self, max_records: int = 1000) -> None:
        super().__init__()
        self.records: deque[str] = deque(maxlen=max_records)
        self.emitter = _QtLogEmitter()

    @property
    def record_emitted(self):
        return self.emitter.record_emitted

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            self.records.append(message)
            self.emitter.record_emitted.emit(record.levelname, message)
        except Exception:
            self.handleError(record)


class LogConsole(QWidget):
    """Console de diagnóstico sem clipping horizontal e com rolagem automática."""

    def __init__(self, handler: QtLogHandler, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = QPlainTextEdit()
        self.view.setObjectName("logConsole")
        self.view.setReadOnly(True)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.view.setMaximumBlockCount(1000)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.view)
        self._handler = handler
        for message in handler.records:
            self.view.appendPlainText(message)
        handler.record_emitted.connect(self._append)

    def _append(self, _level: str, message: str) -> None:
        self.view.appendPlainText(message)
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def clear(self) -> None:
        self.view.clear()


class LogViewer(QObject):
    """Own the application-wide Qt logging handler and optional live console."""

    handler: QtLogHandler

    def __init__(self) -> None:
        super().__init__()
        self.handler = QtLogHandler()
        self.handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        logging.getLogger().addHandler(self.handler)

    def create_console(self, parent: QWidget | None = None) -> LogConsole:
        return LogConsole(self.handler, parent)

    def close(self) -> None:
        logging.getLogger().removeHandler(self.handler)
        self.handler.close()


__all__ = ["LogConsole", "LogViewer", "QtLogHandler"]
