import logging
import sqlite3
from pathlib import Path

from app.config.app_config import AppConfig

logger = logging.getLogger(__name__)


class Database:
    """
    Gerencia a conexão SQLite do MAME Set Builder.

    Responsabilidades:
    - Criar o diretório do banco quando necessário;
    - Abrir a conexão SQLite;
    - Carregar o schema oficial de app/database/schema.sql;
    - Aplicar migrações de bancos antigos;
    - Manter um fallback mínimo caso o schema.sql realmente não exista.
    """

    def __init__(self, db_path: Path | None = None):
        """
        Inicializa o gerenciador do banco.

        Args:
            db_path: Caminho opcional para o arquivo SQLite.
                     Quando não informado, utiliza o caminho definido
                     em AppConfig.
        """
        if db_path is None:
            app_config = AppConfig()
            db_path = app_config.db_path

        self.db_path = Path(db_path)
        self.conn: sqlite3.Connection | None = None

        logger.info(
            "Database inicializado com caminho: %s",
            self.db_path,
        )

    # ------------------------------------------------------------------
    # CONEXÃO
    # ------------------------------------------------------------------

    def connect(self) -> sqlite3.Connection:
        """
        Abre a conexão com o banco SQLite.

        Returns:
            A conexão SQLite aberta.

        Raises:
            sqlite3.Error: Caso não seja possível abrir ou inicializar
                           o banco.
        """
        if self.conn is not None:
            return self.conn

        try:
            # Garante que o diretório do banco exista.
            self.db_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            logger.info(
                "Conectando ao banco: %s",
                self.db_path,
            )

            self.conn = sqlite3.connect(
                str(self.db_path),
            )

            # Permite acessar colunas pelo nome.
            self.conn.row_factory = sqlite3.Row

            # Garante que Foreign Keys sejam respeitadas pelo SQLite.
            self.conn.execute(
                "PRAGMA foreign_keys = ON"
            )

            # Melhora o comportamento de concorrência entre leitura
            # e escrita.
            self.conn.execute(
                "PRAGMA journal_mode = WAL"
            )

            # Cria/verifica as tabelas.
            self._create_tables()

            # Aplica migrações de versões anteriores.
            self._migrate_schema()

            logger.info(
                "Conexão estabelecida e tabelas verificadas."
            )

            return self.conn

        except sqlite3.Error:
            logger.exception(
                "Erro ao inicializar o banco SQLite: %s",
                self.db_path,
            )

            if self.conn is not None:
                try:
                    self.conn.rollback()
                except sqlite3.Error:
                    pass

                try:
                    self.conn.close()
                except sqlite3.Error:
                    pass

                self.conn = None

            raise

    # ------------------------------------------------------------------
    # SCHEMA
    # ------------------------------------------------------------------

    def _get_schema_path(self) -> Path:
        """
        Retorna o caminho absoluto do schema.sql oficial.

        O arquivo deve estar em:

            app/
                database/
                    database.py
                    schema.sql

        Returns:
            Caminho absoluto do schema.sql.
        """
        return (
            Path(__file__)
            .resolve()
            .parent
            / "schema.sql"
        )

    def _create_tables(self) -> None:
        """
        Cria as tabelas utilizando o schema.sql oficial.

        O fallback somente é utilizado quando o schema.sql não existe.
        Se o arquivo existir mas apresentar erro SQL, a exceção é
        propagada para evitar mascarar problemas no banco.
        """
        if self.conn is None:
            raise RuntimeError(
                "Banco não conectado."
            )

        schema_path = self._get_schema_path()

        logger.debug(
            "Procurando schema SQL em: %s",
            schema_path,
        )

        if not schema_path.is_file():
            logger.error(
                "schema.sql não encontrado em: %s",
                schema_path,
            )

            logger.warning(
                "O schema oficial não está disponível. "
                "Utilizando fallback de emergência."
            )

            self._create_schema_fallback()
            return

        logger.info(
            "Carregando schema oficial: %s",
            schema_path,
        )

        try:
            schema_sql = schema_path.read_text(
                encoding="utf-8",
            )

            if not schema_sql.strip():
                raise RuntimeError(
                    f"schema.sql está vazio: {schema_path}"
                )

            self.conn.executescript(schema_sql)
            self.conn.commit()

            logger.info(
                "Schema oficial carregado com sucesso."
            )

        except (OSError, sqlite3.Error, RuntimeError):
            logger.exception(
                "Erro ao carregar schema.sql: %s",
                schema_path,
            )

            self.conn.rollback()
            raise

    # ------------------------------------------------------------------
    # MIGRAÇÕES
    # ------------------------------------------------------------------

    def _migrate_schema(self) -> None:
        """
        Aplica alterações incrementais em bancos criados por versões antigas.

        O MAME -listxml não informa o tamanho dos CHDs. A coluna disk.size
        é utilizada pelo CHD scanner para armazenar o tamanho real do arquivo.

        Bancos antigos podem não possuir essa coluna, portanto ela é criada
        automaticamente durante a inicialização.
        """
        if self.conn is None:
            raise RuntimeError(
                "Banco não conectado."
            )

        cursor = self.conn.cursor()

        try:
            cursor.execute(
                "PRAGMA table_info(disk)"
            )

            columns = {
                row["name"]
                for row in cursor.fetchall()
            }

            # Caso a tabela disk ainda não exista, o schema oficial deveria
            # tê-la criado. Esta proteção evita erro obscuro em instalações
            # incompletas.
            if not columns:
                logger.warning(
                    "Tabela 'disk' não encontrada durante a migração."
                )
                return

            if "size" not in columns:
                logger.info(
                    "Migrando schema: adicionando coluna disk.size"
                )

                cursor.execute(
                    """
                    ALTER TABLE disk
                    ADD COLUMN size INTEGER DEFAULT 0
                    """
                )

                self.conn.commit()

                logger.info(
                    "Migração disk.size concluída."
                )

        except sqlite3.Error:
            self.conn.rollback()

            logger.exception(
                "Erro durante a migração do schema."
            )

            raise

    # ------------------------------------------------------------------
    # FALLBACK
    # ------------------------------------------------------------------

    def _create_schema_fallback(self) -> None:
        """
        Cria um schema mínimo de emergência.

        Este método não deve ser utilizado em uma instalação normal.
        O arquivo app/database/schema.sql deve sempre acompanhar o projeto.

        O fallback existe somente para evitar que a aplicação fique
        completamente inutilizável caso o schema seja removido ou não seja
        incluído durante uma instalação/empacotamento.
        """
        if self.conn is None:
            raise RuntimeError(
                "Banco não conectado."
            )

        logger.warning(
            "Criando tabelas mínimas usando FALLBACK."
        )

        try:
            self.conn.executescript(
                """
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

                    FOREIGN KEY (
                        mame_installation_id
                    )
                    REFERENCES mame_installation(id)
                    ON DELETE CASCADE
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

                    FOREIGN KEY (
                        machine_id
                    )
                    REFERENCES machine(id)
                    ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS disk (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    machine_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    sha1 TEXT,
                    merge TEXT,
                    region TEXT,
                    idx INTEGER DEFAULT 0,
                    writable INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'good',
                    optional INTEGER DEFAULT 0,
                    size INTEGER DEFAULT 0,

                    FOREIGN KEY (
                        machine_id
                    )
                    REFERENCES machine(id)
                    ON DELETE CASCADE
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

                    PRIMARY KEY (
                        machine_id,
                        category_id
                    ),

                    FOREIGN KEY (
                        machine_id
                    )
                    REFERENCES machine(id)
                    ON DELETE CASCADE,

                    FOREIGN KEY (
                        category_id
                    )
                    REFERENCES category(id)
                    ON DELETE CASCADE
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

                -- Índices de machine
                CREATE INDEX IF NOT EXISTS
                    idx_machine_name
                    ON machine(name);

                CREATE INDEX IF NOT EXISTS
                    idx_machine_cloneof
                    ON machine(cloneof);

                CREATE INDEX IF NOT EXISTS
                    idx_machine_romof
                    ON machine(romof);

                CREATE INDEX IF NOT EXISTS
                    idx_machine_sourcefile
                    ON machine(sourcefile);

                CREATE INDEX IF NOT EXISTS
                    idx_machine_emulation_status
                    ON machine(emulation_status);

                CREATE INDEX IF NOT EXISTS
                    idx_machine_is_bios
                    ON machine(is_bios);

                CREATE INDEX IF NOT EXISTS
                    idx_machine_is_device
                    ON machine(is_device);

                CREATE INDEX IF NOT EXISTS
                    idx_machine_is_mechanical
                    ON machine(is_mechanical);

                -- Índices de ROM
                CREATE INDEX IF NOT EXISTS
                    idx_rom_machine_id
                    ON rom(machine_id);

                CREATE INDEX IF NOT EXISTS
                    idx_rom_name
                    ON rom(name);

                CREATE INDEX IF NOT EXISTS
                    idx_rom_crc
                    ON rom(crc);

                CREATE INDEX IF NOT EXISTS
                    idx_rom_sha1
                    ON rom(sha1);

                CREATE INDEX IF NOT EXISTS
                    idx_rom_merge
                    ON rom(merge);

                -- Índices de disk
                CREATE INDEX IF NOT EXISTS
                    idx_disk_machine_id
                    ON disk(machine_id);

                CREATE INDEX IF NOT EXISTS
                    idx_disk_sha1
                    ON disk(sha1);

                -- Índices de categorias
                CREATE INDEX IF NOT EXISTS
                    idx_machine_category_machine
                    ON machine_category(machine_id);

                CREATE INDEX IF NOT EXISTS
                    idx_machine_category_category
                    ON machine_category(category_id);

                -- Categorias padrão
                INSERT OR IGNORE INTO category
                    (name, display_name, source)
                VALUES
                    ('arcade', 'Arcade', 'manual'),
                    ('system', 'System', 'manual'),
                    ('bios', 'BIOS', 'manual'),
                    ('devices', 'Devices', 'manual'),
                    (
                        'electromechanical',
                        'Electromechanical',
                        'manual'
                    ),
                    ('casino', 'Casino', 'manual'),
                    ('mahjong', 'Mahjong', 'manual'),
                    ('screenless', 'Screenless', 'manual'),
                    ('mature', 'Mature', 'manual'),
                    ('driving', 'Driving', 'manual'),
                    ('fighter', 'Fighter', 'manual'),
                    ('gambling', 'Gambling', 'manual'),
                    (
                        'game_console',
                        'Game Console',
                        'manual'
                    ),
                    ('chd', 'CHD', 'manual'),
                    (
                        'ball_paddle',
                        'Ball & Paddle',
                        'manual'
                    ),
                    (
                        'board_game',
                        'Board Game',
                        'manual'
                    ),
                    (
                        'calculator',
                        'Calculator',
                        'manual'
                    ),
                    (
                        'card_games',
                        'Card Games',
                        'manual'
                    ),
                    ('maze', 'Maze', 'manual'),
                    (
                        'handheld',
                        'Handheld',
                        'manual'
                    ),
                    (
                        'climbing',
                        'Climbing',
                        'manual'
                    ),
                    (
                        'medal_game',
                        'Medal Game',
                        'manual'
                    ),
                    (
                        'musical',
                        'Musical',
                        'manual'
                    ),
                    (
                        'platform',
                        'Platform',
                        'manual'
                    ),
                    (
                        'shooter',
                        'Shooter',
                        'manual'
                    ),
                    (
                        'slot_machine',
                        'Slot Machine',
                        'manual'
                    ),
                    ('sports', 'Sports', 'manual'),
                    (
                        'tabletop',
                        'Tabletop',
                        'manual'
                    ),
                    (
                        'telephone',
                        'Telephone',
                        'manual'
                    );
                """
            )

            self.conn.commit()

            logger.info(
                "Tabelas fallback criadas."
            )

        except sqlite3.Error:
            self.conn.rollback()

            logger.exception(
                "Erro ao criar schema fallback."
            )

            raise

    # ------------------------------------------------------------------
    # FECHAMENTO
    # ------------------------------------------------------------------

    def close(self) -> None:
        """
        Fecha a conexão SQLite.

        É seguro chamar o método mesmo quando a conexão já estiver fechada.
        """
        if self.conn is None:
            return

        try:
            self.conn.close()

        except sqlite3.Error:
            logger.exception(
                "Erro ao fechar conexão com banco."
            )

        finally:
            self.conn = None

            logger.info(
                "Conexão com banco fechada."
            )