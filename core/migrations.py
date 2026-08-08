# core/migrations.py
import sqlite3
from core.database import Database

def add_column_if_not_exists(cursor, table_name, column_name, column_type):
    """
    Adiciona uma coluna à tabela se ela não existir.
    """
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [info[1] for info in cursor.fetchall()]
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

def run_migrations(db: Database):
    """
    Cria a tabela machine se não existir e adiciona colunas extras.
    """
    conn = db.conn if hasattr(db, 'conn') else db._conn
    cursor = conn.cursor()

    # Tabela principal (já com todos os campos necessários)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS machine (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            cloneof TEXT,
            romof TEXT,
            manufacturer TEXT,
            year TEXT,
            sourcefile TEXT,
            runnable INTEGER,
            isbios INTEGER,
            isdevice INTEGER,
            ismechanical INTEGER,
            working INTEGER,
            players INTEGER,
            category TEXT,
            genre TEXT,
            genre_ows TEXT,
            machine_category TEXT,
            machine_type TEXT,
            resolution TEXT,
            version TEXT,
            working_arcade INTEGER
        )
    ''')

    # Colunas extras que podem ser preenchidas por arquivos .ini adicionais
    extra_columns = [
        ('controls', 'TEXT'),
        ('cpu', 'TEXT'),
        ('sound', 'TEXT'),
        ('input', 'TEXT'),
        ('driver', 'TEXT'),
        ('display', 'TEXT'),
        ('refresh', 'TEXT'),
        ('orientation', 'TEXT'),
        ('colors', 'INTEGER'),
        ('sound_channels', 'INTEGER'),
        ('screen', 'TEXT'),
        ('video', 'TEXT'),
        ('graphics', 'TEXT'),
        ('notes', 'TEXT'),
    ]

    for col, typ in extra_columns:
        add_column_if_not_exists(cursor, 'machine', col, typ)

    # Índice na coluna name para acelerar buscas
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_machine_name ON machine(name);")

    conn.commit()
    print("Migrações aplicadas com sucesso.")