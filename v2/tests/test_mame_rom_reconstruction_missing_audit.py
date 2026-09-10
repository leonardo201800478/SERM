"""Audita as ROMs ``merge`` que o planner nao conseguiu resolver.

Este teste e somente leitura e nao altera o planner. O objetivo e separar
``MISSING`` logico em causas verificaveis no catalogo real: alvo ausente,
alvo somente em maquina nao relacionada, alvo ambiguo, alvo em BIOS/device ou
identidade fisica coincidente por SHA1/CRC+size.
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


def _load_games(
    db: sqlite3.Connection, import_id: int
) -> tuple[ArcadeGame, ...]:
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
        romof = _text(machine["romof"])
        if romof is not None:
            metadata["romof"] = romof
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


def _build_indexes(games: tuple[ArcadeGame, ...]):
    by_name: dict[str, list[tuple[str, ArcadeRom]]] = defaultdict(list)
    by_sha1: dict[str, list[tuple[str, ArcadeRom]]] = defaultdict(list)
    by_crc_size: dict[tuple[str, int], list[tuple[str, ArcadeRom]]] = defaultdict(list)
    for game in games:
        for rom in game.roms:
            item = (game.machine_name, rom)
            by_name[_norm(rom.display_name)].append(item)
            sha1 = _norm(rom.metadata.get("sha1"))
            if sha1:
                by_sha1[sha1].append(item)
            crc = _norm(rom.metadata.get("crc"))
            size = rom.metadata.get("size")
            if crc and isinstance(size, int):
                by_crc_size[(crc, size)].append(item)
    return by_name, by_sha1, by_crc_size


def _unique_machine_count(items: list[tuple[str, ArcadeRom]]) -> int:
    return len({_norm(machine) for machine, _ in items})


def _related_machines(game: ArcadeGame, catalog: dict[str, ArcadeGame]) -> set[str]:
    related = {_norm(game.machine_name)}
    for value in (game.metadata.get("romof"), game.parent_name):
        name = _text(value)
        if name and _norm(name) in {_norm(k) for k in catalog}:
            related.add(_norm(name))
    return related


def test_audit_real_catalog_unresolved_merge_sources():
    assert DB_FILE.exists(), f"Banco nao encontrado: {DB_FILE}"

    with sqlite3.connect(DB_FILE) as db:
        import_id = _latest_import(db)
        games = _load_games(db, import_id)

    catalog = {game.machine_name: game for game in games}
    by_name, by_sha1, by_crc_size = _build_indexes(games)
    planner = ArcadeRomReconstructionPlanner()
    result = planner.plan(games)

    counters: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    missing_total = 0
    plan_index = 0

    for game in games:
        related = _related_machines(game, catalog)
        for rom in game.roms:
            plan = result.items[plan_index]
            plan_index += 1
            if not rom.metadata.get("merge") or plan.source_kind is not RomSourceKind.MISSING:
                continue

            missing_total += 1
            merge_name = str(rom.metadata["merge"])
            candidates = by_name.get(_norm(merge_name), [])
            related_candidates = [item for item in candidates if _norm(item[0]) in related]
            machine_count = _unique_machine_count(candidates)

            same_machine = [item for item in candidates if _norm(item[0]) == _norm(game.machine_name)]
            if len(same_machine) > 1:
                reason = "duplicate_same_machine"
            elif len(related_candidates) > 1:
                reason = "ambiguous_related_machine"
            elif related_candidates:
                reason = "name_target_related_but_unresolved"
            elif not candidates:
                reason = "name_absent_catalog"
            elif machine_count > 0:
                reason = "name_target_unrelated_machine"
            else:
                reason = "other"

            # A name miss can still have a physical identity match. This is
            # evidence only; it must never change planner classification here.
            sha1 = _norm(rom.metadata.get("sha1"))
            crc = _norm(rom.metadata.get("crc"))
            size = rom.metadata.get("size")
            sha_matches = by_sha1.get(sha1, []) if sha1 else []
            crc_matches = (
                by_crc_size.get((crc, int(size)), [])
                if crc and isinstance(size, int)
                else []
            )
            if sha_matches:
                counters["identity_sha1"] += 1
                if reason == "name_absent_catalog":
                    reason = "name_absent_but_sha1_match"
            elif crc_matches:
                counters["identity_crc_size"] += 1
                if reason == "name_absent_catalog":
                    reason = "name_absent_but_crc_size_match"

            # Status describes the catalog declaration, not physical presence.
            status = _norm(rom.metadata.get("status"))
            if status in {"nodump", "not found", "notfound"}:
                counters[f"status_{status.replace(' ', '_')}"] += 1

            counters[reason] += 1
            if len(examples[reason]) < 5:
                examples[reason].append(
                    f"{game.machine_name}::{rom.display_name} "
                    f"merge={merge_name} candidates={len(candidates)} "
                    f"related={len(related_candidates)}"
                )

    assert plan_index == len(result.items)
    assert missing_total == 4152, (
        "A contagem de MISSING mudou; atualize a expectativa somente apos "
        "revalidar o catalogo real."
    )

    print(f"\nIMPORT ID: {import_id}")
    print(f"MISSING MERGE: {missing_total}")
    print("CLASSIFICACAO:")
    for reason, count in counters.most_common():
        print(f"  {reason:<36}: {count:>6}")
    print("EXEMPLOS:")
    for reason in sorted(examples):
        print(f"  [{reason}]")
        for example in examples[reason]:
            print(f"    {example}")

    assert counters["duplicate_same_machine"] + counters["ambiguous_related_machine"] + counters["name_target_related_but_unresolved"] + counters["name_absent_catalog"] + counters["name_target_unrelated_machine"] == missing_total
