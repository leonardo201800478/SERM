"""Grade responsiva e reutilizável de cards MAME."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QScrollArea, QSizePolicy, QWidget

from .mame_game_card import MameGameCard


class MameArtworkResolver:
    """Resolve artwork local do MAME sem depender de uma fonte externa."""

    EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
    DIRECTORY_NAMES = ("snap", "snaps", "titles", "artwork", "flyers", "marquees")

    def __init__(self, roots: list[str | Path] | None = None) -> None:
        self.roots = [Path(root) for root in (roots or [])]
        self._cache: dict[str, Path | None] = {}

    def resolve(self, game) -> Path | None:
        name = self._game_name(game)
        if not name:
            return None
        if name in self._cache:
            return self._cache[name]
        candidates = []
        for root in self.roots:
            candidates.extend(self._candidate_paths(root, name))
        result = next((path for path in candidates if path.is_file()), None)
        self._cache[name] = result
        return result

    @staticmethod
    def _game_name(game) -> str:
        for field in ("short_name", "name", "rom_name", "set_name"):
            value = getattr(game, field, None)
            if value:
                return str(value)
        return ""

    def _candidate_paths(self, root: Path, name: str):
        directories = [root]
        if root.name.lower() not in self.DIRECTORY_NAMES:
            directories.extend(root / directory for directory in self.DIRECTORY_NAMES)
        for directory in directories:
            for extension in self.EXTENSIONS:
                yield directory / f"{name}{extension}"


class MameGameGrid(QScrollArea):
    """Container de resultados com cálculo automático de colunas."""

    def __init__(self, artwork_roots: list[str | Path] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("mameGameGrid")
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.content = QWidget()
        self.content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.layout = QGridLayout(self.content)
        self.layout.setContentsMargins(2, 2, 2, 12)
        self.layout.setHorizontalSpacing(10)
        self.layout.setVerticalSpacing(10)
        self.setWidget(self.content)
        self.resolver = MameArtworkResolver(artwork_roots)
        self._games = []
        self._cards: list[MameGameCard] = []

    def set_artwork_roots(self, roots: list[str | Path]) -> None:
        self.resolver = MameArtworkResolver(roots)
        self.set_games(self._games)

    def set_games(self, games) -> None:
        self._games = list(games or [])
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        columns = max(1, self._column_count())
        for index, game in enumerate(self._games):
            card = MameGameCard(game, self.resolver.resolve(game), self.content)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._cards.append(card)
            self.layout.addWidget(card, index // columns, index % columns)
        for column in range(columns):
            self.layout.setColumnStretch(column, 1)

    def _column_count(self) -> int:
        width = self.viewport().width()
        return max(1, min(6, width // 205))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._games:
            self.set_games(self._games)


__all__ = ["MameArtworkResolver", "MameGameGrid"]
