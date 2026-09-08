"""Smoke tests rapidos para a semantica de merge do MAME.

Estes testes sao deliberadamente pequenos: validam o contrato do planejador
sem abrir o banco real nem percorrer o catalogo completo. A auditoria do banco
continua existindo separadamente para validar os dados reais.
"""

from serm_v2.models.arcade import ArcadeGame, ArcadeRom
from serm_v2.services.arcade.rom_reconstruction_plan import (
    ArcadeRomReconstructionPlanner,
    RomSourceKind,
)


def _rom(machine: str, name: str, **metadata: object) -> ArcadeRom:
    return ArcadeRom(
        machine_name=machine,
        display_name=name,
        platform="mame",
        metadata=metadata,
    )


def _game(
    machine: str,
    *,
    parent: str | None = None,
    romof: str | None = None,
    roms: list[ArcadeRom],
) -> ArcadeGame:
    return ArcadeGame(
        machine_name=machine,
        display_name=machine,
        platform="mame",
        parent_name=parent,
        metadata={"romof": romof} if romof else {},
        roms=tuple(roms),
    )


def _plan(*games: ArcadeGame):
    return ArcadeRomReconstructionPlanner().plan(games).items


def test_merge_prefers_related_machine_over_unrelated_same_name():
    items = _plan(
        _game("parent", roms=[_rom("parent", "shared.bin")]),
        _game(
            "clone",
            parent="parent",
            roms=[_rom("clone", "local.bin", merge="shared.bin")],
        ),
        _game("unrelated", roms=[_rom("unrelated", "shared.bin")]),
    )

    assert items[1].source_kind is RomSourceKind.MERGED
    assert items[1].source_machine == "parent"


def test_merge_does_not_guess_unrelated_unique_name():
    items = _plan(
        _game("unrelated", roms=[_rom("unrelated", "shared.bin")]),
        _game("clone", roms=[_rom("clone", "local.bin", merge="shared.bin")]),
    )

    assert items[1].source_kind is RomSourceKind.MISSING
    assert items[1].source_machine is None


def test_self_merge_is_local():
    items = _plan(
        _game("set1", roms=[_rom("set1", "local.bin", merge="local.bin")]),
    )

    assert items[0].source_kind is RomSourceKind.SELF
    assert items[0].source_machine == "set1"


def test_romof_has_priority_when_same_rom_exists_there():
    items = _plan(
        _game("source", roms=[_rom("source", "shared.bin")]),
        _game(
            "clone",
            parent="other-parent",
            romof="source",
            roms=[_rom("clone", "shared.bin")],
        ),
        _game("other-parent", roms=[_rom("other-parent", "shared.bin")]),
    )

    assert items[1].source_kind is RomSourceKind.ROMOF
    assert items[1].source_machine == "source"


def test_parent_inheritance_requires_same_rom_name():
    items = _plan(
        _game("parent", roms=[_rom("parent", "parent.bin")]),
        _game(
            "clone",
            parent="parent",
            roms=[_rom("clone", "local.bin")],
        ),
    )

    assert items[1].source_kind is RomSourceKind.SELF
    assert items[1].source_machine == "clone"
