from serm_v2.models.arcade import ArcadeGame, ArcadePlatform, ArcadeSetType
from serm_v2.services.arcade.set_builder import (
    ArcadeSetBuilder,
    SetBuildDecision,
    SetBuildError,
)


def game(name: str, parent: str | None = None, **metadata: object) -> ArcadeGame:
    return ArcadeGame(
        machine_name=name,
        display_name=name,
        platform=ArcadePlatform.MAME,
        parent_name=parent,
        metadata=metadata,
    )


def test_split_set_adds_parent_as_dependency() -> None:
    games = [game("parent"), game("clone", "parent")]

    result = ArcadeSetBuilder().build(games, ["clone"], name="test", set_type=ArcadeSetType.SPLIT)

    assert [item.machine_name for item in result.arcade_set.games] == ["clone", "parent"]
    decisions = {trace.machine_name: trace.decision for trace in result.traces}
    assert decisions["clone"] is SetBuildDecision.SELECTED
    assert decisions["parent"] is SetBuildDecision.DEPENDENCY
    assert result.is_valid


def test_declared_dependencies_are_resolved() -> None:
    games = [game("game", dependencies=["bios", "device"]), game("bios"), game("device")]

    result = ArcadeSetBuilder().build(games, ["game"])

    assert {item.machine_name for item in result.arcade_set.games} == {"game", "bios", "device"}
    assert result.dependency_count == 2


def test_missing_dependency_is_reported_without_silent_drop() -> None:
    result = ArcadeSetBuilder().build([game("game", dependencies=["missing"])], ["game"])

    assert result.missing_dependencies == ("missing",)
    assert not result.is_valid
    assert any(trace.decision is SetBuildDecision.MISSING_DEPENDENCY for trace in result.traces)


def test_dependency_cycle_is_reported() -> None:
    games = [game("a", "b"), game("b", "a")]

    result = ArcadeSetBuilder().build(games, ["a"])

    assert result.cycles
    assert not result.is_valid


def test_unknown_selected_machine_is_rejected() -> None:
    try:
        ArcadeSetBuilder().build([game("known")], ["unknown"])
    except SetBuildError as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("SetBuildError esperado")


def test_generator_catalog_is_supported() -> None:
    games = (item for item in [game("parent"), game("clone", "parent")])

    result = ArcadeSetBuilder().build(games, ["clone"])

    assert {item.machine_name for item in result.arcade_set.games} == {"clone", "parent"}
