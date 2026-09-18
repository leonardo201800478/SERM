"""Card visual compacto e reutilizável para jogos MAME."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics, QPixmap, QPixmapCache
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


class MameGameCard(QFrame):
    """Card compacto para artwork, estado e metadados da máquina MAME."""

    activated = Signal(object)
    favorite_changed = Signal(object, bool)

    CARD_WIDTH = 196
    CARD_HEIGHT = 194
    ARTWORK_HEIGHT = 72

    def __init__(self, game=None, artwork_path: str | Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self.game = game
        self._favorite = False
        self.setObjectName("mameGameCard")
        self.setProperty("status", self._status_key())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setMaximumHeight(self.CARD_HEIGHT)
        self.setStyleSheet("""
            #mameGameCard { background: #071a2a; border: 1px solid #14547d; border-radius: 10px; }
            #mameGameCard:hover { border: 1px solid #1598ff; background: #09243a; }
            #gameArtwork { background: #06111d; border: 1px solid #0e3856; border-radius: 7px; color: #7190a8; font-size: 10px; }
            #gameTitle { color: #f1f7ff; font-size: 11px; font-weight: 700; }
            #gameSubtitle, #gameMetadata { color: #8da9bf; font-size: 9px; }
            #gameChip { background: #063451; color: #63c4ff; border: 1px solid #0d5d8b; border-radius: 6px; padding: 1px 5px; font-size: 8px; }
            #gameFavorite { color: #dbeeff; font-size: 15px; }
            #gameStatusBadge { border-radius: 7px; padding: 1px 6px; font-size: 8px; font-weight: 800; }
            #gameStatusBadge[status="working"] { background: #19e66d; color: #03200f; }
            #gameStatusBadge[status="mixed"] { background: #ffc51b; color: #2b2100; }
            #gameStatusBadge[status="broken"] { background: #ff405e; color: #2b0008; }
            #gameStatusBadge[status="unknown"] { background: #737b84; color: #f1f4f6; }
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
        value = self._value("playability_status", "status", default="unknown").lower()
        if "mixed" in value:
            return "mixed"
        if "not" in value or "broken" in value:
            return "broken"
        if "unknown" in value or "audit" in value or value in {"—", ""}:
            return "unknown"
        return "working"

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(2)

        self.artwork = QLabel()
        self.artwork.setObjectName("gameArtwork")
        self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artwork.setFixedHeight(self.ARTWORK_HEIGHT)
        self.artwork.setSizePolicy(self.artwork.sizePolicy().horizontalPolicy(), self.artwork.sizePolicy().verticalPolicy())
        root.addWidget(self.artwork)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(2)
        self.status_badge = QLabel(self._status_label())
        self.status_badge.setObjectName("gameStatusBadge")
        self.status_badge.setProperty("status", self._status_key())
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_row.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignLeft)
        status_row.addStretch(1)
        self.favorite = QLabel("☆")
        self.favorite.setObjectName("gameFavorite")
        self.favorite.setFixedWidth(18)
        self.favorite.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_row.addWidget(self.favorite)
        root.addLayout(status_row)

        self.title = QLabel()
        self.title.setObjectName("gameTitle")
        self.title.setFixedHeight(27)
        self.title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self.title)

        self.subtitle = QLabel()
        self.subtitle.setObjectName("gameSubtitle")
        self.subtitle.setFixedHeight(13)
        root.addWidget(self.subtitle)

        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(3)
        self.category = QLabel()
        self.category.setObjectName("gameChip")
        self.category.setFixedHeight(16)
        self.subcategory = QLabel()
        self.subcategory.setObjectName("gameChip")
        self.subcategory.setFixedHeight(16)
        chips.addWidget(self.category)
        chips.addWidget(self.subcategory)
        chips.addStretch(1)
        root.addLayout(chips)

        self.metadata = QLabel()
        self.metadata.setObjectName("gameMetadata")
        self.metadata.setFixedHeight(13)
        root.addWidget(self.metadata)

        self.set_game(self.game, None)

    @staticmethod
    def _elide(text: str, width: int, font) -> str:
        return QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideRight, max(20, width))

    def _set_elided(self, label: QLabel, text: str) -> None:
        label.setText(self._elide(text, max(20, label.width()), label.font()))
        label.setToolTip(text if text != label.text() else "")

    def _metadata(self) -> str:
        return f"♙ {self._value('players', 'max_players', default='2')}   ◇ {self._value('buttons', 'max_buttons', default='0')}   ◫ {self._value('orientation', default='Horizontal')}"

    def _status_label(self) -> str:
        return {
            "working": "● WORKING",
            "mixed": "● MIXED",
            "broken": "● NOT WORKING",
            "unknown": "● NÃO AUDITADO",
        }.get(self._status_key(), "● NÃO AUDITADO")

    def set_artwork(self, artwork_path: str | Path | None) -> None:
        path = Path(artwork_path) if artwork_path else None
        if path and path.is_file():
            cache_key = f"serm-mame-card::{path.resolve()}"
            pixmap = QPixmap()
            if not QPixmapCache.find(cache_key, pixmap):
                source = QPixmap(str(path))
                if not source.isNull():
                    pixmap = source.scaled(
                        280,
                        self.ARTWORK_HEIGHT,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    QPixmapCache.insert(cache_key, pixmap)
            if not pixmap.isNull():
                self.artwork.setPixmap(pixmap)
                self.artwork.setText("")
                return
        self.artwork.setPixmap(QPixmap())
        self.artwork.setText(self._value("short_name", "name", default="MAME"))

    def set_game(self, game, artwork_path: str | Path | None = None) -> None:
        self.game = game
        title = self._value("title", "name", "short_name")
        subtitle = f"{self._value('year', default='—')} · {self._value('manufacturer', 'publisher', default='—')}"
        self._set_elided(self.title, title)
        self._set_elided(self.subtitle, subtitle)
        self._set_elided(self.category, self._value("category", "genre", default="Arcade"))
        self._set_elided(self.subcategory, self._value("subcategory", "genre", default="—"))
        self.metadata.setText(self._metadata())
        status = self._status_key()
        self.setProperty("status", status)
        self.status_badge.setText(self._status_label())
        self.status_badge.setProperty("status", status)
        self.style().unpolish(self)
        self.style().polish(self)
        if artwork_path is not None:
            self.set_artwork(artwork_path)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "title") and self.game is not None:
            self._set_elided(self.title, self._value("title", "name", "short_name"))
            self._set_elided(self.subtitle, f"{self._value('year', default='—')} · {self._value('manufacturer', 'publisher', default='—')}")
            self._set_elided(self.category, self._value("category", "genre", default="Arcade"))
            self._set_elided(self.subcategory, self._value("subcategory", "genre", default="—"))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self.game)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self.game)
        super().mouseDoubleClickEvent(event)


__all__ = ["MameGameCard"]
