"""Inicialização idempotente das tabelas do pipeline de dataset."""
from __future__ import annotations
from pathlib import Path


def ensure_dataset_schema(db) -> None:
    """Executa todas as migrações operacionais do dataset."""
    base=Path(__file__).resolve().parent/"migrations"
    for name in ("002_dataset_pipeline.sql","003_physical_rom_scan.sql"):
        path=base/name
        if not path.is_file():raise FileNotFoundError(f"Migração ausente: {path}")
        db.executescript(path.read_text(encoding="utf-8"))
    db.conn.commit()
