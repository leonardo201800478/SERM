"""Grade responsiva e reutilizável de cards MAME."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QScrollArea, QSizePolicy, QWidget

from ...services.mame_artwork_service import MameArtworkService
from .mame_game_card import MameGameCard


class MameArtworkResolver:
    """Compatibilidade para resolução de artwork local do MAME."""

    def __init__(self, roots: list[str | Path] | None = None) -> None:
        self.service = MameArtworkService(roots)

    def resolve(self, game) -> Path | None:
        name = self._game_name(game)
        return self.service.primary(name) if name else None

    def inventory(self, game) -> dict[str, Path]:
        name = self._game_name(game)
        return self.service.inventory(name) if name else {}

    @staticmethod
    def _game_name(game) -> str:
        for field in ("short_name", "name", "rom_name", "set_name"):
            value = getattr(game, field, None)
            if value:
                return str(value)
        return ""


class MameGameGrid(QScrollArea):
    """Container de resultados com cálculo automático de colunas."""

    def __init__(
        self,
        artwork_roots: list[str | Path] | None = None,
        mame_executable: str | Path | None = None,
        parent=None,
    ) -> None:
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

        if artwork_roots:
            self.resolver = MameArtworkResolver(artwork_roots)
        else:
            self.resolver = MameArtworkResolver(
                [Path(mame_executable).parent, Path(mame_executable).parent / "artwork"]
                if mame_executable
                else []
            )
        self._games = []
        self._cards: list[MameGameCard] = []

    def set_artwork_roots(self, roots: list[str | Path]) -> None:
        self.resolver = MameArtworkResolver(roots)
        self.set_games(self._games)

    def set_mame_executable(self, executable: str | Path | None) -> None:
        if not executable:
            return
        service = MameArtworkService.from_mame_executable(executable)
        self.resolver = MameArtworkResolver(service.roots)
        self.set_games(self._games)

    def artwork_inventory(self, game) -> dict[str, Path]:
        """Expõe todas as artes encontradas para uso por detalhes/preview."""
        return self.resolver.inventory(game)

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
