from pathlib import Path

from app.core.services.launchbox_integration_service import LaunchBoxIntegrationService
from app.core.services.retroarch_info_service import RetroArchInfoCore


def _info(corename: str, system_name: str, databases: tuple[str, ...]) -> RetroArchInfoCore:
    """Cria um .info mínimo para testar somente o mapeamento de plataformas."""
    return RetroArchInfoCore(
        info_path=Path(f"{corename}_libretro.info"),
        filename=f"{corename}_libretro.info",
        display_name=corename,
        corename=corename,
        display_version=None,
        authors=(),
        manufacturer=None,
        categories=("Emulator",),
        supported_extensions=(),
        system_name=system_name,
        system_id=corename,
        databases=databases,
        license=None,
        permissions=None,
        description=None,
        features={},
    )


def test_multi_database_core_maps_to_all_requested_platforms() -> None:
    """PUAE/Amiga-like metadata must populate Amiga, AGA, CD32 and CDTV."""
    info = _info(
        "puae",
        "Amiga",
        ("Commodore - Amiga", "Commodore - CD32", "Commodore - CDTV"),
    )
    names = LaunchBoxIntegrationService._matching_system_names(info)
    assert names == (
        "Commodore Amiga",
        "Commodore Amiga AGA",
        "Commodore Amiga CD32",
        "Commodore CDTV",
    )


def test_sega_32x_core_maps_to_32x_and_cd_32x() -> None:
    """PicoDrive-like metadata must populate both requested 32X platforms."""
    info = _info("picodrive", "Sega MS/MD/CD/32X", ("Sega - 32X",))
    names = LaunchBoxIntegrationService._matching_system_names(info)
    assert "Sega 32X" in names
    assert "Sega CD 32X" in names


def test_excluded_xbox_360_platform_is_not_canonical() -> None:
    """Xbox 360 remains outside the project catalog."""
    assert LaunchBoxIntegrationService._is_excluded_system("Microsoft Xbox 360")
