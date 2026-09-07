from types import SimpleNamespace

from serm_v2.models.arcade import ArcadePlatform, PlayabilityStatus
from serm_v2.services.arcade.filter_engine import ArcadeFilterEngine
from serm_v2.services.arcade.mame_filter_v2_service import MameFilterV2Service


def _state(**overrides):
    values = dict(
        fundamental={key: False for key in ("mechanical", "dance", "console", "handheld", "fruit_machines", "quiz", "tabletop")},
        categories=[], subcategories=[], content=[], playability=[], genre=[], hardware=[], manufacturer=[], series=[], input=[], wheel=[],
        title_query="", full_text="", rom_query="", parent_query="", clone_query="", video_query="", audio_query="", screen_query="", orientation="all", cabinet_query="", channels_query="",
        year_from=None, year_to=None, type_filter="all",
        mame_include_bios=False, mame_include_devices=False, mame_include_optional=True, mame_include_chd=True,
        mame_working_only=False, mame_clone_policy="with_clones", mame_set_type="split", database_path=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_mame_snapshot_is_converted_without_legacy_constructor_arguments():
    payload = {"evidence": [{"status": "CURRENT", "machine_name": "pacman", "description": "Pac-Man", "categories": ["Arcade"], "playability": "fully_playable", "working": "yes", "isbios": "no", "isdevice": "no"}]}
    games = MameFilterV2Service._games(payload)
    assert len(games) == 1
    game = games[0]
    assert game.platform is ArcadePlatform.MAME
    assert game.playability is PlayabilityStatus.FULLY_PLAYABLE
    assert game.working is True
    assert game.is_bios is False
    assert game.is_device is False


def test_mame_snapshot_is_deduplicated_to_one_game_per_machine():
    payload = {"evidence": [{"status": "CURRENT", "machine_name": "pacman", "rom_name": "pacman.6e"}, {"status": "CURRENT", "machine_name": "pacman", "rom_name": "pacman.6f"}, {"status": "MISSING", "machine_name": "pacman", "rom_name": "pacman.6h"}, {"status": "CURRENT", "machine_name": "galaga", "rom_name": "gg1"}]}
    games = MameFilterV2Service._games(payload)
    assert [game.machine_name for game in games] == ["pacman", "galaga"]


def test_fundamental_flags_are_explicit_exclusions():
    rules = MameFilterV2Service._rules(_state())
    assert not rules.excluded_content_types
    assert not rules.excluded_genres


def test_filter_engine_accepts_playability_from_arcade_game_metadata():
    games = MameFilterV2Service._games({"evidence": [{"status": "CURRENT", "machine_name": "pacman", "description": "Pac-Man", "playability": "fully_playable"}]})
    state = _state(fundamental={key: True for key in MameFilterV2Service._CONTENT} | {"dance": True}, playability=["fully_playable"])
    result = ArcadeFilterEngine().apply(games, MameFilterV2Service._rules(state))
    assert result.included_count == 1
    assert result.games[0].game.playability is PlayabilityStatus.FULLY_PLAYABLE


def test_title_query_is_inclusive_and_machine_level():
    games = MameFilterV2Service._games({"evidence": [
        {"machine_name": "pacman", "description": "Pac-Man", "categories": ["Arcade"]},
        {"machine_name": "galaga", "description": "Galaga", "categories": ["Arcade"]},
    ]})
    state = _state(title_query="pacman")
    result = ArcadeFilterEngine().apply(games, MameFilterV2Service._rules(state, games))
    assert [item.game.machine_name for item in result.games] == ["pacman"]


def test_empty_advanced_query_does_not_accidentally_filter_everything():
    games = MameFilterV2Service._games({"evidence": [{"machine_name": "pacman", "description": "Pac-Man", "categories": ["Arcade"]}]})
    result = ArcadeFilterEngine().apply(games, MameFilterV2Service._rules(_state(), games))
    assert result.included_count == 1


def test_non_matching_advanced_query_produces_zero_machines():
    games = MameFilterV2Service._games({"evidence": [{"machine_name": "pacman", "description": "Pac-Man", "categories": ["Arcade"]}]})
    state = _state(title_query="this-machine-does-not-exist")
    result = ArcadeFilterEngine().apply(games, MameFilterV2Service._rules(state, games))
    assert result.included_count == 0
