from __future__ import annotations

from pathlib import Path

from app.core.services.emulator_config_service import (
    EmulatorConfigService,
    EmulatorConfigSpec,
    validate_xml,
)


def test_valid_file_is_never_regenerated(tmp_path: Path) -> None:
    path = tmp_path / "emu.cfg"
    path.write_text("[audio]\nbackend = auto\n", encoding="utf-8")

    called = False

    def generator() -> None:
        nonlocal called
        called = True

    spec = EmulatorConfigSpec(
        emulator="flycast",
        name="emu.cfg",
        path=path,
        validator=lambda p: p.read_text(encoding="utf-8").startswith("[audio]"),
    )

    result = EmulatorConfigService().ensure(spec)

    assert result.status == "valid"
    assert result.generated is False
    assert called is False
    assert path.read_text(encoding="utf-8") == "[audio]\nbackend = auto\n"


def test_corrupt_file_is_backed_up_before_generation(tmp_path: Path) -> None:
    path = tmp_path / "data.xml"
    path.write_text("<broken>", encoding="utf-8")

    generator = tmp_path / "generator.py"
    generator.write_text(
        "from pathlib import Path\n"
        "Path('data.xml').write_text('<root><game name=\"ok\"/></root>', encoding='utf-8')\n",
        encoding="utf-8",
    )

    import sys

    spec = EmulatorConfigSpec(
        emulator="test",
        name="data.xml",
        path=path,
        cwd=tmp_path,
        generator_command=(sys.executable, str(generator)),
        validator=validate_xml,
    )

    result = EmulatorConfigService().ensure(spec)

    assert result.generated is True
    assert result.status == "generated_corrupt"
    assert result.backup is not None
    assert result.backup.is_file()
    assert result.backup.read_text(encoding="utf-8") == "<broken>"
    assert validate_xml(path)


def test_missing_without_generator_is_not_synthesized(tmp_path: Path) -> None:
    path = tmp_path / "missing.cfg"

    spec = EmulatorConfigSpec(
        emulator="supermodel",
        name="Supermodel.ini",
        path=path,
    )

    result = EmulatorConfigService().ensure(spec)

    assert result.status == "missing_no_generator"
    assert result.generated is False
    assert not path.exists()
