from pathlib import Path

from serm_v2.sources.acquisition.datoso import DatosoProvider


def test_datoso_detects_new_matching_dat(monkeypatch, tmp_path: Path) -> None:
    source_root = tmp_path / "nointro" / "dats"
    source_root.mkdir(parents=True)
    source = source_root / "Nintendo - Nintendo Entertainment System (20260829).dat"

    provider = DatosoProvider(root=source_root)
    before: dict[Path, int] = {}
    source.write_bytes(b"PK\x03\x04test")
    source.touch()

    result = provider._find_new_or_updated(before, "Nintendo - Nintendo Entertainment System")

    assert result == source


def test_datoso_normalizes_names() -> None:
    assert DatosoProvider._normalize("Nintendo - Game Boy") == "nintendo game boy"
    assert DatosoProvider._normalize("Nintendo_Game_Boy") == "nintendo game boy"
