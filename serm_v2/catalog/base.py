"""Contrato comum para fontes de catálogo do Arcade Studio."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models.arcade import ArcadeGame, ArcadePlatform


class ArcadeCatalogProvider(ABC):
    """Interface mínima que todo catálogo de arcade deve implementar.

    O provider conhece o formato de origem; a camada superior trabalha apenas
    com modelos do Arcade Studio. Isso permite adicionar novos sistemas sem
    duplicar a UI, o motor de filtros ou o Set Builder.
    """

    platform: ArcadePlatform

    @abstractmethod
    def games(self) -> list[ArcadeGame]:
        """Retorna os títulos disponíveis no catálogo."""
        raise NotImplementedError

    @abstractmethod
    def game(self, machine_name: str) -> ArcadeGame | None:
        """Localiza um título pelo identificador técnico."""
        raise NotImplementedError

    @abstractmethod
    def source(self) -> Path | None:
        """Retorna a fonte física usada pelo provider, quando aplicável."""
        raise NotImplementedError

    def game_count(self) -> int:
        """Quantidade de títulos expostos pelo catálogo."""
        return len(self.games())


__all__ = ["ArcadeCatalogProvider"]
