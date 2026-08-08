"""
Resolvedor de clones – obtém a máquina pai (cloneof) recursivamente.
"""

import sqlite3
from typing import Optional, Set

class CloneResolver:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_parent(self, machine_name: str) -> Optional[str]:
        """Retorna o nome da máquina pai (cloneof), se existir."""
        cursor = self.conn.execute(
            "SELECT cloneof FROM machine WHERE name = ?", (machine_name,)
        )
        row = cursor.fetchone()
        return row["cloneof"] if row and row["cloneof"] else None

    def get_root_parent(self, machine_name: str) -> str:
        """
        Retorna a raiz da cadeia de clones (a máquina que não é clone de ninguém).
        """
        current = machine_name
        while True:
            parent = self.get_parent(current)
            if not parent:
                return current
            current = parent