from pathlib import Path
import sqlite3

from serm_v2.services.mame_folder_filter_service import MameFolderFilterService


def _database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE mame_folder_filter_source (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                byte_length INTEGER NOT NULL DEFAULT 0,
                imported_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                UNIQUE(file_name, source_hash)
            );
            CREATE TABLE mame_folder_filter_entry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL REFERENCES mame_folder_filter_source(id) ON DELETE CASCADE,
                section TEXT,
                machine_name TEXT NOT NULL,
                raw_value TEXT NOT NULL,
                UNIQUE(source_id, section, machine_name)
            );
            """
        )


def test_ingests_all_ini_lines_except_folder_settings(tmp_path: Path) -> None:
    database = tmp_path / "serm.db"
    folders = tmp_path / "folders"
    folders.mkdir()
    _database(database)
    (folders / "genre.ini").write_text(
        """[FOLDER_SETTINGS]\nRootFolderIcon = folders\n\n[Fighting]\npacman = Pac-Man\n\n[Platform]\ndkong\n""",
        encoding="utf-8",
    )

    result = MameFolderFilterService.from_folders_path(database, folders).ingest()

    assert result["files"] == 1
    assert result["entries"] == 2
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT section, machine_name, raw_value FROM mame_folder_filter_entry ORDER BY id"
        ).fetchall()
    assert rows == [
        ("Fighting", "pacman", "pacman = Pac-Man"),
        ("Platform", "dkong", "dkong"),
    ]


def test_same_hash_different_files_are_both_preserved(tmp_path: Path) -> None:
    database = tmp_path / "serm.db"
    folders = tmp_path / "folders"
    folders.mkdir()
    _database(database)
    content = "[Arcade]\npacman\n"
    (folders / "Parents Arcade.ini").write_text(content, encoding="utf-8")
    (folders / "Working Arcade.ini").write_text(content, encoding="utf-8")

    result = MameFolderFilterService.from_folders_path(database, folders).ingest()

    assert result["files"] == 2
    with sqlite3.connect(database) as connection:
        names = connection.execute(
            "SELECT file_name FROM mame_folder_filter_source ORDER BY file_name"
        ).fetchall()
    assert names == [("Parents Arcade.ini",), ("Working Arcade.ini",)]


def test_changed_revision_replaces_previous_entries(tmp_path: Path) -> None:
    database = tmp_path / "serm.db"
    folders = tmp_path / "folders"
    folders.mkdir()
    _database(database)
    source = folders / "Working Arcade.ini"
    source.write_text("[Working]\npacman\n", encoding="utf-8")
    service = MameFolderFilterService.from_folders_path(database, folders)
    assert service.ingest()["files"] == 1

    source.write_text("[Working]\ngalaga\n", encoding="utf-8")
    assert service.ingest()["files"] == 1

    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT machine_name FROM mame_folder_filter_entry ORDER BY id"
        ).fetchall()
    assert rows == [("galaga",)]


def test_machine_names_can_be_limited_to_current_scan(tmp_path: Path) -> None:
    database = tmp_path / "serm.db"
    folders = tmp_path / "folders"
    folders.mkdir()
    _database(database)
    (folders / "Clones Arcade.ini").write_text(
        "[Clones]\npacman\ngalaga\n", encoding="utf-8"
    )
    MameFolderFilterService.from_folders_path(database, folders).ingest()

    names = MameFolderFilterService.machine_names_for_files(
        database,
        ("Clones Arcade.ini",),
        {"pacman"},
    )

    assert names == {"pacman"}
