"""Audita duplicidades de ROM ``merge`` dentro do mesmo machine set.

O teste e somente leitura. Ele verifica se os 4.148 casos que ficaram
ambiguous por nome sao duplicidades reais da mesma identidade ou registros
com identidades fisicas distintas. Nenhuma regra do planner e alterada aqui.
"""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from serm_v2.models.arcade import ArcadeGame, ArcadePlatform, ArcadeRom
from serm_v2.services.arcade.rom_reconstruction_plan import (
    ArcadeRomReconstructionPlanner,
    RomSourceKind,
)

DB_FILE = Path(__file__).resolve().parents[1] / "data" / "database" / "serm.db"


def _latest_import(db: sqlite3.Connection) -> int:
    row = db.execute(
        "SELECT id FROM mame_listxml_import "
        "WHERE status='completed' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None, "Nenhuma importacao ListXML concluida."
    return int(row[0])


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _norm(value: object) -> str:
    return str(value or "").strip().casefold()


def _load_games(db: sqlite3.Connection, import_id: int) -> tuple[ArcadeGame, ...]:
    db.row_factory = sqlite3.Row
    machines = db.execute(
        """
        SELECT id, name, description, cloneof, romof
        FROM mame_machine WHERE import_id = ? ORDER BY id
        """,
        (import_id,),
    ).fetchall()
    roms_by_machine: dict[int, list[ArcadeRom]] = defaultdict(list)
    rows = db.execute(
        """
        SELECT r.machine_id, r.name, r.merge, r.sha1, r.crc, r.size, r.status
        FROM mame_rom r
        JOIN mame_machine m ON m.id = r.machine_id
        WHERE m.import_id = ? ORDER BY r.machine_id, r.id
        """,
        (import_id,),
    )
    for row in rows:
        metadata: dict[str, object] = {}
        for key in ("merge", "sha1", "crc", "status"):
            value = _text(row[key])
            if value is not None:
                metadata[key] = value
        if row["size"] is not None:
            metadata["size"] = int(row["size"])
        roms_by_machine[int(row["machine_id"])].append(
            ArcadeRom(
                machine_name="",
                display_name=str(row["name"]),
                platform=ArcadePlatform.MAME,
                metadata=metadata,
            )
        )
    games: list[ArcadeGame] = []
    for machine in machines:
        name = str(machine["name"])
        games.append(
            ArcadeGame(
                machine_name=name,
                display_name=_text(machine["description"]) or name,
                platform=ArcadePlatform.MAME,
                parent_name=_text(machine["cloneof"]),
                roms=tuple(
                    ArcadeRom(
                        machine_name=name,
                        display_name=rom.display_name,
                        platform=ArcadePlatform.MAME,
                        metadata=rom.metadata,
                    )
                    for rom in roms_by_machine.get(int(machine["id"]), ())
                ),
                metadata={
                    "romof": _text(machine["romof"]),
                },
            )
        )
    return tuple(games)


def _identity(rom: ArcadeRom) -> tuple[str, str, object]:
    return (
        _norm(rom.metadata.get("sha1")),
        _norm(rom.metadata.get("crc")),
        rom.metadata.get("size"),
    )


def test_audit_same_machine_duplicate_merge_identities():
    assert DB_FILE.exists(), f"Banco nao encontrado: {DB_FILE}"
    with sqlite3.connect(DB_FILE) as db:
        import_id = _latest_import(db)
        games = _load_games(db, import_id)

    result = ArcadeRomReconstructionPlanner().plan(games)
    counters: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    duplicate_groups = 0
    duplicate_rows = 0
    plan_index = 0

    for game in games:
        by_name: dict[str, list[ArcadeRom]] = defaultdict(list)
        for rom in game.roms:
            by_name[_norm(rom.display_name)].append(rom)

        for rom_name, group in by_name.items():
            merge_rows = [rom for rom in group if _text(rom.metadata.get("merge"))]
            if not merge_rows:
                continue
            if len(group) <= 1:
                continue

            identities = {_identity(rom) for rom in group}
            merge_names = {_norm(rom.metadata.get("merge")) for rom in merge_rows}
            duplicate_groups += 1
            duplicate_rows += len(group)

            if len(identities) == 1:
                reason = "identical_identity"
            elif all(identity[0] for identity in identities) and len({identity[0] for identity in identities}) == 1:
                reason = "same_sha1_different_secondary"
            elif len({(identity[1], identity[2]) for identity in identities}) == 1:
                reason = "same_crc_size_different_sha1"
            else:
                reason = "different_identity"

            if len(merge_names) > 1:
                counters["different_merge_names"] += 1

            counters[reason] += 1
            if len(examples[reason]) < 10:
                example_identities = ", ".join(
                    f"sha1={identity[0][:12] or '-'} crc={identity[1] or '-'} size={identity[2]}"
                    for identity in sorted(identities, key=str)
                )
                examples[reason].append(
                    f"{game.machine_name}::{rom_name} rows={len(group)} "
                    f"merge={sorted(merge_names)} identities=[{example_identities}]"
                )

        # Keep planner/result alignment explicit even though this audit does
        # not use individual plan decisions for classification.
        plan_index += len(game.roms)

    assert plan_index == len(result.items)
    assert duplicate_groups > 0

    print(f"\nIMPORT ID: {import_id}")
    print(f"GRUPOS DUPLICADOS COM MERGE: {duplicate_groups}")
    print(f"LINHAS NOS GRUPOS: {duplicate_rows}")
    print("CLASSIFICACAO DE IDENTIDADE:")
    for reason, count in counters.most_common():
        print(f"  {reason:<36}: {count:>6}")
    print("EXEMPLOS:")
    for reason in sorted(examples):
        print(f"  [{reason}]")
        for example in examples[reason]:
            print(f"    {example}")
