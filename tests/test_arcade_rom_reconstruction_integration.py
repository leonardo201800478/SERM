from serm_v2.models.arcade import ArcadeGame, ArcadePlatform, ArcadeRom
from serm_v2.services.arcade.rom_reconstruction import ArcadeRomReconstructionEngine, PhysicalRom
from serm_v2.services.arcade.rom_reconstruction_plan import RomSourceKind


def test_merge_uses_parent_hashes_for_physical_lookup() -> None:
    parent_rom = ArcadeRom(
        machine_name="common.bin",
        display_name="common.bin",
        platform=ArcadePlatform.MAME,
        metadata={"sha1": "PARENT-SHA1", "size": 4},
    )
    parent = ArcadeGame("parent", "Parent", ArcadePlatform.MAME, roms=(parent_rom,))
    clone_rom = ArcadeRom(
        machine_name="clone.bin",
        display_name="clone.bin",
        platform=ArcadePlatform.MAME,
        metadata={"merge": "common.bin", "sha1": "CLONE-SHA1", "size": 4},
    )
    clone = ArcadeGame("clone", "Clone", ArcadePlatform.MAME, parent_name="parent", roms=(clone_rom,))

    result = ArcadeRomReconstructionEngine().reconstruct(
        [parent, clone],
        [PhysicalRom("common.bin", 4, sha1="PARENT-SHA1")],
    )

    item = result.items[1]
    assert item.source_kind is RomSourceKind.MERGED
    assert item.source_machine == "parent"
    assert item.match is not None
    assert item.match.path == "common.bin"
