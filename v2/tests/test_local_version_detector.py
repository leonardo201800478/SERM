from pathlib import Path

from serm_v2.services.arcade.local_version_detector import detect_local_version


def test_detects_mame_version_from_ini_header(tmp_path: Path) -> None:
    path = tmp_path / "MECHANICAL_ARCADE.ini"
    path.write_text(
        "[FOLDER_SETTINGS]\n"
        "RootFolderIcon mame\n"
        "SubFolderIcon folder\n\n"
        ";; MECHANICAL_ARCADE.ini 0.289 / 21-Aug-26 / MAME 0.289 ;;\n"
        ";; List of mechanical arcade machines ;;\n",
        encoding="utf-8",
    )
    assert detect_local_version(path) == "0.289"


def test_prefers_explicit_mame_version_in_dat_header(tmp_path: Path) -> None:
    path = tmp_path / "command.dat"
    path.write_text(";; command.dat 0.288 ;;\nMAME 0.289\n", encoding="utf-8")
    assert detect_local_version(path) == "0.289"


def test_detects_published_version_from_zip_name(tmp_path: Path) -> None:
    path = tmp_path / "pS_category_289.zip"
    path.write_bytes(b"zip placeholder")
    assert detect_local_version(path) == "0.289"


def test_detects_nplayers_version_from_zip_name(tmp_path: Path) -> None:
    path = tmp_path / "nplayers0278.zip"
    path.write_bytes(b"zip placeholder")
    assert detect_local_version(path) == "0.278"


def test_returns_none_when_no_version_is_available(tmp_path: Path) -> None:
    path = tmp_path / "unknown.ini"
    path.write_text("[FOLDER_SETTINGS]\nRootFolderIcon mame\n", encoding="utf-8")
    assert detect_local_version(path) is None
