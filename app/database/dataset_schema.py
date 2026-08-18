"""Inicialização idempotente das tabelas do pipeline de dataset."""
from __future__ import annotations
from pathlib import Path


def ensure_dataset_schema(db) -> None:
    """Executa a migração 002 antes de usar o pipeline."""
    path=Path(__file__).resolve().parent/"migrations"/"002_dataset_pipeline.sql"
    if not path.is_file():raise FileNotFoundError(f"Migração ausente: {path}")
    db.executescript(path.read_text(encoding="utf-8"))
    db.conn.commit()
