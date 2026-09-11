"""Card visual reutilizável para jogos MAME."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


class MameGameCard(QFrame):
    """Card rico para artwork, estado e metadados da máquina MAME."""

    activated = Signal(object)
    favorite_changed = Signal(object, bool)

    def __init__(self, game=None, artwork_path: str | Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self.game = game
        self._favorite = False
        self.setObjectName("mameGameCard")
        self.setProperty("status", self._status_key())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(196, 174)
        self.setMaximumHeight(194)
        self.setStyleSheet("""
            #mameGameCard { background: #071a2a; border: 1px solid #14547d; border-radius: 10px; }
            #mameGameCard:hover { border: 1px solid #1598ff; background: #09243a; }
            #gameArtwork { background: #06111d; border: 1px solid #0e3856; border-radius: 7px; color: #7190a8; font-size: 11px; }
            #gameTitle { color: #f1f7ff; font-size: 12px; font-weight: 700; }
            #gameSubtitle, #gameMetadata { color: #8da9bf; font-size: 10px; }
            #gameChip { background: #063451; color: #63c4ff; border: 1px solid #0d5d8b; border-radius: 7px; padding: 2px 6px; font-size: 9px; }
            #gameFavorite { color: #dbeeff; font-size: 18px; }
            #gameStatusBadge { border-radius: 8px; padding: 2px 7px; font-size: 9px; font-weight: 800; }
            #gameStatusBadge[status="working"] { background: #19e66d; color: #03200f; }
            #gameStatusBadge[status="mixed"] { background: #ffc51b; color: #2b2100; }
            #gameStatusBadge[status="broken"] { background: #ff405e; color: #2b0008; }
        """)
        self._build_ui()
        self.set_artwork(artwork_path)

    def _value(self, *fields: str, default: str = "—") -> str:
        for field in fields:
            value = getattr(self.game, field, None)
            if value not in (None, ""):
                return str(getattr(value, "value", value))
        return default

    def _status_key(self) -> str:
        value = self._value("playability_status", "status", default="working").lower()
        if "mixed" in value:
            return "mixed"
        if "not" in value or "broken" in value:
            return "broken"
        return "working"

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(7, 7, 7, 7)
        root.setSpacing(4)
        self.artwork = QLabel()
        self.artwork.setObjectName("gameArtwork")
        self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artwork.setMinimumHeight(82)
        self.artwork.setMaximumHeight(92)
        root.addWidget(self.artwork)
        status_row = QHBoxLayout()
        self.status_badge = QLabel(self._status_label())
        self.status_badge.setObjectName("gameStatusBadge")
        self.status_badge.setProperty("status", self._status_key())
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_row.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignLeft)
        status_row.addStretch(1)
        self.favorite = QLabel("☆")
        self.favorite.setObjectName("gameFavorite")
        status_row.addWidget(self.favorite)
        root.addLayout(status_row)
        title_row = QHBoxLayout()
        self.title = QLabel(self._value("title", "name", "short_name"))
        self.title.setObjectName("gameTitle")
        self.title.setWordWrap(False)
        title_row.addWidget(self.title, 1)
        root.addLayout(title_row)
        self.subtitle = QLabel(f"{self._value('year', default='—')} · {self._value('manufacturer', 'publisher', default='—')}")
        self.subtitle.setObjectName("gameSubtitle")
        root.addWidget(self.subtitle)
        chips = QHBoxLayout()
        chips.setSpacing(4)
        self.category = QLabel(self._value("category", "genre", default="Arcade"))
        self.category.setObjectName("gameChip")
        self.subcategory = QLabel(self._value("subcategory", "genre", default="—"))
        self.subcategory.setObjectName("gameChip")
        chips.addWidget(self.category)
        chips.addWidget(self.subcategory)
        chips.addStretch(1)
        root.addLayout(chips)
        self.metadata = QLabel(self._metadata())
        self.metadata.setObjectName("gameMetadata")
        root.addWidget(self.metadata)

    def _metadata(self) -> str:
        return f"♙ {self._value('players', 'max_players', default='2')}   ◇ {self._value('buttons', 'max_buttons', default='0')}   ◫ {self._value('orientation', default='Horizontal')}"

    def _status_label(self) -> str:
        return {"working": "● WORKING", "mixed": "● MIXED", "broken": "● NOT WORKING"}.get(self._status_key(), "● WORKING")

    def set_artwork(self, artwork_path: str | Path | None) -> None:
        path = Path(artwork_path) if artwork_path else None
        if path and path.is_file():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.artwork.setPixmap(pixmap.scaled(280, 88, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
                return
        self.artwork.setText(self._value("short_name", "name", default="MAME"))

    def set_game(self, game, artwork_path: str | Path | None = None) -> None:
        self.game = game
        self.title.setText(self._value("title", "name", "short_name"))
        self.subtitle.setText(f"{self._value('year', default='—')} · {self._value('manufacturer', 'publisher', default='—')}")
        self.category.setText(self._value("category", "genre", default="Arcade"))
        self.subcategory.setText(self._value("subcategory", "genre", default="—"))
        self.metadata.setText(self._metadata())
        status = self._status_key()
        self.setProperty("status", status)
        self.status_badge.setText(self._status_label())
        self.status_badge.setProperty("status", status)
        self.style().unpolish(self)
        self.style().polish(self)
        self.set_artwork(artwork_path)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self.game)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self.game)
        super().mouseDoubleClickEvent(event)


__all__ = ["MameGameCard"]
