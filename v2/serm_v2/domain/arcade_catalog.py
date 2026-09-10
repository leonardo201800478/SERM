"""Contratos de acesso ao catálogo Arcade.

Este módulo define a fronteira entre a aplicação e qualquer persistência.
Implementações SQLite ficam fora do domínio e podem ser substituídas sem
alterar consumidores da GUI ou do Set Builder.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from .arcade import ArcadeGame


class ArcadeCatalog(Protocol):
    """Contrato mínimo para consulta do catálogo Arcade."""

    def get_game(self, name: str) -> ArcadeGame | None:
        """Retorna uma máquina pelo nome ou ``None`` quando ausente."""
        ...

    def iter_games(self) -> Iterable[ArcadeGame]:
        """Itera pelas máquinas do catálogo sem exigir materialização global."""
        ...

    def count(self) -> int:
        """Retorna a quantidade de máquinas disponíveis no catálogo."""
        ...


class InMemoryArcadeCatalog:
    """Implementação simples para testes unitários e prototipagem."""

    def __init__(self, games: Iterable[ArcadeGame] = ()) -> None:
        """Inicializa o catálogo indexando as máquinas pelo nome."""
        self._games = {game.name: game for game in games}

    def get_game(self, name: str) -> ArcadeGame | None:
        """Retorna uma máquina pelo nome."""
        return self._games.get(name)

    def iter_games(self) -> Iterable[ArcadeGame]:
        """Itera as máquinas em ordem determinística pelo nome."""
        for name in sorted(self._games):
            yield self._games[name]

    def count(self) -> int:
        """Retorna a quantidade de máquinas indexadas."""
        return len(self._games)


__all__ = ["ArcadeCatalog", "InMemoryArcadeCatalog"]
