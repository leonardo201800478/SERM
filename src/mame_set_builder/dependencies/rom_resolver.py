import sqlite3
from typing import List, Dict, Any

class RomResolver:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_roms(self, machine_name: str) -> List[Dict[str, Any]]:
        cursor = self.conn.execute("""
            SELECT name, size, crc, sha1, merge, region, offset, status, optional, bios
            FROM rom
            WHERE machine_id = (SELECT id FROM machine WHERE name = ?)
        """, (machine_name,))
        return [dict(row) for row in cursor]