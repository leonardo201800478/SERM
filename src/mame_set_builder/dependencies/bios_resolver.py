"""
Resolvedor de BIOS – encontra as BIOS necessárias para uma máquina.
"""

import sqlite3
from typing import List

class BiosResolver:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_bios_for_machine(self, machine_name: str) -> List[str]:
        """
        Retorna os nomes das BIOS referenciadas por esta máquina.
        (Através de device_refs que são BIOS)
        """
        # Primeiro, busca device_refs
        cursor = self.conn.execute(
            "SELECT name FROM device_ref WHERE machine_id = (SELECT id FROM machine WHERE name = ?)",
            (machine_name,)
        )
        refs = [row["name"] for row in cursor]

        # Para cada referência, verifica se é BIOS
        bios_names = []
        for ref in refs:
            cursor2 = self.conn.execute(
                "SELECT name FROM machine WHERE name = ? AND isbios = 1", (ref,)
            )
            row = cursor2.fetchone()
            if row:
                bios_names.append(row["name"])
        return bios_names