# src/mame_set_builder/database/connection.py
import sqlite3
from pathlib import Path
from .schema import init_db

class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            # Cria o diretório pai se não existir
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.path))
            self._conn.row_factory = sqlite3.Row
            init_db(self._conn)
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None