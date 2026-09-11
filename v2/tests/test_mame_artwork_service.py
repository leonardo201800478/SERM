from pathlib import Path

from serm_v2.services.mame_artwork_service import MameArtworkService


def test_inventory_supports_standard_mame_artwork_directories(tmp_path: Path) -> None:
    root = tmp_path
    (root / "snap").mkdir()
    (root / "titles").mkdir()
    (root / "pcb").mkdir()
    (root / "icons").mkdir()
    (root / "snap" / "pacman.png").write_bytes(b"snap")
    (root / "titles" / "pacman.png").write_bytes(b"title")
    (root / "pcb" / "pacman.png").write_bytes(b"pcb")
    (root / "icons" / "pacman.png").write_bytes(b"icon")

    service = MameArtworkService([root])
    inventory = service.inventory("pacman")

    assert inventory["snap"] == root / "snap" / "pacman.png"
    assert inventory["title"] == root / "titles" / "pacman.png"
    assert inventory["pcb"] == root / "pcb" / "pacman.png"
    assert inventory["icon"] == root / "icons" / "pacman.png"
    assert service.primary("pacman") == root / "snap" / "pacman.png"


def test_primary_falls_back_to_title_then_flyer(tmp_path: Path) -> None:
    root = tmp_path
    (root / "titles").mkdir()
    (root / "flyers").mkdir()
    (root / "flyers" / "galaga.jpg").write_bytes(b"flyer")

    service = MameArtworkService([root])
    assert service.primary("galaga") == root / "flyers" / "galaga.jpg"

    (root / "titles" / "galaga.png").write_bytes(b"title")
    service.clear_cache()
    assert service.primary("galaga") == root / "titles" / "galaga.png"


def test_executable_root_auto_detection(tmp_path: Path) -> None:
    exe = tmp_path / "mame.exe"
    exe.write_bytes(b"MAME")
    (tmp_path / "snap").mkdir()
    (tmp_path / "snap" / "sf2.png").write_bytes(b"snap")

    service = MameArtworkService.from_mame_executable(exe)
    assert service.primary("sf2") == tmp_path / "snap" / "sf2.png"
