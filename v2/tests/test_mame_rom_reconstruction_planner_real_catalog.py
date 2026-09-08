"""Valida o planejador de reconstrucao contra o catalogo MAME real.

O teste e somente leitura. Ele converte o ultimo import ListXML concluido
para os modelos de dominio do V2 e compara a decisao do planejador com as
evidencias relacionais do proprio catalogo.
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
        FROM mame_machine
        WHERE import_id = ?
        ORDER BY id
        """,
        (import_id,),
    ).fetchall()

    roms_by_machine: dict[int, list[ArcadeRom]] = defaultdict(list)
    rows = db.execute(
        """
        SELECT r.machine_id, r.name, r.merge, r.sha1, r.crc, r.size, r.status
        FROM mame_rom r
        JOIN mame_machine m ON m.id = r.machine_id
        WHERE m.import_id = ?
        ORDER BY r.machine_id, r.id
        """,
        (import_id,),
    )
    for row in rows:
        metadata: dict[str, object] = {}
        if _text(row["merge"]):
            metadata["merge"] = row["merge"]
        if _text(row["sha1"]):
            metadata["sha1"] = row["sha1"]
        if _text(row["crc"]):
            metadata["crc"] = row["crc"]
        if row["size"] is not None:
            metadata["size"] = row["size"]
        if _text(row["status"]):
            metadata["status"] = row["status"]
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
        machine_name = str(machine["name"])
        roms = tuple(
            ArcadeRom(
                machine_name=machine_name,
                display_name=rom.display_name,
                platform=ArcadePlatform.MAME,
                metadata=rom.metadata,
            )
            for rom in roms_by_machine.get(int(machine["id"]), ())
        )
        metadata: dict[str, object] = {}
        if _text(machine["romof"]):
            metadata["romof"] = machine["romof"]
        games.append(
            ArcadeGame(
                machine_name=machine_name,
                display_name=_text(machine["description"]) or machine_name,
                platform=ArcadePlatform.MAME,
                parent_name=_text(machine["cloneof"]),
                roms=roms,
                metadata=metadata,
            )
        )
    return tuple(games)


def _load_merge_rows(
    db: sqlite3.Connection, import_id: int
) -> list[sqlite3.Row]:
    db.row_factory = sqlite3.Row
    return db.execute(
        """
        SELECT r.machine_id, m.name AS machine_name,
               r.name AS rom_name, r.merge AS merge_name,
               m.cloneof, m.romof
        FROM mame_rom r
        JOIN mame_machine m ON m.id = r.machine_id
        WHERE m.import_id = ?
          AND trim(COALESCE(r.merge, '')) <> ''
        ORDER BY r.machine_id, r.id
        """,
        (import_id,),
    ).fetchall()


def _find_source(
    game: ArcadeGame,
    rom: sqlite3.Row,
    games_by_name: dict[str, ArcadeGame],
) -> tuple[RomSourceKind, str | None, str]:
    """Resolve a real row using the same explicit MAME relations as the planner."""
    merge_name = _text(rom["merge_name"])
    assert merge_name
    candidates: list[tuple[str, ArcadeRom]] = []
    normalized = _norm(merge_name)
    for candidate_game in games_by_name.values():
        for candidate_rom in candidate_game.roms:
            if _norm(candidate_rom.display_name) == normalized:
                candidates.append((candidate_game.machine_name, candidate_rom))

    preferred = (
        (RomSourceKind.SELF, game.machine_name),
        (RomSourceKind.ROMOF, _text(rom["romof"])),
        (RomSourceKind.PARENT, _text(rom["cloneof"])),
    )
    for kind, machine_name in preferred:
        if not machine_name:
            continue
        matches = tuple(
            item for item in candidates if _norm(item[0]) == _norm(machine_name)
        )
        if len(matches) == 1:
            return kind, matches[0][0], matches[0][1].display_name
        if len(matches) > 1:
            return RomSourceKind.MISSING, None, "ambiguous"
    return RomSourceKind.MISSING, None, "unresolved"


def test_real_catalog_planner_matches_relation_evidence():
    assert DB_FILE.exists(), f"Banco nao encontrado: {DB_FILE}"

    with sqlite3.connect(DB_FILE) as db:
        import_id = _latest_import(db)
        games = _load_games(db, import_id)
        merge_rows = _load_merge_rows(db, import_id)

    assert games, "Catalogo MAME vazio."
    assert merge_rows, "Nenhuma ROM com merge no catalogo real."

    result = ArcadeRomReconstructionPlanner().plan(games)
    planned_by_key: dict[tuple[str, str], list] = defaultdict(list)
    for item in result.items:
        if item.source_kind is not RomSourceKind.MISSING or item.rom_name:
            planned_by_key[(_norm(item.machine_name), _norm(item.rom_name))].append(item)

    games_by_name = {_norm(game.machine_name): game for game in games}
    expected_counts: Counter[RomSourceKind] = Counter()
    actual_counts: Counter[RomSourceKind] = Counter()
    checked = 0
    mismatches: list[str] = []

    for row in merge_rows:
        game = games_by_name[_norm(row["machine_name"])]
        expected_kind, expected_machine, expected_rom = _find_source(
            game, row, games_by_name
        )
        key = (_norm(row["machine_name"]), _norm(row["rom_name"]))
        candidates = planned_by_key[key]
        matching = [
            item
            for item in candidates
            if _norm(item.source_rom_name) == _norm(row["merge_name"])
        ]

        expected_counts[expected_kind] += 1
        if len(matching) != 1:
            mismatches.append(
                f"{row['machine_name']}::{row['rom_name']} "
                f"merge={row['merge_name']} planner_items={len(matching)}"
            )
            continue

        actual = matching[0]
        actual_counts[actual.source_kind] += 1
        checked += 1
        if actual.source_kind is not expected_kind:
            mismatches.append(
                f"{row['machine_name']}::{row['rom_name']} "
                f"expected={expected_kind.value} actual={actual.source_kind.value}"
            )
        elif expected_machine is not None and _norm(actual.source_machine) != _norm(expected_machine):
            mismatches.append(
                f"{row['machine_name']}::{row['rom_name']} "
                f"expected_machine={expected_machine} actual_machine={actual.source_machine}"
            )
        elif _norm(actual.source_rom_name) != _norm(expected_rom):
            mismatches.append(
                f"{row['machine_name']}::{row['rom_name']} "
                f"expected_rom={expected_rom} actual_rom={actual.source_rom_name}"
            )

    print(f"\nIMPORT ID: {import_id}")
    print(f"MAQUINAS: {len(games)}")
    print(f"ROMS COM MERGE VERIFICADAS: {len(merge_rows)}")
    print("EVIDENCIA ESPERADA:")
    for kind in RomSourceKind:
        print(f"  {kind.value:<10}: {expected_counts[kind]:>8}")
    print("DECISAO DO PLANNER:")
    for kind in RomSourceKind:
        print(f"  {kind.value:<10}: {actual_counts[kind]:>8}")
    print(f"CORRESPONDENCIAS UNICAS: {checked}")
    print(f"DIVERGENCIAS: {len(mismatches)}")
    if mismatches:
        print("PRIMEIRAS DIVERGENCIAS:")
        for mismatch in mismatches[:20]:
            print(f"  {mismatch}")

    assert not mismatches, "Planner divergiu da evidencia relacional do catalogo real."
    assert checked == len(merge_rows), "Nem todas as ROMs com merge tiveram correspondencia unica."
