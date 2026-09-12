"""Persistência SQLite do inventário e dos perfis de entrada.

A camada é intencionalmente pequena e usa apenas a conexão DB já fornecida
pelo aplicativo. Nenhum estado do controlador é mantido em arquivos paralelos.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ..models.input_control import ControlProfile, InputDevice, InputElement, InputElementType, LogicalControl


class InputControlRepository:
    """CRUD idempotente para input_device/input_element/control_profile/binding."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def upsert_device(self, device: InputDevice) -> int:
        now = datetime.now(timezone.utc).isoformat()
        metadata = json.dumps(device.metadata, ensure_ascii=False, default=str)
        self.connection.execute(
            """INSERT INTO input_device
            (device_key,name,device_type,connection,vendor_id,product_id,version,serial,
             manufacturer,product,usage_page,usage,path,interface_number,bus_type,sdl_guid,
             sdl_mapping,backend,first_seen_at,last_seen_at,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(device_key) DO UPDATE SET
              name=excluded.name,device_type=excluded.device_type,connection=excluded.connection,
              vendor_id=excluded.vendor_id,product_id=excluded.product_id,version=excluded.version,
              serial=excluded.serial,manufacturer=excluded.manufacturer,product=excluded.product,
              usage_page=excluded.usage_page,usage=excluded.usage,path=excluded.path,
              interface_number=excluded.interface_number,bus_type=excluded.bus_type,sdl_guid=excluded.sdl_guid,
              sdl_mapping=excluded.sdl_mapping,backend=excluded.backend,last_seen_at=excluded.last_seen_at,
              metadata_json=excluded.metadata_json""",
            (device.hardware_key, device.name, device.device_type.value, device.connection.value,
             device.vendor_id, device.product_id, device.version, device.serial, device.manufacturer,
             device.product, device.usage_page, device.usage, device.path, device.interface_number,
             device.bus_type, device.sdl_guid, device.sdl_mapping, device.backend, now, now, metadata),
        )
        row = self.connection.execute("SELECT id FROM input_device WHERE device_key=?", (device.hardware_key,)).fetchone()
        if row is None:
            raise RuntimeError("Falha ao persistir dispositivo de entrada")
        return int(row[0])

    def replace_elements(self, device: InputDevice) -> int:
        device_row = self.connection.execute("SELECT id FROM input_device WHERE device_key=?", (device.hardware_key,)).fetchone()
        if device_row is None:
            device_id = self.upsert_device(device)
        else:
            device_id = int(device_row[0])
        self.connection.execute("DELETE FROM input_element WHERE device_id=?", (device_id,))
        for element in device.elements:
            self.connection.execute(
                """INSERT INTO input_element
                (device_id,element_key,element_type,name,element_index,logical_control,minimum,maximum,metadata_json)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (device_id, element.element_id, element.element_type.value, element.name, element.index,
                 element.logical_control.value if element.logical_control else None, element.minimum,
                 element.maximum, "{}"),
            )
        return device_id

    def save_profile(self, profile: ControlProfile, target_system: str | None = None, target_emulator: str | None = None) -> int:
        device_row = self.connection.execute("SELECT id FROM input_device WHERE device_key=?", (profile.device_id,)).fetchone()
        if device_row is None:
            raise ValueError("O dispositivo do perfil ainda não foi persistido")
        device_id = int(device_row[0])
        now = datetime.now(timezone.utc).isoformat()
        metadata = json.dumps(profile.metadata, ensure_ascii=False, default=str)
        self.connection.execute(
            """INSERT INTO control_profile
            (profile_key,name,device_id,target_system,target_emulator,version,created_at,updated_at,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(profile_key) DO UPDATE SET
              name=excluded.name,device_id=excluded.device_id,target_system=excluded.target_system,
              target_emulator=excluded.target_emulator,version=excluded.version,updated_at=excluded.updated_at,
              metadata_json=excluded.metadata_json""",
            (profile.profile_id, profile.name, device_id, target_system, target_emulator, 1, now, now, metadata),
        )
        row = self.connection.execute("SELECT id FROM control_profile WHERE profile_key=?", (profile.profile_id,)).fetchone()
        if row is None:
            raise RuntimeError("Falha ao persistir perfil de controle")
        profile_id = int(row[0])
        self.connection.execute("DELETE FROM control_binding WHERE profile_id=?", (profile_id,))
        for logical, elements in profile.bindings.items():
            for priority, element_id in enumerate(elements):
                self.connection.execute(
                    "INSERT INTO control_binding(profile_id,logical_control,physical_element,priority) VALUES (?,?,?,?)",
                    (profile_id, logical.value, element_id, priority),
                )
        return profile_id

    def commit(self) -> None:
        self.connection.commit()


__all__ = ["InputControlRepository"]
