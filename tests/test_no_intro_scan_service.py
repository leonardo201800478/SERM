import hashlib
import zipfile
import zlib
from types import SimpleNamespace

from serm_v2.services import no_intro_scan_service
from serm_v2.services.no_intro_scan_service import NoIntroScanService


def test_redump_dat_scan_uses_shared_hash_audit_and_source_label(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    bios_data = b"verified bios data"
    archive_path = source / "[BIOS] System.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("bios/system.rom", bios_data)

    dat_path = tmp_path / "system.dat"
    dat_path.write_text(
        f"""<?xml version="1.0"?>
<datafile>
  <header><name>Test System</name></header>
  <game name="[BIOS] System">
    <rom name="bios/system.rom" size="{len(bios_data)}" crc="{zlib.crc32(bios_data):08x}" sha1="{hashlib.sha1(bios_data).hexdigest()}" />
  </game>
</datafile>
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(no_intro_scan_service, "scans_root", lambda: tmp_path / "scans")
    profile = SimpleNamespace(
        profile_id="redump-test",
        source="Redump",
        system="Test System",
        dat_path=str(dat_path),
        source_directories=[str(source)],
    )

    result = NoIntroScanService().scan(profile)

    assert result.source == "Redump"
    assert result.status_counts["CURRENT"] == 1
    assert result.evidence[0].categories == ("clone:no", "type:bios", "extension:rom")
