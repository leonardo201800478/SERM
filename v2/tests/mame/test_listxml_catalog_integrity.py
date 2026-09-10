"""Validação leve e determinística do catálogo MAME.

Compara a fonte ListXML com o catálogo relacional sem imprimir máquinas/ROMs
individualmente. O XML é percorrido em streaming para evitar carregar o documento
inteiro em memória.
"""

from __future__ import annotations

import hashlib
import sqlite3
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "database" / "serm.db"
XML_PATH = ROOT / "data" / "mame" / "metadata" / "listxml.xml"

COUNTS = {
    "machine": "mame_machine",
    "rom": "mame_rom",
    "disk": "mame_disk",
    "display": "mame_display",
    "sample": "mame_sample",
    "chip": "mame_chip",
    "device": "mame_device",
}


def _db_table_exists(db: sqlite3.Connection, table: str) -> bool:
    """Retorna se uma tabela existe no SQLite."""
    return (
        db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        is not None
    )


def _db_count(db: sqlite3.Connection, table: str, import_id: int) -> int | None:
    """Conta somente registros pertencentes à importação auditada."""
    if not _db_table_exists(db, table):
        return None
    if table == "mame_machine":
        query = 'SELECT COUNT(*) FROM "mame_machine" WHERE import_id=?'
        params = (import_id,)
    else:
        query = (
            f'SELECT COUNT(*) FROM "{table}" '
            "WHERE machine_id IN (SELECT id FROM mame_machine WHERE import_id=?)"
        )
        params = (import_id,)
    return int(db.execute(query, params).fetchone()[0])


def _sha256(path: Path) -> str:
    """Calcula SHA-256 em blocos pequenos."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stream_counts(path: Path) -> tuple[dict[str, int], int, str | None]:
    """Percorre o XML em streaming e conta entidades relevantes."""
    counts = {key: 0 for key in COUNTS}
    machines = 0
    build: str | None = None

    for event, elem in ET.iterparse(path, events=("start", "end")):
        if event == "start":
            if elem.tag == "mame" and build is None:
                build = elem.attrib.get("build")
            elif elem.tag == "machine":
                machines += 1
            continue

        key = elem.tag
        if key in counts:
            counts[key] += 1
        if key == "machine":
            elem.clear()

    return counts, machines, build


def _print_result(label: str, expected: int | None, actual: int | None) -> bool:
    """Imprime uma linha compacta e retorna se a comparação passou."""
    if expected is None or actual is None:
        print(f"{label:<18} SKIP   fonte={expected!s:<10} banco={actual!s}")
        return True
    ok = expected == actual
    status = "PASS" if ok else "FAIL"
    print(f"{label:<18} {status:<6} fonte={expected:<10,} banco={actual:<10,}")
    return ok


def _sample_machine_names(db: sqlite3.Connection, import_id: int, limit: int = 10) -> list[str]:
    """Obtém uma amostra determinística da importação auditada."""
    if not _db_table_exists(db, "mame_machine"):
        return []
    rows = db.execute(
        "SELECT name FROM mame_machine WHERE import_id=? ORDER BY name LIMIT ?",
        (import_id, limit),
    ).fetchall()
    return [str(row[0]) for row in rows]


def _validate_sample_identity(db: sqlite3.Connection, xml_path: Path, import_id: int) -> tuple[int, int]:
    """Compara uma pequena amostra de nomes XML contra a importação auditada."""
    sample = set(_sample_machine_names(db, import_id))
    if not sample:
        return 0, 0

    found: set[str] = set()
    for _event, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag == "machine":
            name = elem.attrib.get("name")
            if name in sample:
                found.add(name)
            elem.clear()
            if len(found) == len(sample):
                break
    return len(sample), len(found)


def main() -> int:
    """Executa as validações e retorna código de processo apropriado."""
    started = time.perf_counter()
    print("=" * 72)
    print("SERM | MAME CATALOG INTEGRITY TEST")
    print("=" * 72)
    print(f"XML    : {XML_PATH}")
    print(f"BANCO  : {DB_PATH}")

    if not XML_PATH.is_file() or not DB_PATH.is_file():
        print("ERROR  | fonte XML ou banco não encontrado")
        return 2

    print("\n[1/5] FONTE")
    xml_hash = _sha256(XML_PATH)
    print(f"SHA256 : {xml_hash}")

    print("\n[2/5] XML STREAMING")
    xml_counts, machine_count, build = _stream_counts(XML_PATH)
    print(f"Build  : {build or 'não informado'}")
    print(f"Machines: {machine_count:,}")
    for key, count in xml_counts.items():
        if key != "machine":
            print(f"{key:<8}: {count:,}")

    print("\n[3/5] BANCO")
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys=ON")
    import_row = db.execute(
        """SELECT id, mame_build, machine_count, byte_length, source_hash, status
           FROM mame_listxml_import
           WHERE status='completed'
           ORDER BY id DESC LIMIT 1"""
    ).fetchone()
    if not import_row:
        print("FAIL   | nenhuma importação MAME concluída")
        db.close()
        return 1

    import_id, db_build, declared_machines, byte_length, db_hash, status = import_row
    print(f"Import : {import_id} | status={status} | build={db_build}")
    print(f"Bytes  : {byte_length:,}")
    print(f"Hash   : {'PASS' if db_hash == xml_hash else 'FAIL'}")
    passed = db_hash == xml_hash

    print("\n[4/5] CARDINALIDADE")
    for xml_key, table in COUNTS.items():
        expected = machine_count if xml_key == "machine" else xml_counts[xml_key]
        actual = _db_count(db, table, int(import_id))
        passed &= _print_result(table, expected, actual)

    if declared_machines != machine_count:
        print(f"machine_count      FAIL   import={declared_machines:,} xml={machine_count:,}")
        passed = False
    else:
        print(f"machine_count      PASS   {machine_count:,}")

    print("\n[5/5] AMOSTRA DE IDENTIDADE")
    sample_total, sample_found = _validate_sample_identity(db, XML_PATH, int(import_id))
    sample_ok = sample_total == sample_found
    print(f"Máquinas amostra   {'PASS' if sample_ok else 'FAIL'}   {sample_found}/{sample_total}")
    passed &= sample_ok

    db.close()
    elapsed = time.perf_counter() - started
    print("\n" + "=" * 72)
    print(f"RESULTADO: {'PASS' if passed else 'FAIL'} | tempo={elapsed:.2f}s")
    print("=" * 72)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
