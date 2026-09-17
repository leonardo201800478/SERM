from serm_v2.models.arcade import ArcadeGame, ArcadePlatform, ArcadeRom, ArcadeSetType
from serm_v2.services.arcade.reconstruction_manifest import ArcadeReconstructionManifestBuilder
from serm_v2.services.arcade.rom_reconstruction import ArcadeRomReconstructionEngine, PhysicalRom


def game(name: str, *roms: ArcadeRom) -> ArcadeGame:
    return ArcadeGame(
        machine_name=name,
        display_name=name,
        platform=ArcadePlatform.MAME,
        roms=tuple(roms),
    )


def rom(name: str, sha1: str) -> ArcadeRom:
    return ArcadeRom(
        machine_name="machine",
        display_name=name,
        platform=ArcadePlatform.MAME,
        metadata={"sha1": sha1, "size": 4096},
    )


def test_manifest_indexes_each_rom_by_display_name() -> None:
    games = [
        game(
            "machine",
            rom("maincpu.bin", "a" * 40),
            rom("soundcpu.bin", "b" * 40),
            rom("gfx.bin", "c" * 40),
        )
    ]
    physical = [
        PhysicalRom("maincpu.bin", 4096, sha1="a" * 40),
        PhysicalRom("soundcpu.bin", 4096, sha1="b" * 40),
        PhysicalRom("gfx.bin", 4096, sha1="c" * 40),
    ]

    result = ArcadeRomReconstructionEngine().reconstruct(games, physical)
    manifest = ArcadeReconstructionManifestBuilder().build(
        games,
        set_name="test",
        set_type=ArcadeSetType.NON_MERGED,
        rom_result=result,
    )

    assert manifest.is_ready
    assert manifest.rom_count == 3
    assert {entry.member_name for entry in manifest.entries} == {
        "maincpu.bin",
        "soundcpu.bin",
        "gfx.bin",
    }
