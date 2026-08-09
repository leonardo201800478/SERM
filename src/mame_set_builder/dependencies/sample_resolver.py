import sqlite3
from typing import List

class SampleResolver:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_samples(self, machine_name: str) -> List[str]:
        cursor = self.conn.execute(
            "SELECT sampleof FROM machine WHERE name = ?", (machine_name,)
        )
        row = cursor.fetchone()
        if row and row[0]:
            return row[0].split()
        return []