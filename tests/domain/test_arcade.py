"""Testes unitários do domínio Arcade, independentes de SQLite e MAME."""

from __future__ import annotations

from serm_v2.domain.arcade import (
    ArcadeDisplay,
    ArcadeGame,
    ArcadeRom,
    ArcadeSet,
    MachineKind,
    RomStatus,
)


def test_arcade_game_clone_and_playability() -> None:
    """Valida identidade parent/clone e regra básica de jogabilidade."""
    parent = ArcadeGame(name="pacman", description="Pac-Man")
    clone = ArcadeGame(name="puckman", cloneof="pacman")
    device = ArcadeGame(name="cpu", machine_kind=MachineKind.DEVICE)

    assert parent.is_parent
    assert not parent.is_clone
    assert clone.is_clone
    assert not clone.is_parent
    assert parent.playable
    assert not device.playable


def test_arcade_set_counts_roms_and_membership() -> None:
    """Valida agregação de jogos, ROMs e consulta de pertencimento."""
    roms = (
        ArcadeRom(name="pacman.6e", size=4096, crc="c1", status=RomStatus.OK),
        ArcadeRom(name="pacman.6f", size=4096, crc="c2", status=RomStatus.FIXABLE),
    )
    game = ArcadeGame(
        name="pacman",
        roms=roms,
        displays=(ArcadeDisplay(tag="screen", display_type="raster", width=288, height=224, refresh_hz=60.606),),
    )
    arcade_set = ArcadeSet(name="test", games=(game,))

    assert arcade_set.game_count == 1
    assert arcade_set.rom_count == 2
    assert arcade_set.contains("pacman")
    assert not arcade_set.contains("galaga")
