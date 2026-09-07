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
    parent_name: str | None = None,
    metadata: dict[str, object] | None = None,
    roms: list[ArcadeRom] | None = None,
) -> ArcadeGame:
    return ArcadeGame(
        machine_name=machine,
        display_name=machine,
        platform="mame",
        parent_name=parent_name,
        metadata=metadata or {},
        roms=tuple(roms or ()),
    )


def test_merge_resolves_against_parent_by_rom_name():
    parent_rom = rom("parent", "shared.bin")
    clone_rom = rom("clone", "clone.bin", merge="shared.bin")

    result = ArcadeRomReconstructionPlanner().plan(
        [
            game("parent", roms=[parent_rom]),
            game("clone", parent_name="parent", roms=[clone_rom]),
        ]
    )

    item = result.items[1]
    assert item.source_kind is RomSourceKind.MERGED
    assert item.source_machine == "parent"
    assert item.source_rom_name == "shared.bin"


def test_romof_resolves_without_parent():
    source_rom = rom("source", "shared.bin")
    clone_rom = rom("clone", "clone.bin", romof="source")

    result = ArcadeRomReconstructionPlanner().plan(
        [game("source", roms=[source_rom]), game("clone", roms=[clone_rom])]
    )

    item = result.items[1]
    assert item.source_kind is RomSourceKind.ROMOF
    assert item.source_machine == "source"


def test_self_merge_does_not_create_external_dependency():
    self_rom = rom("set1", "local.bin", merge="local.bin")
    result = ArcadeRomReconstructionPlanner().plan([game("set1", roms=[self_rom])])

    item = result.items[0]
    assert item.source_kind is RomSourceKind.SELF
    assert item.source_machine == "set1"
    assert item.source_rom_name == "local.bin"


def test_unresolved_merge_is_missing_not_self_fallback():
    clone_rom = rom("clone", "clone.bin", merge="missing.bin")
    result = ArcadeRomReconstructionPlanner().plan([game("clone", roms=[clone_rom])])

    item = result.items[0]
    assert item.source_kind is RomSourceKind.MISSING
    assert item.source_machine is None


def test_ambiguous_global_merge_name_is_not_guessed():
    result = ArcadeRomReconstructionPlanner().plan(
        [
            game("source-a", roms=[rom("source-a", "shared.bin")]),
            game("source-b", roms=[rom("source-b", "shared.bin")]),
            game("clone", roms=[rom("clone", "clone.bin", merge="shared.bin")]),
        ]
    )

    item = result.items[2]
    assert item.source_kind is RomSourceKind.MISSING
    assert item.source_machine is None


def test_unique_global_merge_name_without_relationship_is_not_guessed():
    result = ArcadeRomReconstructionPlanner().plan(
        [
            game("unrelated", roms=[rom("unrelated", "shared.bin")]),
            game("clone", roms=[rom("clone", "clone.bin", merge="shared.bin")]),
        ]
    )

    item = result.items[1]
    assert item.source_kind is RomSourceKind.MISSING
    assert item.source_machine is None
