"""Card visual reutilizável para jogos MAME."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


class MameGameCard(QFrame):
    """Apresenta artwork e metadados essenciais de uma máquina MAME."""

    activated = Signal(object)
    favorite_changed = Signal(object, bool)

    def __init__(self, game=None, artwork_path: str | Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self.game = game
        self._favorite = False
        self.setObjectName("mameGameCard")
        self.setProperty("status", self._status_key())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(196, 158)
        self.setMaximumHeight(190)
        self._build_ui()
        self.set_artwork(artwork_path)

    def _status_key(self) -> str:
        value = getattr(self.game, "playability_status", None)
        if value is None:
            value = getattr(self.game, "status", "working")
        text = getattr(value, "value", value)
        text = str(text).lower()
        if "mixed" in text:
            return "mixed"
        if "not" in text or "broken" in text:
            return "broken"
        return "working"

    def _text(self, *names: str, default: str = "—") -> str:
        for name in names:
            value = getattr(self.game, name, None)
            if value not in (None, ""):
                return str(getattr(value, "value", value))
        return default

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

        title_row = QHBoxLayout()
        title_row.setSpacing(4)
        self.title = QLabel(self._text("title", "name", "short_name"))
        self.title.setObjectName("gameTitle")
        self.title.setWordWrap(False)
        self.title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        title_row.addWidget(self.title, 1)
        self.favorite = QLabel("☆")
        self.favorite.setObjectName("gameFavorite")
        self.favorite.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addWidget(self.favorite)
        root.addLayout(title_row)

        self.subtitle = QLabel(
            f"{self._text('year', default='—')} · {self._text('manufacturer', 'publisher', default='—')}"
        )
        self.subtitle.setObjectName("gameSubtitle")
        root.addWidget(self.subtitle)

        chips = QHBoxLayout()
        chips.setSpacing(4)
        self.category = QLabel(self._text("category", "genre", default="Arcade"))
        self.category.setObjectName("gameChip")
        self.subcategory = QLabel(self._text("subcategory", "genre", default="—"))
        self.subcategory.setObjectName("gameChip")
        chips.addWidget(self.category)
        chips.addWidget(self.subcategory)
        chips.addStretch(1)
        root.addLayout(chips)

        self.metadata = QLabel(self._metadata_text())
        self.metadata.setObjectName("gameMetadata")
        root.addWidget(self.metadata)

        self.status_badge = QLabel(self._status_label())
        self.status_badge.setObjectName("gameStatusBadge")
        self.status_badge.setProperty("status", self._status_key())
        self.status_badge.setMaximumWidth(92)
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.raise_()
        self.artwork.installEventFilter(self)

    def _metadata_text(self) -> str:
        players = self._text("players", "max_players", default="2")
        buttons = self._text("buttons", "max_buttons", default="0")
        orientation = self._text("orientation", default="Horizontal")
        return f"♙ {players}   ◇ {buttons}   ◫ {orientation}"

    def _status_label(self) -> str:
        return {"working": "● WORKING", "mixed": "● MIXED", "broken": "● NOT WORKING"}.get(
            self._status_key(), "● WORKING"
        )

    def set_artwork(self, artwork_path: str | Path | None) -> None:
        self._artwork_path = Path(artwork_path) if artwork_path else None
        if self._artwork_path and self._artwork_path.is_file():
            pixmap = QPixmap(str(self._artwork_path))
            if not pixmap.isNull():
                self.artwork.setPixmap(
                    pixmap.scaled(
                        self.artwork.size().width() or 180,
                        88,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return
        self.artwork.setText(self._text("short_name", "name", default="MAME"))

    def set_game(self, game, artwork_path: str | Path | None = None) -> None:
        self.game = game
        self.title.setText(self._text("title", "name", "short_name"))
        self.subtitle.setText(
            f"{self._text('year', default='—')} · {self._text('manufacturer', 'publisher', default='—')}"
        )
        self.category.setText(self._text("category", "genre", default="Arcade"))
        self.subcategory.setText(self._text("subcategory", "genre", default="—"))
        self.metadata.setText(self._metadata_text())
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
