"""
Resolvedor de CHDs (discos) – retorna discos associados à máquina.
"""

import sqlite3
from typing import List, Dict, Any

class ChdResolver:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_disks(self, machine_name: str) -> List[Dict[str, Any]]:
        """Retorna a lista de discos (CHDs) da máquina."""
        cursor = self.conn.execute(
            """
            SELECT name, sha1, merge, region, disk_index, writable, status, optional
            FROM disk
            WHERE machine_id = (SELECT id FROM machine WHERE name = ?)
            """,
            (machine_name,)
        )
        return [dict(row) for row in cursor]