from serm_v2.models.arcade import ArcadeGame, ArcadePlatform, ArcadeRom
from serm_v2.services.arcade.rom_reconstruction import (
    ArcadeRomReconstructionEngine,
    PhysicalRom,
    RomMatchKind,
)


def rom(name: str, **metadata: object) -> ArcadeRom:
    return ArcadeRom(
        machine_name=name,
        display_name=name,
        platform=ArcadePlatform.MAME,
        metadata=metadata,
    )


def game(name: str, *roms: ArcadeRom) -> ArcadeGame:
    return ArcadeGame(
        machine_name=name,
        display_name=name,
        platform=ArcadePlatform.MAME,
        roms=tuple(roms),
    )


def test_sha1_is_preferred() -> None:
    result = ArcadeRomReconstructionEngine().reconstruct(
        [game("game", rom("main", sha1="ABC123", crc="deadbeef", size=4))],
        [PhysicalRom("wrong.bin", 4, crc="deadbeef"), PhysicalRom("right.bin", 4, sha1="ABC123")],
    )

    assert result.items[0].kind is RomMatchKind.SHA1
    assert result.items[0].match is not None
    assert result.items[0].match.path == "right.bin"
    assert result.is_complete


def test_md5_is_used_when_sha1_is_unavailable() -> None:
    result = ArcadeRomReconstructionEngine().reconstruct(
        [game("game", rom("main", md5="ABC123"))],
        [PhysicalRom("main.bin", 8, md5="abc123")],
    )

    assert result.items[0].kind is RomMatchKind.MD5


def test_crc_and_size_are_fallback_identity() -> None:
    result = ArcadeRomReconstructionEngine().reconstruct(
        [game("game", rom("main", crc="ABCDEF12", size=16))],
        [PhysicalRom("main.bin", 16, crc="abcdef12")],
    )

    assert result.items[0].kind is RomMatchKind.CRC_SIZE


def test_duplicate_identity_is_ambiguous() -> None:
    result = ArcadeRomReconstructionEngine().reconstruct(
        [game("game", rom("main", sha1="ABC123"))],
        [PhysicalRom("a.bin", 1, sha1="abc123"), PhysicalRom("b.bin", 1, sha1="ABC123")],
    )

    assert result.items[0].kind is RomMatchKind.AMBIGUOUS
    assert not result.is_complete
    assert result.ambiguous_count == 1


def test_missing_rom_is_reported() -> None:
    result = ArcadeRomReconstructionEngine().reconstruct(
        [game("game", rom("main", sha1="ABC123"))],
        [],
    )

    assert result.items[0].kind is RomMatchKind.MISSING
    assert result.missing_count == 1
    assert not result.is_complete
