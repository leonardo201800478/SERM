from serm_v2.models.arcade import ArcadeGame, ArcadePlatform, ArcadeRom
from serm_v2.services.arcade.rom_reconstruction_plan import (
    ArcadeRomReconstructionPlanner,
    RomSourceKind,
)


def game(name, *, parent=None, romof=None, roms=()):
    metadata = {}
    if romof is not None:
        metadata["romof"] = romof
    return ArcadeGame(
        machine_name=name,
        display_name=name,
        platform=ArcadePlatform.MAME,
        parent_name=parent,
        roms=tuple(roms),
        metadata=metadata,
    )


def rom(machine, name, **metadata):
    return ArcadeRom(
        machine_name=machine,
        display_name=name,
        platform=ArcadePlatform.MAME,
        metadata=metadata,
    )


def test_merge_resolves_against_parent_by_rom_name():
    parent_rom = rom("parent", "shared.bin", sha1="a")
    clone_rom = rom("clone", "shared.bin", merge="shared.bin", sha1="a")
    result = ArcadeRomReconstructionPlanner().plan(
        [game("parent", roms=[parent_rom]), game("clone", parent="parent", roms=[clone_rom])]
    )

    item = next(item for item in result.items if item.machine_name == "clone")
    assert item.source_kind is RomSourceKind.MERGED
    assert item.source_machine == "parent"
    assert item.source_rom_name == "shared.bin"


def test_romof_resolves_without_parent():
    source_rom = rom("aristmk6", "bios.bin")
    derived_rom = rom("100lions", "bios.bin")
    result = ArcadeRomReconstructionPlanner().plan(
        [game("aristmk6", roms=[source_rom]), game("100lions", romof="aristmk6", roms=[derived_rom])]
    )

    item = next(item for item in result.items if item.machine_name == "100lions")
    assert item.source_kind is RomSourceKind.ROMOF
    assert item.source_machine == "aristmk6"


def test_self_merge_does_not_create_external_dependency():
    self_rom = rom("set1", "local.bin", merge="local.bin")
    result = ArcadeRomReconstructionPlanner().plan([game("set1", roms=[self_rom])])

    item = result.items[0]
    assert item.source_kind is RomSourceKind.SELF
    assert item.source_machine == "set1"


def test_unresolved_merge_is_missing_not_self_fallback():
    unresolved = rom("clone", "missing.bin", merge="source.bin")
    result = ArcadeRomReconstructionPlanner().plan([game("clone", roms=[unresolved])])

    item = result.items[0]
    assert item.source_kind is RomSourceKind.MISSING
    assert item.source_machine is None
    assert item.source_rom_name == "source.bin"


def test_ambiguous_global_merge_name_is_not_guessed():
    source_a = rom("source_a", "shared.bin")
    source_b = rom("source_b", "shared.bin")
    clone_rom = rom("clone", "clone.bin", merge="shared.bin")
    result = ArcadeRomReconstructionPlanner().plan(
        [game("source_a", roms=[source_a]), game("source_b", roms=[source_b]), game("clone", roms=[clone_rom])]
    )

    item = next(item for item in result.items if item.machine_name == "clone")
    assert item.source_kind is RomSourceKind.MISSING
    assert item.source_machine is None


def test_unique_global_merge_name_without_relationship_is_not_guessed():
    source = rom("unrelated", "unique.bin", sha1="a")
    clone_rom = rom("clone", "clone.bin", merge="unique.bin")
    result = ArcadeRomReconstructionPlanner().plan(
        [game("unrelated", roms=[source]), game("clone", roms=[clone_rom])]
    )

    item = next(item for item in result.items if item.machine_name == "clone")
    assert item.source_kind is RomSourceKind.MISSING
    assert item.source_machine is None
    assert item.source_rom_name == "unique.bin"
