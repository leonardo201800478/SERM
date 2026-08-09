import sqlite3
from pathlib import Path

class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
        # Tabela mame_installation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mame_installation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT,
                executable_path TEXT UNIQUE,
                executable_hash TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Tabela machine
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS machine (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mame_installation_id INTEGER,
                name TEXT UNIQUE,
                description TEXT,
                year TEXT,
                manufacturer TEXT,
                sourcefile TEXT,
                cloneof TEXT,
                romof TEXT,
                sampleof TEXT,
                is_bios INTEGER DEFAULT 0,
                is_device INTEGER DEFAULT 0,
                is_mechanical INTEGER DEFAULT 0,
                runnable INTEGER DEFAULT 1,
                emulation_status TEXT,
                driver_status TEXT,
                savestate INTEGER DEFAULT 0,
                requires_artwork INTEGER DEFAULT 0,
                unofficial INTEGER DEFAULT 0,
                nosoundhardware INTEGER DEFAULT 0,
                incomplete INTEGER DEFAULT 0,
                FOREIGN KEY (mame_installation_id) REFERENCES mame_installation(id)
            )
        ''')
        # Tabela rom
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rom (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id INTEGER,
                name TEXT,
                size INTEGER,
                crc TEXT,
                sha1 TEXT,
                merge TEXT,
                region TEXT,
                offset INTEGER,
                status TEXT,
                optional INTEGER DEFAULT 0,
                bios TEXT,
                FOREIGN KEY (machine_id) REFERENCES machine(id)
            )
        ''')
        # Demais tabelas serão adicionadas nas fases seguintes
        self.conn.commit()