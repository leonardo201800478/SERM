from app.database.database import Database
from app.mame.listxml import ListXmlParser
from app.core.models.mame_installation import MameInstallation
from app.database.repositories.machine_repository import MachineRepository
import hashlib

class DatabaseService:
    def __init__(self, db: Database):
        self.db = db
        self.machine_repo = MachineRepository(db)

    def import_listxml(self, xml_string: str, executable_path: str, version: str):
        conn = self.db.conn
        cursor = conn.cursor()

        # Verifica se já existe uma instalação com este caminho
        cursor.execute("SELECT id FROM mame_installation WHERE executable_path = ?", (executable_path,))
        row = cursor.fetchone()
        if row:
            installation_id = row[0]
            cursor.execute("UPDATE mame_installation SET version = ?, detected_at = CURRENT_TIMESTAMP WHERE id = ?",
                           (version, installation_id))
        else:
            with open(executable_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            cursor.execute("INSERT INTO mame_installation (version, executable_path, executable_hash) VALUES (?, ?, ?)",
                           (version, executable_path, file_hash))
            installation_id = cursor.lastrowid
        conn.commit()

        # Parse do XML
        machines = ListXmlParser.parse(xml_string)

        # Insere máquinas e roms
        for machine in machines:
            machine.mame_installation_id = installation_id
            machine_id = self.machine_repo.insert_machine(machine)
            for rom in machine.roms:
                rom.machine_id = machine_id
                self.machine_repo.insert_rom(rom)

        conn.commit()