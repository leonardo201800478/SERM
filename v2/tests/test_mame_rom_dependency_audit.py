"""Auditoria das dependencias de ROM MAME para reconstrucao de sets.

Nao modifica o banco. Diferencia merge, BIOS e ROM compartilhada para
preparar a camada de resolucao de componentes.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parents[1] / "data" / "database" / "serm.db"


def main() -> int:
    if not DB_FILE.exists():
        raise SystemExit(f"Banco nao encontrado: {DB_FILE}")

    with sqlite3.connect(DB_FILE) as db:
        print("=" * 80)
        print("AUDITORIA DE DEPENDENCIAS DE ROM MAME")
        print("=" * 80)
        print(f"DB: {DB_FILE}")

        latest = db.execute(
            "SELECT id,mame_build,source_hash FROM mame_listxml_import "
            "WHERE status='completed' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if latest is None:
            raise SystemExit("Nenhuma importacao ListXML MAME concluida.")
        import_id, build, source_hash = latest
        print(f"IMPORT: id={import_id} build={build} hash={source_hash}")

        total = db.execute(
            "SELECT COUNT(*) FROM mame_rom r JOIN mame_machine m ON m.id=r.machine_id WHERE m.import_id=?",
            (import_id,),
        ).fetchone()[0]
        print(f"ROMS: {total:,}")

        print("\nCLASSIFICACAO DE DEPENDENCIAS:")
        rows = [
            ("BIOS referenciada", "r.bios IS NOT NULL AND trim(r.bios)<>''"),
            ("merge definido", "r.merge IS NOT NULL AND trim(r.merge)<>''"),
            ("status NOT FOUND", "lower(trim(COALESCE(r.status,''))) IN ('nodump','not found','notfound')"),
            ("optional explicit", "lower(trim(COALESCE(r.optional,''))) IN ('yes','true','1','on')"),
            ("dispose", "lower(trim(COALESCE(r.dispose,''))) IN ('yes','true','1','on')"),
        ]
        for label, predicate in rows:
            count = db.execute(
                f"SELECT COUNT(*) FROM mame_rom r JOIN mame_machine m ON m.id=r.machine_id WHERE m.import_id=? AND {predicate}",
                (import_id,),
            ).fetchone()[0]
            print(f"  {label:<20}: {count:>8,}")

        print("\nMERGE: SEMANTICA DO ALVO")
        same_machine = db.execute(
            """SELECT COUNT(*) FROM mame_rom r JOIN mame_machine m ON m.id=r.machine_id
               WHERE m.import_id=? AND r.merge IS NOT NULL AND trim(r.merge)<>''
               AND EXISTS (SELECT 1 FROM mame_rom b WHERE b.machine_id=r.machine_id AND b.name=r.merge)""",
            (import_id,),
        ).fetchone()[0]
        cross_machine = db.execute(
            """SELECT COUNT(*) FROM mame_rom r JOIN mame_machine m ON m.id=r.machine_id
               WHERE m.import_id=? AND r.merge IS NOT NULL AND trim(r.merge)<>''
               AND NOT EXISTS (SELECT 1 FROM mame_rom b WHERE b.machine_id=r.machine_id AND b.name=r.merge)
               AND EXISTS (
                   SELECT 1 FROM mame_machine pm
                   JOIN mame_rom b ON b.machine_id=pm.id
                   WHERE pm.import_id=m.import_id AND b.name=r.merge
               )""",
            (import_id,),
        ).fetchone()[0]
        unresolved = db.execute(
            """SELECT COUNT(*) FROM mame_rom r JOIN mame_machine m ON m.id=r.machine_id
               WHERE m.import_id=? AND r.merge IS NOT NULL AND trim(r.merge)<>''
               AND NOT EXISTS (
                   SELECT 1 FROM mame_rom b
                   WHERE b.machine_id=r.machine_id AND b.name=r.merge
               )
               AND NOT EXISTS (
                   SELECT 1 FROM mame_machine pm JOIN mame_rom b ON b.machine_id=pm.id
                   WHERE pm.import_id=m.import_id AND b.name=r.merge
               )""",
            (import_id,),
        ).fetchone()[0]
        print(f"  merge com alvo local      : {same_machine:>8,}")
        print(f"  merge resolvivel por nome : {cross_machine:>8,}")
        print(f"  merge sem alvo catalogado : {unresolved:>8,}")

        print("\nSHA1 COMPARTILHADO:")
        shared = db.execute(
            """SELECT COUNT(*) FROM (
                   SELECT sha1
                   FROM mame_rom r JOIN mame_machine m ON m.id=r.machine_id
                   WHERE m.import_id=? AND sha1 IS NOT NULL AND trim(sha1)<>''
                   GROUP BY sha1
                   HAVING COUNT(DISTINCT m.id)>1
               )""",
            (import_id,),
        ).fetchone()[0]
        print(f"  identidades em multiplas maquinas: {shared:,}")

        print("\nRELACAO ROMOF / CLONEOF:")
        clone_with_romof = db.execute(
            """SELECT COUNT(*) FROM mame_machine
               WHERE import_id=? AND cloneof IS NOT NULL AND trim(cloneof)<>''
                 AND romof IS NOT NULL AND trim(romof)<>''""",
            (import_id,),
        ).fetchone()[0]
        clone_without_romof = db.execute(
            """SELECT COUNT(*) FROM mame_machine
               WHERE import_id=? AND cloneof IS NOT NULL AND trim(cloneof)<>''
                 AND (romof IS NULL OR trim(romof)='')""",
            (import_id,),
        ).fetchone()[0]
        print(f"  clone com romof : {clone_with_romof:,}")
        print(f"  clone sem romof : {clone_without_romof:,}")

        print("\nAMOSTRA DE CASOS PARA RESOLUCAO:")
        samples = db.execute(
            """SELECT m.name,m.cloneof,m.romof,r.name,r.merge,r.bios,r.sha1
               FROM mame_machine m JOIN mame_rom r ON r.machine_id=m.id
               WHERE m.import_id=? AND r.merge IS NOT NULL AND trim(r.merge)<>''
               ORDER BY m.name,r.name LIMIT 15""",
            (import_id,),
        ).fetchall()
        for row in samples:
            print("  ", row)

        print("\nRESULTADO:")
        print("  A auditoria NAO modifica dados.")
        print("  Nenhuma ROM deve ser considerada resolvida apenas pelo nome da maquina.")
        print("  A proxima camada devera resolver identidade por SHA1/CRC e heranca")
        print("  por cloneof/romof/merge antes de montar o conjunto fisico.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
