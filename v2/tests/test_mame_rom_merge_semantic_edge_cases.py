"""Casos limite da semantica de merge MAME.

Suite rapida, sem banco real. O objetivo e detectar regressao no contrato do
planejador antes de executar auditorias sobre o catalogo completo.
"""

from serm_v2.models.arcade import ArcadeGame, ArcadeRom
from serm_v2.services.arcade.rom_reconstruction_plan import (
    ArcadeRomReconstructionPlanner,
    RomSourceKind,
)


def rom(machine: str, name: str, **metadata: object) -> ArcadeRom:
    return ArcadeRom(
        machine_name=machine,
        display_name=name,
        platform="mame",
        metadata=metadata,
    )


def game(
    machine: str,
    *,
    parent: str | None = None,
    romof: str | None = None,
    metadata: dict[str, object] | None = None,
    roms: list[ArcadeRom],
) -> ArcadeGame:
    values = dict(metadata or {})
    if romof is not None:
        values["romof"] = romof
    return ArcadeGame(
        machine_name=machine,
        display_name=machine,
        platform="mame",
        parent_name=parent,
        metadata=values,
        roms=tuple(roms),
    )


def plan(*games: ArcadeGame):
    return ArcadeRomReconstructionPlanner().plan(games).items


def test_names_are_case_insensitive_for_merge_resolution():
    items = plan(
        game("parent", roms=[rom("parent", "Shared.BIN")]),
        game(
            "clone",
            parent="parent",
            roms=[rom("clone", "local.bin", merge="shared.bin")],
        ),
    )

    assert items[1].source_kind is RomSourceKind.MERGED
    assert items[1].source_machine == "parent"
    assert items[1].source_rom_name == "Shared.BIN"


def test_missing_romof_does_not_fabricate_dependency():
    items = plan(
        game("clone", roms=[rom("clone", "local.bin")], romof="does-not-exist"),
    )

    assert items[0].source_kind is RomSourceKind.SELF
    assert items[0].source_machine == "clone"


def test_missing_parent_does_not_fabricate_dependency():
    items = plan(
        game(
            "clone",
            parent="does-not-exist",
            roms=[rom("clone", "local.bin")],
        ),
    )

    assert items[0].source_kind is RomSourceKind.SELF
    assert items[0].source_machine == "clone"


def test_merge_with_explicit_romof_prefers_romof_target():
    items = plan(
        game("rom-source", roms=[rom("rom-source", "shared.bin")]),
        game("parent", roms=[rom("parent", "shared.bin")]),
        game(
            "clone",
            parent="parent",
            romof="rom-source",
            roms=[rom("clone", "local.bin", merge="shared.bin")],
        ),
    )

    assert items[2].source_kind is RomSourceKind.MERGED
    assert items[2].source_machine == "rom-source"


def test_merge_with_parent_and_unrelated_duplicate_stays_parent_bound():
    items = plan(
        game("parent", roms=[rom("parent", "shared.bin")]),
        game("unrelated", roms=[rom("unrelated", "shared.bin")]),
        game(
            "clone",
            parent="parent",
            roms=[rom("clone", "local.bin", merge="shared.bin")],
        ),
    )

    assert items[2].source_kind is RomSourceKind.MERGED
    assert items[2].source_machine == "parent"


def test_parent_inheritance_is_used_when_same_name_exists_only_in_parent():
    items = plan(
        game("parent", roms=[rom("parent", "shared.bin")]),
        game(
            "clone",
            parent="parent",
            roms=[rom("clone", "shared.bin")],
        ),
    )

    assert items[1].source_kind is RomSourceKind.PARENT
    assert items[1].source_machine == "parent"


def test_identical_duplicate_rom_identity_inside_target_machine_is_resolved():
    items = plan(
        game(
            "parent",
            roms=[
                rom(
                    "parent",
                    "shared.bin",
                    sha1="1111111111111111111111111111111111111111",
                    crc="aaaaaaaa",
                    size=256,
                ),
                rom(
                    "parent",
                    "shared.bin",
                    sha1="1111111111111111111111111111111111111111",
                    crc="aaaaaaaa",
                    size=256,
                ),
            ],
        ),
        game(
            "clone",
            parent="parent",
            roms=[rom("clone", "local.bin", merge="shared.bin")],
        ),
    )

    assert items[2].source_kind is RomSourceKind.MERGED
    assert items[2].source_machine == "parent"
    assert items[2].source_rom_name == "shared.bin"


def test_duplicate_rom_name_with_different_identity_stays_ambiguous():
    items = plan(
        game(
            "parent",
            roms=[
                rom(
                    "parent",
                    "shared.bin",
                    sha1="1111111111111111111111111111111111111111",
                    crc="aaaaaaaa",
                    size=256,
                ),
                rom(
                    "parent",
                    "shared.bin",
                    sha1="2222222222222222222222222222222222222222",
                    crc="bbbbbbbb",
                    size=512,
                ),
            ],
        ),
        game(
            "clone",
            parent="parent",
            roms=[rom("clone", "local.bin", merge="shared.bin")],
        ),
    )

    assert items[2].source_kind is RomSourceKind.MISSING
    assert items[2].source_machine is None


def test_merge_target_with_different_identity_is_still_logically_resolved():
    items = plan(
        game(
            "parent",
            roms=[
                rom(
                    "parent",
                    "shared.bin",
                    sha1="1111111111111111111111111111111111111111",
                )
            ],
        ),
        game(
            "clone",
            parent="parent",
            roms=[
                rom(
                    "clone",
                    "local.bin",
                    merge="shared.bin",
                    sha1="2222222222222222222222222222222222222222",
                )
            ],
        ),
    )

    assert items[1].source_kind is RomSourceKind.MERGED
    assert items[1].source_machine == "parent"


def test_merge_and_romof_machine_relationships_are_not_confused_with_rom_name():
    items = plan(
        game("source", roms=[rom("source", "machine-name")]),
        game(
            "clone",
            romof="source",
            roms=[rom("clone", "local.bin", merge="source")],
        ),
    )

    assert items[1].source_kind is RomSourceKind.MISSING
    assert items[1].source_machine is None
