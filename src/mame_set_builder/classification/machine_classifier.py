"""
Classificador de máquinas MAME.
Aplica as regras definidas em rules.py para cada máquina.
"""

import sqlite3
import logging
from typing import Dict, Any, Optional
from .rules import CATEGORIES, Rule

logger = logging.getLogger(__name__)

class MachineClassifier:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.categories = CATEGORIES

    def classify_machine(self, machine_data: Dict[str, Any]) -> Optional[str]:
        for category_name, rules in self.categories:
            if all(rule(machine_data) for rule in rules):
                return category_name
        return None

    def classify_all(self, batch_size: int = 1000) -> int:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS machine_classification (
                machine_id INTEGER PRIMARY KEY,
                category TEXT NOT NULL,
                FOREIGN KEY(machine_id) REFERENCES machine(id)
            )
        """)
        self.conn.commit()

        cursor = self.conn.execute("""
            SELECT 
                m.id,
                m.name,
                m.description,
                m.isbios,
                m.isdevice,
                m.ismechanical,
                m.runnable,
                m.sourcefile,
                m.manufacturer,
                i.id as input_id,
                i.service,
                i.tilt,
                i.coin
            FROM machine m
            LEFT JOIN input i ON m.id = i.machine_id
            ORDER BY m.id
        """)

        count = 0
        for row in cursor:
            machine_data = {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"] or "",
                "isbios": bool(row["isbios"]),
                "isdevice": bool(row["isdevice"]),
                "ismechanical": bool(row["ismechanical"]),
                "runnable": bool(row["runnable"]),
                "sourcefile": row["sourcefile"] or "",
                "manufacturer": row["manufacturer"] or "",
                "input": bool(row["input_id"]),
                "input_ports": self._get_input_ports(row["id"]),
            }
            category = self.classify_machine(machine_data)
            if category is None:
                category = "Other"

            self.conn.execute(
                "INSERT OR REPLACE INTO machine_classification (machine_id, category) VALUES (?, ?)",
                (row["id"], category)
            )
            count += 1
            if count % batch_size == 0:
                self.conn.commit()
                logger.info(f"{count} máquinas classificadas...")

        self.conn.commit()
        logger.info(f"Classificação concluída: {count} máquinas classificadas.")
        return count

    def _get_input_ports(self, machine_id: int) -> list:
        cursor = self.conn.execute("""
            SELECT tag, type
            FROM input_port ip
            JOIN input i ON ip.input_id = i.id
            WHERE i.machine_id = ?
        """, (machine_id,))
        return [dict(row) for row in cursor]