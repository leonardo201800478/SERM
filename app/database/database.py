import sqlite3
import logging
from pathlib import Path
from app.config.app_config import AppConfig

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: Path = None):
        if db_path is None:
            app_config = AppConfig()
            db_path = app_config.db_path
        self.db_path = db_path
        self.conn = None
        logger.info(f"Database inicializado com caminho: {db_path}")

    def connect(self):
        logger.info(f"Conectando ao banco: {self.db_path}")
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info("Conexão estabelecida e tabelas verificadas.")

    def _create_tables(self):
        """Cria todas as tabelas e índices a partir do schema.sql."""
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            logger.warning(f"schema.sql não encontrado em {schema_path}. Usando fallback.")
            self._create_schema_fallback()
            return
        logger.info(f"Carregando schema de {schema_path}")
        with open(schema_path, "r", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        self.conn.commit()
        logger.info("Schema criado com sucesso.")

    def _create_schema_fallback(self):
        """Fallback: cria apenas tabelas essenciais se schema.sql não existir."""
        logger.warning("Criando tabelas mínimas (fallback).")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS mame_installation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                executable_path TEXT UNIQUE NOT NULL,
                executable_hash TEXT NOT NULL,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS machine (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mame_installation_id INTEGER NOT NULL,
                name TEXT UNIQUE NOT NULL,
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
                FOREIGN KEY (mame_installation_id) REFERENCES mame_installation(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS rom (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                size INTEGER,
                crc TEXT,
                sha1 TEXT,
                merge TEXT,
                region TEXT,
                offset INTEGER DEFAULT 0,
                status TEXT DEFAULT 'good',
                optional INTEGER DEFAULT 0,
                bios TEXT,
                FOREIGN KEY (machine_id) REFERENCES machine(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS category (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                source TEXT DEFAULT 'manual'
            );
            CREATE TABLE IF NOT EXISTS machine_category (
                machine_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                PRIMARY KEY (machine_id, category_id),
                FOREIGN KEY (machine_id) REFERENCES machine(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS filter_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                profile_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_default INTEGER DEFAULT 0
            );
            INSERT OR IGNORE INTO category (name, display_name, source) VALUES
                ('arcade', 'Arcade', 'manual'),
                ('system', 'System', 'manual'),
                ('bios', 'BIOS', 'manual'),
                ('devices', 'Devices', 'manual'),
                ('electromechanical', 'Electromechanical', 'manual'),
                ('casino', 'Casino', 'manual'),
                ('mahjong', 'Mahjong', 'manual'),
                ('screenless', 'Screenless', 'manual'),
                ('mature', 'Mature', 'manual'),
                ('driving', 'Driving', 'manual'),
                ('fighter', 'Fighter', 'manual'),
                ('gambling', 'Gambling', 'manual'),
                ('game_console', 'Game Console', 'manual'),
                ('chd', 'CHD', 'manual'),
                ('ball_paddle', 'Ball & Paddle', 'manual'),
                ('board_game', 'Board Game', 'manual'),
                ('calculator', 'Calculator', 'manual'),
                ('card_games', 'Card Games', 'manual'),
                ('maze', 'Maze', 'manual'),
                ('handheld', 'Handheld', 'manual'),
                ('climbing', 'Climbing', 'manual'),
                ('medal_game', 'Medal Game', 'manual'),
                ('musical', 'Musical', 'manual'),
                ('platform', 'Platform', 'manual'),
                ('shooter', 'Shooter', 'manual'),
                ('slot_machine', 'Slot Machine', 'manual'),
                ('sports', 'Sports', 'manual'),
                ('tabletop', 'Tabletop', 'manual'),
                ('telephone', 'Telephone', 'manual');
        """)
        self.conn.commit()
        logger.info("Tabelas fallback criadas.")

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("Conexão com banco fechada.")