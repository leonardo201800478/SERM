"""Qt logging bridge used by the SERM V2 GUI."""
from __future__ import annotations

import logging
from collections import deque

from PySide6.QtCore import QObject, Signal


class QtLogHandler(logging.Handler, QObject):
    """Forward Python logging records to Qt widgets without changing the logger API."""

    record_emitted = Signal(str, str)

    def __init__(self, max_records: int = 500) -> None:
        QObject.__init__(self)
        logging.Handler.__init__(self)
        self.records: deque[str] = deque(maxlen=max_records)

    def emit(self, record: logging.LogRecord) -> None:
        """Store and emit one formatted logging record."""
        try:
            message = self.format(record)
            self.records.append(message)
            self.record_emitted.emit(record.levelname, message)
        except Exception:
            self.handleError(record)


class LogViewer(QObject):
    """Own the application-wide Qt logging handler."""

    handler: QtLogHandler

    def __init__(self) -> None:
        super().__init__()
        self.handler = QtLogHandler()
        self.handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        root = logging.getLogger()
        root.addHandler(self.handler)

    def close(self) -> None:
        """Detach the Qt handler from the root logger."""
        logging.getLogger().removeHandler(self.handler)
        self.handler.close()
