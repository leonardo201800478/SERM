from types import SimpleNamespace

from serm_v2.models.arcade import ArcadePlatform, PlayabilityStatus
from serm_v2.services.arcade.filter_engine import ArcadeFilterEngine
from serm_v2.services.arcade.mame_filter_v2_service import MameFilterV2Service


def test_mame_snapshot_is_converted_without_legacy_constructor_arguments():
    payload = {
        "evidence": [
            {
                "status": "CURRENT",
                "machine_name": "pacman",
                "description": "Pac-Man",
                "categories": ["Arcade"],
                "playability": "fully_playable",
                "working": "yes",
                "isbios": "no",
                "isdevice": "no",
            }
        ]
    }
    games = MameFilterV2Service._games(payload)
    assert len(games) == 1
    game = games[0]
    assert game.platform is ArcadePlatform.MAME
    assert game.playability is PlayabilityStatus.FULLY_PLAYABLE
    assert game.working is True
    assert game.is_bios is False
    assert game.is_device is False


def test_filter_engine_accepts_playability_from_arcade_game_metadata():
    games = MameFilterV2Service._games({"evidence": [{
        "status": "CURRENT",
        "machine_name": "pacman",
        "description": "Pac-Man",
        "playability": "fully_playable",
    }]})
    state = SimpleNamespace(
        fundamental={key: True for key in MameFilterV2Service._CONTENT} | {"dance": True},
        categories=[], subcategories=[], content=[], playability=["fully_playable"], genre=[],
        hardware=[], manufacturer=[], series=[], input=[], wheel=[],
        mame_include_bios=False, mame_include_devices=False, mame_include_optional=True,
        mame_working_only=False, mame_clone_policy="with_clones", mame_set_type="split",
        database_path=None,
    )
    result = ArcadeFilterEngine().apply(games, MameFilterV2Service._rules(state))
    assert result.included_count == 1
    assert result.games[0].game.playability is PlayabilityStatus.FULLY_PLAYABLE
