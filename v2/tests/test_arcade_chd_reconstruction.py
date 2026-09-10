from serm_v2.models.arcade import ArcadeDisk, ArcadeGame, ArcadePlatform
from serm_v2.services.arcade.chd_reconstruction import (
    ArcadeChdReconstructionEngine,
    ChdMatchKind,
    PhysicalChd,
)


def game(name: str, *, parent: str | None = None, disks: tuple[ArcadeDisk, ...] = ()) -> ArcadeGame:
    return ArcadeGame(
        machine_name=name,
        display_name=name,
        platform=ArcadePlatform.MAME,
        parent_name=parent,
        disks=disks,
    )


def test_chd_matches_by_logical_sha1_not_file_sha1() -> None:
    catalog_disk = ArcadeDisk(name="disc", sha1="A" * 40)
    physical = PhysicalChd(
        path="/roms/game/disc.chd",
        logical_sha1="a" * 40,
        file_sha1="b" * 40,
    )

    result = ArcadeChdReconstructionEngine().reconstruct(
        [game("game", disks=(catalog_disk,))], [physical]
    )

    assert result.resolved_count == 1
    assert result.items[0].kind is ChdMatchKind.SHA1
    assert result.items[0].match == physical


def test_merged_chd_uses_parent_disk_identity() -> None:
    parent_disk = ArcadeDisk(name="disc", sha1="A" * 40)
    clone_disk = ArcadeDisk(name="disc_clone", sha1="C" * 40, merge="disc")
    games = [
        game("parent", disks=(parent_disk,)),
        game("clone", parent="parent", disks=(clone_disk,)),
    ]
    physical = [PhysicalChd(path="parent/disc.chd", logical_sha1="a" * 40)]

    result = ArcadeChdReconstructionEngine().reconstruct(games, physical)

    clone = next(item for item in result.items if item.machine_name == "clone")
    assert clone.kind is ChdMatchKind.SHA1
    assert clone.source_machine == "parent"
    assert clone.source_disk_name == "disc"
    assert clone.source_kind.value == "merged"
    assert clone.match == physical[0]


def test_explicit_merge_without_parent_is_invalid() -> None:
    disk = ArcadeDisk(name="disc", sha1="A" * 40, merge="parent_disc")

    result = ArcadeChdReconstructionEngine().reconstruct(
        [game("clone", disks=(disk,))], []
    )

    assert result.invalid_count == 1
    assert not result.is_complete
    assert result.items[0].kind is ChdMatchKind.INVALID


def test_duplicate_logical_chd_is_ambiguous() -> None:
    disk = ArcadeDisk(name="disc", md5="A" * 32)
    physical = [
        PhysicalChd(path="one/disc.chd", logical_md5="a" * 32),
        PhysicalChd(path="two/disc.chd", logical_md5="a" * 32),
    ]

    result = ArcadeChdReconstructionEngine().reconstruct(
        [game("game", disks=(disk,))], physical
    )

    assert result.ambiguous_count == 1
    assert result.items[0].kind is ChdMatchKind.AMBIGUOUS
    assert len(result.items[0].candidates) == 2


def test_missing_chd_is_reported() -> None:
    disk = ArcadeDisk(name="disc", sha1="A" * 40)

    result = ArcadeChdReconstructionEngine().reconstruct(
        [game("game", disks=(disk,))], []
    )

    assert result.missing_count == 1
    assert not result.is_complete
