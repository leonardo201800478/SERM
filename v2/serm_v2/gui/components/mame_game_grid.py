"""Grade responsiva e reutilizável de cards MAME."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
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
    """Container responsivo que reutiliza cards e evita reconstruções visuais."""

    game_activated = Signal(object)

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
        self._columns = 0

    def set_artwork_roots(self, roots: list[str | Path]) -> None:
        self.resolver = MameArtworkResolver(roots)
        self._refresh_existing_cards()

    def set_mame_executable(self, executable: str | Path | None) -> None:
        if not executable:
            return
        service = MameArtworkService.from_mame_executable(executable)
        self.resolver = MameArtworkResolver(service.roots)
        self._refresh_existing_cards()

    def artwork_inventory(self, game) -> dict[str, Path]:
        """Expõe todas as artes encontradas para uso por detalhes/preview."""
        return self.resolver.inventory(game)

    def set_games(self, games) -> None:
        """Atualiza a grade incrementalmente, preservando widgets existentes."""
        self._games = list(games or [])
        self.content.setUpdatesEnabled(False)
        try:
            common = min(len(self._games), len(self._cards))

            for index in range(common):
                game = self._games[index]
                self._cards[index].set_game(game, self.resolver.resolve(game))

            while len(self._cards) > len(self._games):
                card = self._cards.pop()
                self.layout.removeWidget(card)
                card.deleteLater()

            while len(self._cards) < len(self._games):
                game = self._games[len(self._cards)]
                card = MameGameCard(parent=self.content)
                card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                card.activated.connect(self.game_activated.emit)
                card.set_game(game, self.resolver.resolve(game))
                self._cards.append(card)

            self._reflow(force=True)
        finally:
            self.content.setUpdatesEnabled(True)
            self.content.update()

    def _refresh_existing_cards(self) -> None:
        if not self._cards:
            return
        self.content.setUpdatesEnabled(False)
        try:
            for card, game in zip(self._cards, self._games):
                card.set_game(game, self.resolver.resolve(game))
        finally:
            self.content.setUpdatesEnabled(True)
            self.content.update()

    def _reflow(self, force: bool = False) -> None:
        columns = self._column_count()
        if not force and columns == self._columns:
            return
        self._columns = columns

        # Retira somente os itens do layout; os widgets continuam vivos e são
        # reposicionados, evitando o efeito de piscar observado no resize.
        while self.layout.count():
            self.layout.takeAt(0)

        for column in range(6):
            self.layout.setColumnStretch(column, 0)
        for column in range(columns):
            self.layout.setColumnStretch(column, 1)

        for index, card in enumerate(self._cards):
            self.layout.addWidget(card, index // columns, index % columns)

    def _column_count(self) -> int:
        width = self.viewport().width()
        return max(1, min(6, width // 205))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._cards:
            self._reflow()


__all__ = ["MameArtworkResolver", "MameGameGrid"]
