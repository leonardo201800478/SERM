from serm_v2.services.emulator_manager import CoreInfo
from serm_v2.services.retroarch_catalog_service import RetroArchCatalogService


def test_merge_prefers_stable_and_keeps_nightly_only_cores():
    stable = (
        CoreInfo("snes9x_libretro.dll.zip", "snes9x", channel="stable"),
        CoreInfo("mame2003_libretro.dll.zip", "mame2003", channel="stable"),
    )
    nightly = (
        CoreInfo("snes9x_libretro.dll.zip", "snes9x", channel="nightly"),
        CoreInfo("newcore_libretro.dll.zip", "newcore", channel="nightly"),
    )

    merged = RetroArchCatalogService._merge_sources(stable, nightly)

    assert [(item.core_name, item.channel) for item in merged] == [
        ("mame2003", "stable"),
        ("newcore", "nightly"),
        ("snes9x", "stable"),
    ]


def test_filter_snapshot_can_expose_or_remove_legacy_and_game_engine_cores():
    cores = (
        CoreInfo("snes9x_libretro.dll.zip", "snes9x"),
        CoreInfo("mame2003_libretro.dll.zip", "mame2003"),
        CoreInfo("scummvm_libretro.dll.zip", "scummvm"),
    )

    filtered = RetroArchCatalogService.filter_snapshot(
        cores,
        current_only=True,
        hide_games=True,
    )

    assert [item.core_name for item in filtered] == ["snes9x"]

    unfiltered = RetroArchCatalogService.filter_snapshot(
        cores,
        current_only=False,
        hide_games=False,
    )
    assert unfiltered == cores
