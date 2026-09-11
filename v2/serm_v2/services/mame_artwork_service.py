"""Descoberta e resolução de artwork local de uma instalação MAME.

A instalação MAME pode conter vários diretórios de artwork. Este serviço não
baixa arquivos e não altera a instalação: apenas indexa o que já existe e
resolve a melhor imagem para cada máquina.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MameArtwork:
    """Arquivo de artwork associado a uma máquina MAME."""

    kind: str
    path: Path


class MameArtworkService:
    """Resolve artwork usando a convenção de diretórios do MAME/SNAPS."""

    # A ordem representa a prioridade visual quando mais de uma fonte existe.
    DIRECTORY_ALIASES: dict[str, tuple[str, ...]] = {
        "snap": ("snap", "snaps"),
        "title": ("titles", "title"),
        "flyer": ("flyers", "flyer"),
        "marquee": ("marquees", "marquee"),
        "cabinet": ("cabinets", "cabinet"),
        "pcb": ("pcb", "pcbs"),
        "icon": ("icons", "icon"),
        "cpanel": ("cpanel", "cpanels"),
        "score": ("scores", "score"),
        "select": ("select", "selects"),
        "versus": ("versus",),
        "boss": ("bosses", "boss"),
        "end": ("ends", "end"),
        "gameover": ("gameover", "gameovers"),
        "howto": ("howto", "howtos"),
        "promo": ("promo", "promos"),
        "artwork": ("artwork",),
    }
    EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
    PRIMARY_ORDER = ("snap", "title", "flyer", "marquee", "cabinet", "artwork")

    def __init__(self, roots: list[str | Path] | None = None) -> None:
        self.roots = [Path(root) for root in (roots or [])]
        self._cache: dict[str, dict[str, Path]] = {}

    @classmethod
    def from_mame_executable(cls, executable: str | Path | None) -> "MameArtworkService":
        """Cria um resolvedor a partir de ``mame.exe``.

        O diretório ``artwork`` e os diretórios irmãos ficam normalmente ao
        lado de ``mame.exe``. Também aceitamos uma pasta ``artwork`` explícita.
        """
        if not executable:
            return cls()
        exe = Path(executable)
        root = exe.parent if exe.suffix else exe
        return cls([root, root / "artwork"])

    def inventory(self, game_name: str) -> dict[str, Path]:
        """Retorna todas as artes encontradas para ``game_name``."""
        name = str(game_name or "").strip()
        if not name:
            return {}
        cached = self._cache.get(name)
        if cached is not None:
            return dict(cached)

        found: dict[str, Path] = {}
        for kind, aliases in self.DIRECTORY_ALIASES.items():
            path = self._find_in_aliases(name, aliases)
            if path is not None:
                found[kind] = path
        self._cache[name] = found
        return dict(found)

    def resolve(self, game_name: str, kind: str = "snap") -> Path | None:
        """Retorna a arte de um tipo, com fallback para ``snap``."""
        inventory = self.inventory(game_name)
        if kind in inventory:
            return inventory[kind]
        if kind == "primary":
            return self.primary(game_name)
        return None

    def primary(self, game_name: str) -> Path | None:
        """Escolhe a melhor arte para representar o jogo no card."""
        inventory = self.inventory(game_name)
        for kind in self.PRIMARY_ORDER:
            path = inventory.get(kind)
            if path is not None:
                return path
        return None

    def all_artwork(self, game_name: str) -> list[MameArtwork]:
        """Retorna a coleção encontrada em ordem determinística."""
        inventory = self.inventory(game_name)
        return [MameArtwork(kind, inventory[kind]) for kind in self.DIRECTORY_ALIASES if kind in inventory]

    def clear_cache(self) -> None:
        self._cache.clear()

    def _find_in_aliases(self, name: str, aliases: tuple[str, ...]) -> Path | None:
        for root in self.roots:
            for directory_name in aliases:
                directory = root if root.name.lower() == directory_name else root / directory_name
                for extension in self.EXTENSIONS:
                    candidate = directory / f"{name}{extension}"
                    if candidate.is_file():
                        return candidate
        return None


__all__ = ["MameArtwork", "MameArtworkService"]
