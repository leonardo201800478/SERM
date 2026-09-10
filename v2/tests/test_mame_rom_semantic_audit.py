"""Auditoria semantica da identidade e heranca de ROMs MAME.

Nao modifica o banco. Mede somente os relacionamentos que serao usados
pelo filtro e pelo planejador de reconstrucao.
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
        print("AUDITORIA SEMANTICA DA ARVORE DE ROMS MAME")
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

        total_machines = db.execute(
            "SELECT COUNT(*) FROM mame_machine WHERE import_id=?", (import_id,)
        ).fetchone()[0]
        total_roms = db.execute(
            "SELECT COUNT(*) FROM mame_rom r JOIN mame_machine m ON m.id=r.machine_id WHERE m.import_id=?",
            (import_id,),
        ).fetchone()[0]
        total_disks = db.execute(
            "SELECT COUNT(*) FROM mame_disk d JOIN mame_machine m ON m.id=d.machine_id WHERE m.import_id=?",
            (import_id,),
        ).fetchone()[0]

        print(f"MACHINES: {total_machines:,}")
        print(f"ROMS:     {total_roms:,}")
        print(f"DISKS:    {total_disks:,}")

        print("\nHERANCA DE MAQUINAS:")
        clone_count = db.execute(
            "SELECT COUNT(*) FROM mame_machine WHERE import_id=? AND cloneof IS NOT NULL AND trim(cloneof)<>''",
            (import_id,),
        ).fetchone()[0]
        romof_count = db.execute(
            "SELECT COUNT(*) FROM mame_machine WHERE import_id=? AND romof IS NOT NULL AND trim(romof)<>''",
            (import_id,),
        ).fetchone()[0]
        sampleof_count = db.execute(
            "SELECT COUNT(*) FROM mame_machine WHERE import_id=? AND sampleof IS NOT NULL AND trim(sampleof)<>''",
            (import_id,),
        ).fetchone()[0]
        print(f"  cloneof definido : {clone_count:,}")
        print(f"  romof definido   : {romof_count:,}")
        print(f"  sampleof definido: {sampleof_count:,}")

        print("\nREFERENCIAS DE HERANCA INEXISTENTES:")
        for field in ("cloneof", "romof", "sampleof"):
            count = db.execute(
                f"""SELECT COUNT(*)
                    FROM mame_machine child
                    WHERE child.import_id=?
                      AND child.{field} IS NOT NULL
                      AND trim(child.{field})<>''
                      AND NOT EXISTS (
                          SELECT 1 FROM mame_machine parent
                          WHERE parent.import_id=child.import_id
                            AND parent.name=child.{field}
                      )""",
                (import_id,),
            ).fetchone()[0]
            print(f"  {field:<9}: {count:,}")

        print("\nIDENTIDADE DE ROM:")
        for label, where in (
            ("com SHA1", "sha1 IS NOT NULL AND trim(sha1)<>''"),
            ("com CRC", "crc IS NOT NULL AND trim(crc)<>''"),
            ("com MD5", "md5 IS NOT NULL AND trim(md5)<>''"),
            ("com merge", "merge IS NOT NULL AND trim(merge)<>''"),
            ("opcionais", "optional IS NOT NULL AND lower(trim(optional)) IN ('yes','true','1','on')"),
            ("BIOS", "bios IS NOT NULL AND trim(bios)<>''"),
        ):
            count = db.execute(
                f"""SELECT COUNT(*) FROM mame_rom r
                    JOIN mame_machine m ON m.id=r.machine_id
                    WHERE m.import_id=? AND {where}""",
                (import_id,),
            ).fetchone()[0]
            print(f"  {label:<12}: {count:,}")

        print("\nROMS COM MESMO SHA1 EM MAQUINAS DIFERENTES:")
        duplicate_sha1 = db.execute(
            """SELECT COUNT(*) FROM (
                   SELECT sha1
                   FROM mame_rom r JOIN mame_machine m ON m.id=r.machine_id
                   WHERE m.import_id=? AND sha1 IS NOT NULL AND trim(sha1)<>''
                   GROUP BY sha1
                   HAVING COUNT(DISTINCT r.machine_id)>1
               )""",
            (import_id,),
        ).fetchone()[0]
        print(f"  SHA1 compartilhados : {duplicate_sha1:,}")

        print("\nROM MERGE SEM ALVO NO MESMO IMPORT:")
        missing_merge = db.execute(
            """SELECT COUNT(*)
               FROM mame_rom r
               JOIN mame_machine m ON m.id=r.machine_id
               WHERE m.import_id=?
                 AND r.merge IS NOT NULL AND trim(r.merge)<>''
                 AND NOT EXISTS (
                     SELECT 1 FROM mame_rom base
                     WHERE base.machine_id=r.machine_id
                       AND base.name=r.merge
                 )""",
            (import_id,),
        ).fetchone()[0]
        print(f"  merge sem ROM alvo : {missing_merge:,}")

        print("\nAMOSTRA DE ROMS COM MERGE:")
        rows = db.execute(
            """SELECT m.name,r.name,r.merge,r.region,r.bios,r.optional
               FROM mame_rom r JOIN mame_machine m ON m.id=r.machine_id
               WHERE m.import_id=? AND r.merge IS NOT NULL AND trim(r.merge)<>''
               ORDER BY m.name,r.name LIMIT 10""",
            (import_id,),
        ).fetchall()
        for row in rows:
            print("  ", row)

        print("\nRESULTADO:")
        print("  A auditoria NAO modifica dados.")
        print("  Os numeros acima definem as regras de identidade, heranca e dependencia")
        print("  que o filtro de componentes e o planejador de reconstrucao deverao respeitar.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
