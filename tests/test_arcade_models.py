from serm_v2.models.arcade import (
    ArcadeGame,
    ArcadePlatform,
    ArcadeRom,
    ArcadeSet,
    ArcadeSetType,
    PlayabilityStatus,
    RomStatus,
)


def test_clone_is_derived_from_parent_name() -> None:
    rom = ArcadeRom(
        machine_name="sf2ce",
        display_name="Street Fighter II' Champion Edition",
        platform=ArcadePlatform.MAME,
        parent_name="sf2",
    )

    assert rom.is_clone


def test_game_status_uses_worst_component_status() -> None:
    game = ArcadeGame(
        machine_name="example",
        display_name="Example",
        platform=ArcadePlatform.MAME,
        roms=(
            ArcadeRom(
                machine_name="example",
                display_name="Example",
                platform=ArcadePlatform.MAME,
                rom_status=RomStatus.OK,
            ),
            ArcadeRom(
                machine_name="example",
                display_name="Example",
                platform=ArcadePlatform.MAME,
                rom_status=RomStatus.REPAIRABLE,
            ),
        ),
    )

    assert game.rom_status is RomStatus.REPAIRABLE


def test_arcade_set_tracks_games_and_configuration() -> None:
    game = ArcadeGame(
        machine_name="pacman",
        display_name="Pac-Man",
        platform=ArcadePlatform.MAME,
    )
    arcade_set = ArcadeSet(
        name="Arcade Collection",
        platform=ArcadePlatform.MAME,
        set_type=ArcadeSetType.NON_MERGED,
    )
    arcade_set.add_games([game])

    assert arcade_set.game_count == 1
    assert arcade_set.set_type is ArcadeSetType.NON_MERGED


def test_playability_is_independent_from_rom_status() -> None:
    rom = ArcadeRom(
        machine_name="vf3",
        display_name="Virtua Fighter 3",
        platform=ArcadePlatform.MAME,
        rom_status=RomStatus.OK,
        playability=PlayabilityStatus.IN_DEVELOPMENT,
    )

    assert rom.rom_status is RomStatus.OK
    assert rom.playability is PlayabilityStatus.IN_DEVELOPMENT
