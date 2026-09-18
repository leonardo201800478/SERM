from serm_v2.models.arcade import ArcadeGame, ArcadePlatform, ArcadeSetType
from serm_v2.services.arcade.set_layout import ArcadeSetLayoutPlanner, SetFileAction


def game(name: str, parent: str | None = None) -> ArcadeGame:
    return ArcadeGame(
        machine_name=name,
        display_name=name,
        platform=ArcadePlatform.MAME,
        parent_name=parent,
    )


def test_split_keeps_one_archive_per_machine() -> None:
    plan = ArcadeSetLayoutPlanner().plan([game("parent"), game("clone", "parent")], ArcadeSetType.SPLIT)

    assert [(entry.machine_name, entry.archive_name) for entry in plan.entries] == [
        ("parent", "parent"),
        ("clone", "clone"),
    ]
    assert all(entry.action is SetFileAction.KEEP for entry in plan.entries)


def test_non_merged_embeds_components_in_each_archive() -> None:
    plan = ArcadeSetLayoutPlanner().plan([game("parent"), game("clone", "parent")], ArcadeSetType.NON_MERGED)

    assert [entry.archive_name for entry in plan.entries] == ["parent", "clone"]
    assert all(entry.action is SetFileAction.EMBED for entry in plan.entries)


def test_full_merged_collapses_family_into_parent_root() -> None:
    games = [game("parent"), game("clone", "parent"), game("clone2", "clone")]

    plan = ArcadeSetLayoutPlanner().plan(games, ArcadeSetType.FULL_MERGED)

    assert [entry.archive_name for entry in plan.entries] == ["parent", "parent", "parent"]
    assert plan.entries[0].action is SetFileAction.KEEP
    assert all(entry.action is SetFileAction.SHARE for entry in plan.entries[1:])


def test_full_merged_detects_parent_cycle() -> None:
    try:
        ArcadeSetLayoutPlanner().plan([game("a", "b"), game("b", "a")], ArcadeSetType.FULL_MERGED)
    except ValueError as exc:
        assert "Ciclo" in str(exc)
    else:
        raise AssertionError("ValueError esperado")
