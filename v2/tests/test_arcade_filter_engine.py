from serm_v2.models.arcade import ArcadeGame, ArcadePlatform
from serm_v2.models.arcade_classification import (
    ArcadeContentType,
    ArcadeGenre,
    ArcadeHardwareFamily,
)
from serm_v2.services.arcade.filter_engine import (
    ArcadeFilterEngine,
    FilterDecision,
    FilterRules,
    FilterStage,
)


def game(name: str, categories: list[str], **metadata: object) -> ArcadeGame:
    return ArcadeGame(
        machine_name=name,
        display_name=name,
        platform=ArcadePlatform.MAME,
        category=categories[0] if categories else None,
        subcategory=categories[1] if len(categories) > 1 else None,
        metadata={"categories": categories, **metadata},
    )


def test_content_exclusion_happens_before_genre_refinement() -> None:
    games = [
        game("fruit", ["Fruit Machines", "Action"]),
        game("fighter", ["Fighter", "CPS2"]),
    ]
    rules = FilterRules(
        excluded_content_types=frozenset({ArcadeContentType.FRUIT_MACHINE}),
        included_genres=frozenset({ArcadeGenre.ACTION, ArcadeGenre.FIGHTING}),
    )

    result = ArcadeFilterEngine().apply(games, rules)

    assert [item.game.machine_name for item in result.games] == ["fighter"]
    assert result.counts_after_stage[FilterStage.CONTENT] == 1
    assert result.counts_after_stage[FilterStage.GENRE] == 1


def test_multiple_values_in_one_refinement_are_or() -> None:
    games = [
        game("cps1", ["Fighter", "CPS1"]),
        game("cps2", ["Fighter", "CPS2"]),
        game("racing", ["Racing", "Model 2"]),
    ]
    rules = FilterRules(
        included_genres=frozenset({ArcadeGenre.FIGHTING}),
        included_hardware=frozenset({ArcadeHardwareFamily.CPS1, ArcadeHardwareFamily.CPS2}),
    )

    result = ArcadeFilterEngine().apply(games, rules)

    assert [item.game.machine_name for item in result.games] == ["cps1", "cps2"]


def test_content_exclusion_keeps_trace_explainable() -> None:
    items = [game("quiz1", ["Quiz"])]
    rules = FilterRules(excluded_content_types=frozenset({ArcadeContentType.QUIZ}))

    result = ArcadeFilterEngine().apply(items, rules)
    classified = ArcadeFilterEngine()._classifier.classify(items[0])

    assert result.included_count == 0
    assert classified.content_type is ArcadeContentType.QUIZ


def test_empty_rules_preserve_catalog() -> None:
    games = [game("a", ["Fighter"]), game("b", ["Racing"])]

    result = ArcadeFilterEngine().apply(games)

    assert [item.game.machine_name for item in result.games] == ["a", "b"]
    assert result.total_input == 2
    assert all(item.trace.decision is FilterDecision.INCLUDED for item in result.games)
