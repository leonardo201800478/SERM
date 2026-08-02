# repositories/machine_repository.py
import sqlite3
from typing import List, Optional
from core.models import Machine
from core.database import Database

class MachineRepository:
    def __init__(self, db: Database):
        self.db = db
        self.cursor = db.cursor()

    def count(self) -> int:
        self.cursor.execute("SELECT COUNT(*) FROM machine")
        return self.cursor.fetchone()[0]

    def insert_batch(self, machines: List[Machine]):
        """Insere várias máquinas de uma vez."""
        sql = """
            INSERT OR IGNORE INTO machine
            (name, description, year, manufacturer, cloneof, working, ismechanical, isdevice)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        data = [
            (
                m.name,
                m.description,
                m.year,
                m.manufacturer,
                m.cloneof,
                1 if m.working else 0,
                1 if m.ismechanical else 0,
                1 if m.isdevice else 0,
            )
            for m in machines
        ]
        self.cursor.executemany(sql, data)
        self.db.commit()

    def bulk_update_column(self, column: str, updates: List[tuple]):
        """Atualiza uma coluna para várias máquinas.
        updates = [(value, machine_name), ...]
        """
        if not updates:
            return
        sql = f"UPDATE machine SET {column} = ? WHERE LOWER(name) = LOWER(?)"
        self.cursor.executemany(sql, updates)
        self.db.commit()

    # repositories/machine_repository.py (trecho adicional)
    def get_all(self) -> List[Machine]:
        """Retorna todas as máquinas com todos os campos (incluindo extras)."""
        query = """
            SELECT
                name, description, year, manufacturer, cloneof,
                working, ismechanical, isdevice,
                category, genre, genre_ows, machine_category,
                machine_type, players, resolution, version,
                working_arcade
            FROM machine
            ORDER BY name
        """
        self.cursor.execute(query)
        rows = self.cursor.fetchall()
        machines = []
        for row in rows:
            machine = Machine(
                name=row[0],
                description=row[1],
                year=row[2],
                manufacturer=row[3],
                cloneof=row[4],
                working=bool(row[5]),
                ismechanical=bool(row[6]),
                isdevice=bool(row[7]),
                category=row[8],
                genre=row[9],
                genre_ows=row[10],
                machine_category=row[11],
                machine_type=row[12],
                players=row[13],
                resolution=row[14],
                version=row[15],
                working_arcade=bool(row[16]) if row[16] is not None else None,
            )
            machines.append(machine)
        return machines