"""Valida o planejador de reconstrucao contra o catalogo MAME real.

O teste e somente leitura. Ele converte o ultimo import ListXML concluido
para os modelos de dominio do V2 e compara a decisao do planejador com as
evidencias relacionais do proprio catalogo.

Para uma ROM que possui ``merge``, ``merge`` identifica a ROM de origem. O
``romof``/``cloneof`` da maquina identifica em qual machine set relacionado
essa ROM pode ser localizada. Por isso a origem resolvida por ``merge`` e
classificada como ``MERGED`` quando vem de outra maquina, mesmo que a maquina
seja alcancada pela relacao ``romof``. ``ROMOF`` e ``PARENT`` ficam reservados
para a heranca por mesmo nome de ROM quando nao existe ``merge`` explicito.
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
        for key in ("merge", "sha1", "crc", "status"):
            value = _text(row[key])
            if value is not None:
                metadata[key] = value
        if row["size"] is not None:
            metadata["size"] = row["size"]
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


def _build_relation_index(
    games: tuple[ArcadeGame, ...],
) -> dict[str, tuple[tuple[str, ArcadeRom], ...]]:
    index: dict[str, list[tuple[str, ArcadeRom]]] = defaultdict(list)
    for game in games:
        for rom in game.roms:
            index[_norm(rom.display_name)].append((game.machine_name, rom))
    return {name: tuple(items) for name, items in index.items()}


def _expected_source(
    game: ArcadeGame,
    rom: ArcadeRom,
    relation_index: dict[str, tuple[tuple[str, ArcadeRom], ...]],
) -> tuple[RomSourceKind, str | None, str]:
    merge_name = _text(rom.metadata.get("merge"))
    assert merge_name
    candidates = relation_index.get(_norm(merge_name), ())
    romof = _text(game.metadata.get("romof"))
    parent_name = _text(game.parent_name)

    # Para merge, o atributo identifica explicitamente a ROM de origem.
    # A relacao da maquina apenas restringe onde essa ROM pode ser procurada.
    # Portanto, uma origem em outra maquina e MERGED, independentemente de a
    # maquina ter sido encontrada por romof ou cloneof/parent.
    for machine_name in (game.machine_name, romof, parent_name):
        if not machine_name:
            continue
        matches = tuple(
            item for item in candidates if _norm(item[0]) == _norm(machine_name)
        )
        if len(matches) == 1:
            if _norm(matches[0][0]) == _norm(game.machine_name):
                return RomSourceKind.SELF, matches[0][0], matches[0][1].display_name
            return RomSourceKind.MERGED, matches[0][0], matches[0][1].display_name
        if len(matches) > 1:
            return RomSourceKind.MISSING, None, "ambiguous"

    return RomSourceKind.MISSING, None, "unresolved"


def test_real_catalog_planner_matches_relation_evidence():
    assert DB_FILE.exists(), f"Banco nao encontrado: {DB_FILE}"

    with sqlite3.connect(DB_FILE) as db:
        import_id = _latest_import(db)
        games = _load_games(db, import_id)

    assert games, "Catalogo MAME vazio."
    relation_index = _build_relation_index(games)
    result = ArcadeRomReconstructionPlanner().plan(games)

    expected_counts: Counter[RomSourceKind] = Counter()
    actual_counts: Counter[RomSourceKind] = Counter()
    checked = 0
    mismatches: list[str] = []
    plan_index = 0

    for game in games:
        for rom in game.roms:
            actual = result.items[plan_index]
            plan_index += 1
            merge_name = _text(rom.metadata.get("merge"))
            if merge_name is None:
                continue

            expected_kind, expected_machine, expected_rom = _expected_source(
                game, rom, relation_index
            )
            expected_counts[expected_kind] += 1
            actual_counts[actual.source_kind] += 1
            checked += 1

            if actual.source_kind is not expected_kind:
                mismatches.append(
                    f"{game.machine_name}::{rom.display_name} "
                    f"merge={merge_name} expected={expected_kind.value} "
                    f"actual={actual.source_kind.value}"
                )
                continue

            # MISSING deliberadamente preserva o nome de merge como
            # source_rom_name. A evidencia "ambiguous"/"unresolved" nao e um
            # nome de ROM e nao deve ser comparada ao plano. O contrato a ser
            # validado nesse caso e exclusivamente a classificacao MISSING.
            if actual.source_kind is RomSourceKind.MISSING:
                continue

            if expected_machine is not None and _norm(actual.source_machine) != _norm(expected_machine):
                mismatches.append(
                    f"{game.machine_name}::{rom.display_name} "
                    f"merge={merge_name} expected_machine={expected_machine} "
                    f"actual_machine={actual.source_machine}"
                )
                continue
            if _norm(actual.source_rom_name) != _norm(expected_rom):
                mismatches.append(
                    f"{game.machine_name}::{rom.display_name} "
                    f"merge={merge_name} expected_rom={expected_rom} "
                    f"actual_rom={actual.source_rom_name}"
                )

    assert plan_index == len(result.items)
    print(f"\nIMPORT ID: {import_id}")
    print(f"MAQUINAS: {len(games)}")
    print(f"ROMS COM MERGE VERIFICADAS: {checked}")
    print("EVIDENCIA ESPERADA:")
    for kind in RomSourceKind:
        print(f"  {kind.value:<10}: {expected_counts[kind]:>8}")
    print("DECISAO DO PLANNER:")
    for kind in RomSourceKind:
        print(f"  {kind.value:<10}: {actual_counts[kind]:>8}")
    print(f"DIVERGENCIAS: {len(mismatches)}")
    if mismatches:
        print("PRIMEIRAS DIVERGENCIAS:")
        for mismatch in mismatches[:20]:
            print(f"  {mismatch}")

    assert checked > 0, "Nenhuma ROM com merge foi encontrada no catalogo real."
    assert not mismatches, "Planner divergiu da evidencia relacional do catalogo real."
