"""Auditoria semântica das fontes positivas e negativas dos filtros MAME.

Não modifica o banco. Mede apenas sobreposição entre fontes que representam
estados opostos e a presença de máquinas nas fontes esperadas.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


DB_FILE = Path(__file__).resolve().parents[1] / "data" / "database" / "serm.db"


POLARITIES = {
    "working": ("Working Arcade.ini", "Working Arcade Clean.ini", "Not Working Arcade.ini", "not_working_arcade.ini"),
    "mechanical": ("Mechanical Arcade.ini", "mechanical_arcade.ini", "Non Mechanical Arcade.ini", "not_mechanical_arcade.ini"),
    "mature": ("mature.ini", "not_mature.ini"),
    "bootleg": ("bootlegs.ini", "Non Bootlegs.ini", "not_ bootlegs.ini"),
    "artwork": ("artwork.ini", "artwork_necessary.ini"),
    "chd": ("CHD Working.ini", "CHD (no BIOS).ini"),
}


def source_ids(db: sqlite3.Connection, names: tuple[str, ...]) -> list[int]:
    placeholders = ",".join("?" for _ in names)
    rows = db.execute(
        f"SELECT id FROM mame_folder_filter_source WHERE lower(file_name) IN ({placeholders})",
        tuple(name.casefold() for name in names),
    ).fetchall()
    return [int(row[0]) for row in rows]


def machines(db: sqlite3.Connection, ids: list[int]) -> set[str]:
    if not ids:
        return set()
    placeholders = ",".join("?" for _ in ids)
    rows = db.execute(
        f"SELECT DISTINCT machine_name FROM mame_folder_filter_entry WHERE source_id IN ({placeholders})",
        tuple(ids),
    ).fetchall()
    return {str(row[0]) for row in rows if row[0]}


def main() -> int:
    if not DB_FILE.exists():
        raise SystemExit(f"Banco não encontrado: {DB_FILE}")

    with sqlite3.connect(DB_FILE) as db:
        print("=" * 80)
        print("AUDITORIA SEMÂNTICA DAS FONTES MAME FOLDERS")
        print("=" * 80)
        print(f"DB: {DB_FILE}")

        for name, groups in POLARITIES.items():
            if name == "working":
                positive, positive_clean, negative, negative_alt = groups
                pos_names = (positive, positive_clean)
                neg_names = (negative, negative_alt)
            elif name == "mechanical":
                positive, positive_alt, negative, negative_alt = groups
                pos_names = (positive, positive_alt)
                neg_names = (negative, negative_alt)
            elif name == "bootleg":
                positive = groups[0]
                negative = groups[1:]
                pos_names = (positive,)
                neg_names = negative
            else:
                pos_names = (groups[0],)
                neg_names = (groups[1],)

            pos_ids = source_ids(db, pos_names)
            neg_ids = source_ids(db, neg_names)
            pos = machines(db, pos_ids)
            neg = machines(db, neg_ids)
            overlap = pos & neg

            print(f"\n{name.upper()}")
            print(f"  positivos encontrados : {len(pos):>8,}")
            print(f"  negativos encontrados : {len(neg):>8,}")
            print(f"  sobreposição          : {len(overlap):>8,}")
            if overlap:
                sample = ", ".join(sorted(overlap, key=str.casefold)[:10])
                print(f"  amostra               : {sample}")

        print("\nRESULTADO:")
        print("  A auditoria NÃO modifica dados.")
        print("  Sobreposição positiva/negativa é conflito de evidência e não pode")
        print("  ser convertida silenciosamente em False pelo loader de filtros.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
