from __future__ import annotations

from pathlib import Path
import os


class ScanSnapshot:
    """Gerencia o manifesto ativo de um escaneamento de forma transacional."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.temp_path = self.path.with_name(self.path.name + ".tmp")

    def begin(self) -> Path:
        """Prepara o arquivo temporário sem destruir o manifesto anterior."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.temp_path.unlink()
        except FileNotFoundError:
            pass
        return self.temp_path

    def commit(self) -> None:
        """Publica o novo manifesto somente após o escaneamento terminar."""
        if not self.temp_path.exists():
            raise FileNotFoundError(f"Manifesto temporário não encontrado: {self.temp_path}")
        os.replace(self.temp_path, self.path)

    def rollback(self) -> None:
        """Remove somente o manifesto temporário do escaneamento atual."""
        try:
            self.temp_path.unlink()
        except FileNotFoundError:
            pass
