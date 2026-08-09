import sqlite3
from typing import Optional

class CloneResolver:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_parent(self, machine_name: str) -> Optional[str]:
        cursor = self.conn.execute(
            "SELECT cloneof FROM machine WHERE name = ?", (machine_name,)
        )
        row = cursor.fetchone()
        return row[0] if row and row[0] else None

    def get_root_parent(self, machine_name: str) -> str:
        current = machine_name
        while True:
            parent = self.get_parent(current)
            if not parent:
                return current
            current = parent