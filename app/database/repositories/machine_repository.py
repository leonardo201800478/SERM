from app.core.models.machine import Machine
from app.core.models.rom import Rom
from app.database.database import Database


class MachineRepository:
    def __init__(self, db: Database):
        self.db = db

    def insert_machine(self, machine: Machine):
        cursor = self.db.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO machine
            (name, description, year, manufacturer, sourcefile, cloneof, romof, sampleof,
             is_bios, is_device, is_mechanical, runnable, mame_installation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            machine.name, machine.description, machine.year, machine.manufacturer,
            machine.sourcefile, machine.cloneof, machine.romof, machine.sampleof,
            1 if machine.is_bios else 0,
            1 if machine.is_device else 0,
            1 if machine.is_mechanical else 0,
            1 if machine.runnable else 0,
            machine.mame_installation_id
        ))
        machine.id = cursor.lastrowid
        return machine.id

    def insert_rom(self, rom: Rom):
        cursor = self.db.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO rom
            (machine_id, name, size, crc, sha1, merge, region, offset, status, optional, bios)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            rom.machine_id, rom.name, rom.size, rom.crc, rom.sha1, rom.merge,
            rom.region, rom.offset, rom.status, 1 if rom.optional else 0, rom.bios
        ))
        rom.id = cursor.lastrowid
        return rom.id