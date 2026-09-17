import sqlite3
from pathlib import Path

from serm_v2.database.bootstrap import apply_migrations
from serm_v2.services.mame_folder_filter_service import MameFolderFilterService


def test_folder_filter_migration_allows_identical_content_with_different_names(tmp_path: Path) -> None:
    database = tmp_path / "serm.db"
    apply_migrations(database)

    folders = tmp_path / "folders"
    folders.mkdir()
    content = "[Arcade]\npacman\n"
    (folders / "Parents Arcade.ini").write_text(content, encoding="utf-8")
    (folders / "Working Arcade.ini").write_text(content, encoding="utf-8")

    result = MameFolderFilterService.from_folders_path(database, folders).ingest()

    assert result["files"] == 2
    with sqlite3.connect(database) as connection:
        sources = connection.execute(
            "SELECT file_name, source_hash FROM mame_folder_filter_source ORDER BY file_name"
        ).fetchall()
    assert [row[0] for row in sources] == [
        "Parents Arcade.ini",
        "Working Arcade.ini",
    ]
    assert sources[0][1] == sources[1][1]


def test_migrations_record_018(tmp_path: Path) -> None:
    database = tmp_path / "serm.db"
    apply_migrations(database)

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version='018_mame_folder_filter_storage'"
        ).fetchone()

    assert row == (1,)
