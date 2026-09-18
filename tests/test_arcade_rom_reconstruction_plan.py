from serm_v2.models.arcade import ArcadeGame, ArcadePlatform, ArcadeRom
from serm_v2.services.arcade.rom_reconstruction_plan import (
    ArcadeRomReconstructionPlanner,
    RomSourceKind,
)


def rom(name: str, **metadata: object) -> ArcadeRom:
    return ArcadeRom(
        machine_name=name,
        display_name=name,
        platform=ArcadePlatform.MAME,
        metadata=metadata,
    )


def game(name: str, parent: str | None = None, roms=(), **metadata: object) -> ArcadeGame:
    return ArcadeGame(
        machine_name=name,
        display_name=name,
        platform=ArcadePlatform.MAME,
        parent_name=parent,
        roms=tuple(roms),
        metadata=metadata,
    )


def test_merge_prefers_parent_rom() -> None:
    parent = game("parent", roms=[rom("common.bin")])
    clone = game("clone", "parent", [rom("clone.bin", merge="common.bin")])

    result = ArcadeRomReconstructionPlanner().plan([parent, clone])

    item = result.items[1]
    assert item.source_kind is RomSourceKind.MERGED
    assert item.source_machine == "parent"
    assert item.source_rom_name == "common.bin"


def test_romof_resolves_to_declared_machine() -> None:
    base = game("base", roms=[rom("shared.bin")])
    clone = game("clone", roms=[rom("shared.bin", romof="base")])

    result = ArcadeRomReconstructionPlanner().plan([base, clone])

    item = result.items[1]
    assert item.source_kind is RomSourceKind.ROMOF
    assert item.source_machine == "base"


def test_parent_same_rom_name_is_dependency() -> None:
    parent = game("parent", roms=[rom("common.bin")])
    clone = game("clone", "parent", [rom("common.bin")])

    result = ArcadeRomReconstructionPlanner().plan([parent, clone])

    assert result.items[1].source_kind is RomSourceKind.PARENT


def test_unique_rom_stays_on_self() -> None:
    result = ArcadeRomReconstructionPlanner().plan([game("game", roms=[rom("unique.bin")])])

    item = result.items[0]
    assert item.source_kind is RomSourceKind.SELF
    assert item.source_machine == "game"
