from typing import Iterable

from core.database import Database
from core.models import Machine


class MachineRepository:

    """
    Responsável por gravar e consultar máquinas no banco SQLite.
    """

    def __init__(self, db: Database):

        self.db = db

        self.cursor = db.cursor()

        self.batch = []

        self.batch_size = 1000

    def insert(self, machine: Machine):

        self.batch.append((
            machine.name,
            machine.description,
            machine.cloneof,
            machine.romof,
            machine.manufacturer,
            machine.year,
            machine.sourcefile,
            int(machine.runnable),
            int(machine.isbios),
            int(machine.isdevice),
            int(machine.ismechanical),
            int(machine.working),
            machine.players
        ))

        if len(self.batch) >= self.batch_size:

            self.flush()

    def flush(self):

        if not self.batch:
            return

        self.cursor.executemany("""

            INSERT OR REPLACE INTO machine(

                name,
                description,
                cloneof,
                romof,
                manufacturer,
                year,
                sourcefile,
                runnable,
                isbios,
                isdevice,
                ismechanical,
                working,
                players

            )

            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)

        """, self.batch)

        self.db.commit()

        self.batch.clear()

    def count(self):

        return self.cursor.execute(

            "SELECT COUNT(*) FROM machine"

        ).fetchone()[0]