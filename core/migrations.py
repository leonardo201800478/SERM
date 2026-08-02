# core/migrations.py
import sqlite3
from core.database import Database

def run_migrations(db: Database):
    """
    Adiciona colunas extras à tabela machine se não existirem.
    """
    new_columns = [
        "category TEXT",
        "genre TEXT",
        "genre_ows TEXT",
        "machine_category TEXT",
        "machine_type TEXT",
        "players TEXT",
        "resolution TEXT",
        "version TEXT",
        "working_arcade INTEGER",
    ]
    for col in new_columns:
        try:
            db.cursor().execute(f"ALTER TABLE machine ADD COLUMN {col}")
            db.commit()
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise
            # Se a coluna já existe, ignoramos