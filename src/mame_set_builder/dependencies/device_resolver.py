"""
Resolvedor de devices – encontra devices referenciados por uma máquina.
"""

import sqlite3
from typing import List

class DeviceResolver:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_devices_for_machine(self, machine_name: str) -> List[str]:
        """Retorna nomes de devices referenciados (que não são BIOS)."""
        cursor = self.conn.execute(
            "SELECT name FROM device_ref WHERE machine_id = (SELECT id FROM machine WHERE name = ?)",
            (machine_name,)
        )
        refs = [row["name"] for row in cursor]

        devices = []
        for ref in refs:
            cursor2 = self.conn.execute(
                "SELECT name FROM machine WHERE name = ? AND isdevice = 1", (ref,)
            )
            row = cursor2.fetchone()
            if row:
                devices.append(row["name"])
        return devices