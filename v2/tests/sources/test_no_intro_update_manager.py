from pathlib import Path

from serm_v2.sources.no_intro.catalog import NoIntroSystem
from serm_v2.sources.no_intro.downloader import NoIntroDownload
from serm_v2.sources.no_intro.update_manager import NoIntroUpdateManager


def test_missing_and_current_status(tmp_path: Path) -> None:
    manager = NoIntroUpdateManager(tmp_path)
    system = NoIntroSystem("Nintendo - NES", "2026-08-29 12:00:00")
    destination = tmp_path / "nes.zip"

    assert manager.inspect(system, destination).state == "missing"

    destination.write_bytes(b"dat")
    manager.record(
        system,
        NoIntroDownload(system.name, destination, "abc", "https://example.invalid/dat"),
    )
    status = manager.inspect(system, destination)
    assert status.state == "current"
    assert not status.needs_update


def test_older_revision_is_update_candidate(tmp_path: Path) -> None:
    manager = NoIntroUpdateManager(tmp_path)
    system = NoIntroSystem("Nintendo - NES", "2026-08-29 13:00:00")
    destination = tmp_path / "nes.zip"
    destination.write_bytes(b"old")
    manager.record(
        NoIntroSystem(system.name, "2026-08-29 12:00:00"),
        NoIntroDownload(system.name, destination, "old", ""),
    )

    status = manager.inspect(system, destination)
    assert status.state == "outdated"
    assert status.needs_update
    assert manager.update_candidates((system,), lambda _: destination) == (system,)


def test_unknown_existing_file_is_not_marked_outdated(tmp_path: Path) -> None:
    manager = NoIntroUpdateManager(tmp_path)
    system = NoIntroSystem("Nintendo - NES", "2026-08-29 13:00:00")
    destination = tmp_path / "nes.zip"
    destination.write_bytes(b"legacy")

    status = manager.inspect(system, destination)
    assert status.state == "unknown"
    assert not status.needs_update
    assert manager.update_candidates((system,), lambda _: destination) == ()
