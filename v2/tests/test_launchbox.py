from pathlib import Path

from serm_v2.integrations.launchbox import LaunchBoxIntegration


def test_launchbox_accepts_executable_and_persists(tmp_path, monkeypatch):
    """Validate the V2 LaunchBox anchor without touching a real installation."""
    config = tmp_path / "launchbox.json"
    executable = tmp_path / "LaunchBox.exe"
    executable.write_bytes(b"test")
    monkeypatch.setattr(LaunchBoxIntegration, "CONFIG_PATH", config)

    integration = LaunchBoxIntegration()
    integration.set_executable(executable)

    assert integration.executable == Path(executable).resolve()
    assert integration.installed
    assert config.is_file()

    restored = LaunchBoxIntegration()
    assert restored.executable == Path(executable).resolve()
