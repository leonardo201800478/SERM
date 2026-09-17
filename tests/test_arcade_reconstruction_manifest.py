from serm_v2.models.arcade import ArcadeDisk, ArcadeGame, ArcadePlatform, ArcadeRom, ArcadeSetType
from serm_v2.services.arcade.chd_reconstruction import ArcadeChdReconstructionEngine, PhysicalChd
from serm_v2.services.arcade.reconstruction_manifest import (
    ArcadeReconstructionManifestBuilder,
    MaterializationKind,
)
from serm_v2.services.arcade.rom_reconstruction import (
    ArcadeRomReconstructionEngine,
    PhysicalRom,
    ReconstructionResult,
)


def game(name: str, *, parent: str | None = None, roms=(), disks=()) -> ArcadeGame:
    return ArcadeGame(
        machine_name=name,
        display_name=name,
        platform=ArcadePlatform.MAME,
        parent_name=parent,
        roms=tuple(roms),
        disks=tuple(disks),
    )


def rom(name: str, **metadata: object) -> ArcadeRom:
    return ArcadeRom(name, name, ArcadePlatform.MAME, metadata=metadata)


def test_split_omits_parent_rom_from_clone_archive() -> None:
    parent_rom = rom("common.bin", sha1="a" * 40)
    clone_rom = rom("clone.bin", sha1="b" * 40)
    games = [game("parent", roms=[parent_rom]), game("clone", parent="parent", roms=[clone_rom])]
    physical = [PhysicalRom("common.bin", 1, sha1="a" * 40), PhysicalRom("clone.bin", 1, sha1="b" * 40)]

    result = ArcadeRomReconstructionEngine().reconstruct(games, physical)
    manifest = ArcadeReconstructionManifestBuilder().build(
        games, set_name="test", set_type=ArcadeSetType.SPLIT, rom_result=result
    )

    assert manifest.is_ready
    assert manifest.rom_count == 2
    assert {entry.destination for entry in manifest.entries} == {
        "parent.zip!/common.bin",
        "clone.zip!/clone.bin",
    }


def test_non_merged_embeds_parent_rom_in_clone_archive() -> None:
    parent_rom = rom("common.bin", sha1="a" * 40)
    clone_rom = rom("common.bin", sha1="a" * 40)
    games = [game("parent", roms=[parent_rom]), game("clone", parent="parent", roms=[clone_rom])]
    physical = [PhysicalRom("common.bin", 1, sha1="a" * 40)]

    result = ArcadeRomReconstructionEngine().reconstruct(games, physical)
    manifest = ArcadeReconstructionManifestBuilder().build(
        games, set_name="test", set_type=ArcadeSetType.NON_MERGED, rom_result=result
    )

    assert manifest.is_ready
    assert manifest.rom_count == 2
    assert all(entry.kind is MaterializationKind.ROM for entry in manifest.entries)
    assert {entry.destination for entry in manifest.entries} == {
        "parent.zip!/common.bin",
        "clone.zip!/common.bin",
    }


def test_full_merged_deduplicates_shared_rom_destination() -> None:
    parent_rom = rom("common.bin", sha1="a" * 40)
    clone_rom = rom("common.bin", sha1="a" * 40)
    games = [game("parent", roms=[parent_rom]), game("clone", parent="parent", roms=[clone_rom])]
    physical = [PhysicalRom("common.bin", 1, sha1="a" * 40)]

    result = ArcadeRomReconstructionEngine().reconstruct(games, physical)
    manifest = ArcadeReconstructionManifestBuilder().build(
        games, set_name="test", set_type=ArcadeSetType.FULL_MERGED, rom_result=result
    )

    assert manifest.is_ready
    assert manifest.rom_count == 1
    assert manifest.entries[0].destination == "parent.zip!/common.bin"


def test_chd_is_placed_in_machine_directory() -> None:
    disk = ArcadeDisk(name="disc", sha1="c" * 40)
    games = [game("game", disks=(disk,))]
    chd_result = ArcadeChdReconstructionEngine().reconstruct(
        games, [PhysicalChd("source/disc.chd", logical_sha1="c" * 40)]
    )

    manifest = ArcadeReconstructionManifestBuilder().build(
        games,
        set_name="test",
        set_type=ArcadeSetType.SPLIT,
        rom_result=ReconstructionResult(()),
        chd_result=chd_result,
    )

    assert manifest.is_ready
    assert manifest.chd_count == 1
    assert manifest.entries[0].destination == "game/disc.chd"
