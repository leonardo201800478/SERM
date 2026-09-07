from serm_v2.models.arcade import ArcadeGame, ArcadePlatform
from serm_v2.models.arcade_classification import (
    ArcadeContentType,
    ArcadeGenre,
    ArcadeHardwareFamily,
    ArcadeInputType,
    WheelAngleClass,
)
from serm_v2.services.arcade.classification_service import ArcadeClassificationService


def make_game(*, categories: list[str], metadata: dict | None = None) -> ArcadeGame:
    return ArcadeGame(
        machine_name="test",
        display_name="Test Game",
        platform=ArcadePlatform.MAME,
        category=categories[0] if categories else None,
        subcategory=categories[1] if len(categories) > 1 else None,
        metadata={"categories": categories, **(metadata or {})},
    )


def test_content_type_is_the_first_filter_layer() -> None:
    game = make_game(categories=["Fruit Machines", "Action"])

    result = ArcadeClassificationService().classify(game)

    assert result.content_type is ArcadeContentType.FRUIT_MACHINE
    assert ArcadeGenre.ACTION in result.genres


def test_mechanical_flag_is_used_when_category_is_missing() -> None:
    game = make_game(categories=[], metadata={"ismechanical": True})

    result = ArcadeClassificationService().classify(game)

    assert result.content_type is ArcadeContentType.MECHANICAL


def test_hardware_and_genre_are_independent_facets() -> None:
    game = make_game(categories=["Fighting", "CPS2", "Neo Geo"])

    result = ArcadeClassificationService().classify(game)

    assert result.genres == (ArcadeGenre.FIGHTING,)
    assert ArcadeHardwareFamily.CPS2 in result.hardware
    assert ArcadeHardwareFamily.NEO_GEO in result.hardware
    assert ArcadeHardwareFamily.MAME in result.hardware


def test_input_requirements_are_read_from_metadata() -> None:
    game = make_game(
        categories=["Racing"],
        metadata={"inputs": ["Steering Wheel", "Pedals", "Analog"]},
    )

    result = ArcadeClassificationService().classify(game)

    assert ArcadeInputType.STEERING_WHEEL in result.inputs
    assert ArcadeInputType.PEDALS in result.inputs
    assert ArcadeInputType.ANALOG in result.inputs
    assert result.wheel_angle is WheelAngleClass.UNKNOWN


def test_mame_control_schema_is_understood() -> None:
    game = make_game(
        categories=["Racing"],
        metadata={
            "controls": [
                {"type": "paddle", "player": 1, "buttons": 4},
                {"type": "pedal", "player": 1, "buttons": 4},
            ],
        },
    )

    result = ArcadeClassificationService().classify(game)

    assert ArcadeInputType.STEERING_WHEEL in result.inputs
    assert ArcadeInputType.PEDALS in result.inputs
    assert ArcadeInputType.BUTTONS_4 in result.inputs


def test_button_count_uses_maximum_controller_button_count() -> None:
    game = make_game(
        categories=["Fighting"],
        metadata={"controls": [{"type": "stick", "buttons": 2}, {"type": "stick", "buttons": 6}]},
    )

    result = ArcadeClassificationService().classify(game)

    assert ArcadeInputType.BUTTONS_6 in result.inputs
    assert result.evidence["button_count"] == 6


def test_dance_genre_does_not_imply_dance_pad() -> None:
    game = make_game(categories=["Dance"])

    result = ArcadeClassificationService().classify(game)

    assert ArcadeGenre.DANCE in result.genres
    assert ArcadeInputType.DANCE_PAD not in result.inputs


def test_explicit_dance_pad_is_detected() -> None:
    game = make_game(categories=["Dance"], metadata={"inputs": ["Dance Pad"]})

    result = ArcadeClassificationService().classify(game)

    assert ArcadeInputType.DANCE_PAD in result.inputs


def test_explicit_wheel_angle_is_classified() -> None:
    game = make_game(
        categories=["Racing"],
        metadata={"inputs": ["Steering Wheel"], "wheel_angle": "900 degrees"},
    )

    result = ArcadeClassificationService().classify(game)

    assert ArcadeInputType.STEERING_WHEEL in result.inputs
    assert result.wheel_angle is WheelAngleClass.DEG_900


def test_unsupported_wheel_angle_remains_unknown() -> None:
    game = make_game(categories=["Racing"], metadata={"wheel_angle": 330})

    result = ArcadeClassificationService().classify(game)

    assert result.wheel_angle is WheelAngleClass.UNKNOWN


def test_unknown_metadata_is_not_guessed() -> None:
    game = make_game(categories=["Something Unknown"])

    result = ArcadeClassificationService().classify(game)

    assert result.content_type is ArcadeContentType.UNKNOWN
    assert result.genres == ()
    assert result.hardware == (ArcadeHardwareFamily.MAME,)
    assert result.inputs == ()
