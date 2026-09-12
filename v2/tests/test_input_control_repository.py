import sqlite3

from serm_v2.models.input_control import ControlProfile, InputDevice, InputElement, InputElementType, LogicalControl
from serm_v2.services.input_control_repository import InputControlRepository


SCHEMA = """
CREATE TABLE input_device (
 id INTEGER PRIMARY KEY AUTOINCREMENT, device_key TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 device_type TEXT NOT NULL, connection TEXT NOT NULL, vendor_id INTEGER, product_id INTEGER, version INTEGER,
 serial TEXT, manufacturer TEXT, product TEXT, usage_page INTEGER, usage INTEGER, path TEXT,
 interface_number INTEGER, bus_type INTEGER, sdl_guid TEXT, sdl_mapping TEXT, backend TEXT NOT NULL,
 first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, metadata_json TEXT
);
CREATE TABLE input_element (
 id INTEGER PRIMARY KEY AUTOINCREMENT, device_id INTEGER NOT NULL, element_key TEXT NOT NULL,
 element_type TEXT NOT NULL, name TEXT NOT NULL, element_index INTEGER, logical_control TEXT,
 minimum INTEGER, maximum INTEGER, metadata_json TEXT, UNIQUE(device_id, element_key)
);
CREATE TABLE control_profile (
 id INTEGER PRIMARY KEY AUTOINCREMENT, profile_key TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 device_id INTEGER NOT NULL, target_system TEXT, target_emulator TEXT, version INTEGER NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, metadata_json TEXT
);
CREATE TABLE control_binding (
 id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL, logical_control TEXT NOT NULL,
 physical_element TEXT NOT NULL, direction TEXT, modifier TEXT, priority INTEGER NOT NULL,
 metadata_json TEXT, UNIQUE(profile_id, logical_control, physical_element, direction, modifier)
);
"""


def test_upsert_device_and_replace_elements():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    repo = InputControlRepository(db)
    device = InputDevice(
        device_id="hid:1234:5678:unit",
        name="8BitDo M30",
        vendor_id=0x1234,
        product_id=0x5678,
        serial="unit",
        elements=(
            InputElement("b1", InputElementType.BUTTON, "B1", logical_control=LogicalControl.FACE_SOUTH),
            InputElement("b2", InputElementType.BUTTON, "B2", logical_control=LogicalControl.FACE_EAST),
        ),
    )
    assert repo.replace_elements(device) > 0
    assert db.execute("SELECT count(*) FROM input_element").fetchone()[0] == 2
    repo.replace_elements(device)
    assert db.execute("SELECT count(*) FROM input_element").fetchone()[0] == 2


def test_save_profile_replaces_bindings_idempotently():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    repo = InputControlRepository(db)
    device = InputDevice("d1", "Pad", vendor_id=1, product_id=2)
    repo.upsert_device(device)
    profile = ControlProfile(
        "pad-default", "Pad padrão", device.hardware_key,
        {LogicalControl.FACE_SOUTH: ("b1",), LogicalControl.FACE_EAST: ("b2",)},
    )
    repo.save_profile(profile, "arcade", "mame")
    repo.save_profile(profile, "arcade", "mame")
    assert db.execute("SELECT count(*) FROM control_profile").fetchone()[0] == 1
    assert db.execute("SELECT count(*) FROM control_binding").fetchone()[0] == 2
