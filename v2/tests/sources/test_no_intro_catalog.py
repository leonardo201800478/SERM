from pathlib import Path

from serm_v2.sources.no_intro.catalog import NoIntroCatalog


def test_catalog_extracts_official_systems() -> None:
    source = """
    Nintendo - Nintendo Entertainment System (#8429 ~ 20260828-135635 ~ P/C: #8420)
    Source Code - Nintendo - Game Boy (#001 ~ 20230107-011201)
    Unofficial - Sony - PlayStation Vita (#624 ~ 20260823-084923)
    Sega - Mega Drive - Genesis (#3738 ~ 20260828-164800)
    """

    systems = NoIntroCatalog().systems(source)

    assert [item.name for item in systems] == [
        "Nintendo - Nintendo Entertainment System",
        "Sega - Mega Drive - Genesis",
    ]
    assert systems[0].update_text == "20260828-135635"


def test_catalog_snapshot_is_saved(tmp_path: Path) -> None:
    path = NoIntroCatalog().save_catalog("<html>test</html>", tmp_path / "catalog.html")

    assert path.read_text(encoding="utf-8") == "<html>test</html>"


def test_catalog_row_text_fallback_extracts_multiple_current_style_entries() -> None:
    source = """
    <table>
      <tr><td>Nintendo - Nintendo DS (#6800 + x220 + z690 ~ 2026-08-28 23:16:09 ~ P/C: #6800)</td></tr>
      <tr><td>Nintendo - Game Boy (#2470 ~ 2026-08-28 17:28:24 ~ P/C: #2437)</td></tr>
      <tr><td>Sega - Mega Drive - Genesis (#3738 ~ 2026-08-28 16:48:00 ~ P/C: #3737)</td></tr>
    </table>
    """

    systems = NoIntroCatalog().systems(source)

    assert [item.name for item in systems] == [
        "Nintendo - Nintendo DS",
        "Nintendo - Game Boy",
        "Sega - Mega Drive - Genesis",
    ]
    assert systems[0].update_text == "2026-08-28 23:16:09"
