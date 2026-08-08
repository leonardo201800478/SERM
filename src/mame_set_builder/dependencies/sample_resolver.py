"""
Resolvedor de samples – retorna samples referenciados pela máquina.
"""

import sqlite3
from typing import List

class SampleResolver:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_samples(self, machine_name: str) -> List[str]:
        """Retorna os nomes dos samples necessários (se houver)."""
        cursor = self.conn.execute(
            """
            SELECT sampleof FROM machine WHERE name = ?
            """,
            (machine_name,)
        )
        row = cursor.fetchone()
        if row and row["sampleof"]:
            # Geralmente sampleof é uma lista separada por espaço, mas pode ser um único nome
            return row["sampleof"].split()
        return []