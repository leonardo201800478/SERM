from serm_v2.sources.routing import SourceFamily, SystemSourceRouter


def test_optical_platforms_route_to_redump() -> None:
    router = SystemSourceRouter()

    assert router.route("Sony PlayStation") is SourceFamily.REDUMP
    assert router.route("Sega Saturn") is SourceFamily.REDUMP
    assert router.route("Nintendo Wii") is SourceFamily.REDUMP
    assert not router.allows_no_intro("Sony PlayStation")


def test_cartridge_platforms_route_to_no_intro() -> None:
    router = SystemSourceRouter()

    assert router.route("Nintendo Entertainment System") is SourceFamily.NO_INTRO
    assert router.route("Game Boy Advance") is SourceFamily.NO_INTRO
    assert router.allows_no_intro("Game Boy Advance")


def test_unknown_platform_is_not_guessed() -> None:
    assert SystemSourceRouter().route("Future Unknown System") is SourceFamily.UNSUPPORTED
