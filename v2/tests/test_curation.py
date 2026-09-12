from serm_v2.domain.arcade import ArcadeGame
from serm_v2.domain.curation import CurationPolicy, curate_games


def game(name: str, parent: str | None = None, **metadata: object) -> ArcadeGame:
    return ArcadeGame(name=name, cloneof=parent, metadata=metadata)


def test_1g1r_prefers_region_then_language() -> None:
    games = [
        game("game-jp", "game", regions=["Japan"], languages=["Japanese"]),
        game("game-us", "game", regions=["USA"], languages=["English"]),
        game("game", regions=["Europe"], languages=["English"]),
    ]
    result = curate_games(
        games,
        CurationPolicy(
            one_game_one_rom=True,
            preferred_regions=("USA", "Europe", "Japan"),
            preferred_languages=("English", "Japanese"),
        ),
    )
    assert [item.name for item in result.selected] == ["game-us"]
    assert any(decision.rule == "1G1R" for decision in result.decisions)


def test_strict_controls_rejects_known_incompatible_machine() -> None:
    games = [game("wheel-game", controls=["270 wheel"])]
    result = curate_games(
        games,
        CurationPolicy(required_controls=("joystick",), strict_controls=True),
    )
    assert not result.selected
    assert result.decisions[0].rule == "controls"


def test_missing_controls_do_not_fail_permissive_mode() -> None:
    games = [game("unknown-controls")]
    result = curate_games(games, CurationPolicy(required_controls=("joystick",)))
    assert [item.name for item in result.selected] == ["unknown-controls"]


def test_max_players_and_buttons() -> None:
    games = [
        game("too-many-players", players=5, buttons=4),
        game("too-many-buttons", players=2, buttons=10),
        game("ok", players=2, buttons=6),
    ]
    result = curate_games(games, CurationPolicy(max_players=4, max_buttons=8))
    assert [item.name for item in result.selected] == ["ok"]
