from pathlib import Path
import subprocess

import pytest

from serm_v2.emulation.mame_dat_scraper import MameDatError, scrape_mame_dat


class FakeCompleted:
    returncode = 0
    stderr = ""
    stdout = "<mame><machine name=\"pacman\"/><machine name=\"galaga\"/></mame>"


def test_scrape_mame_dat_invokes_listxml(monkeypatch, tmp_path: Path):
    executable = tmp_path / "mame.exe"
    executable.write_text("stub", encoding="utf-8")
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = scrape_mame_dat(executable)

    assert result.machine_count == 2
    assert result.executable == executable.resolve()
    assert calls[0][0][0] == [str(executable.resolve()), "-listxml"]


def test_scrape_mame_dat_rejects_missing_executable(tmp_path: Path):
    with pytest.raises(MameDatError, match="not found"):
        scrape_mame_dat(tmp_path / "missing.exe")


def test_scrape_mame_dat_rejects_process_failure(monkeypatch, tmp_path: Path):
    executable = tmp_path / "mame.exe"
    executable.write_text("stub", encoding="utf-8")

    class Failed:
        returncode = 2
        stderr = "unknown option"
        stdout = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Failed())

    with pytest.raises(MameDatError, match="exit code 2"):
        scrape_mame_dat(executable)


def test_scrape_mame_dat_rejects_invalid_xml(monkeypatch, tmp_path: Path):
    executable = tmp_path / "mame.exe"
    executable.write_text("stub", encoding="utf-8")

    class Invalid:
        returncode = 0
        stderr = ""
        stdout = "<mame>"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Invalid())

    with pytest.raises(MameDatError, match="invalid XML"):
        scrape_mame_dat(executable)
