import hashlib
import xml.etree.ElementTree as ET
import logging
from app.core.models.machine import Machine
from app.core.models.rom import Rom
from app.core.models.disk import Disk

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self, conn):
        self.conn = conn

    def import_listxml(self, xml_string: str, executable_path: str, version: str):
        cursor = self.conn.cursor()
        logger.info("Iniciando importação do listxml...")

        # Registrar instalação
        cursor.execute("SELECT id FROM mame_installation WHERE executable_path = ?", (executable_path,))
        row = cursor.fetchone()
        if row:
            installation_id = row[0]
            cursor.execute("UPDATE mame_installation SET version = ?, detected_at = CURRENT_TIMESTAMP WHERE id = ?",
                           (version, installation_id))
            logger.info(f"Instalação existente atualizada (ID {installation_id})")
        else:
            with open(executable_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            cursor.execute("INSERT INTO mame_installation (version, executable_path, executable_hash) VALUES (?, ?, ?)",
                           (version, executable_path, file_hash))
            installation_id = cursor.lastrowid
            logger.info(f"Nova instalação criada (ID {installation_id})")
        self.conn.commit()

        # Parse do XML
        logger.info("Iniciando parse do XML...")
        machines = self._parse_listxml(xml_string)
        logger.info(f"Parse concluído: {len(machines)} máquinas encontradas.")

        # Inserir dados
        logger.info("Inserindo dados no banco...")
        total = len(machines)
        for idx, machine in enumerate(machines):
            if idx % 100 == 0:
                logger.info(f"Progresso: {idx}/{total} máquinas processadas.")

            cursor.execute("""
                INSERT OR REPLACE INTO machine
                (name, description, year, manufacturer, sourcefile, cloneof, romof, sampleof,
                 is_bios, is_device, is_mechanical, runnable, emulation_status, mame_installation_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                machine.name, machine.description, machine.year, machine.manufacturer,
                machine.sourcefile, machine.cloneof, machine.romof, machine.sampleof,
                1 if machine.is_bios else 0,
                1 if machine.is_device else 0,
                1 if machine.is_mechanical else 0,
                1 if machine.runnable else 0,
                machine.emulation_status,
                installation_id
            ))
            machine_id = cursor.lastrowid

            # Remover ROMs antigas
            cursor.execute("DELETE FROM rom WHERE machine_id = ?", (machine_id,))
            for rom in machine.roms:
                cursor.execute("""
                    INSERT INTO rom
                    (machine_id, name, size, crc, sha1, merge, region, offset, status, optional, bios)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    machine_id, rom.name, rom.size, rom.crc, rom.sha1, rom.merge,
                    rom.region, rom.offset, rom.status, 1 if rom.optional else 0, rom.bios
                ))

            # Remover disks antigos
            cursor.execute("DELETE FROM disk WHERE machine_id = ?", (machine_id,))
            for disk in machine.disks:
                cursor.execute("""
                    INSERT INTO disk
                    (machine_id, name, sha1, merge, region, idx, writable, status, optional)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    machine_id, disk.name, disk.sha1, disk.merge, disk.region,
                    disk.index, 1 if disk.writable else 0, disk.status, 1 if disk.optional else 0
                ))

        self.conn.commit()
        logger.info(f"Importação concluída. {total} máquinas inseridas/atualizadas.")

    def _parse_listxml(self, xml_string: str):
        try:
            root = ET.fromstring(xml_string)
        except ET.ParseError as e:
            logger.error(f"Erro ao parsear XML: {e}")
            raise

        machines = []
        for machine_elem in root.findall('machine'):
            machine = Machine()
            machine.name = machine_elem.get('name', '')
            machine.sourcefile = machine_elem.get('sourcefile', '')
            machine.is_bios = machine_elem.get('isbios', 'no') == 'yes'
            machine.is_device = machine_elem.get('isdevice', 'no') == 'yes'
            machine.is_mechanical = machine_elem.get('ismechanical', 'no') == 'yes'
            machine.runnable = machine_elem.get('runnable', 'yes') == 'yes'

            desc = machine_elem.find('description')
            if desc is not None:
                machine.description = desc.text or ''
            year = machine_elem.find('year')
            if year is not None:
                machine.year = year.text or ''
            manuf = machine_elem.find('manufacturer')
            if manuf is not None:
                machine.manufacturer = manuf.text or ''

            machine.cloneof = machine_elem.get('cloneof', '')
            machine.romof = machine_elem.get('romof', '')
            machine.sampleof = machine_elem.get('sampleof', '')

            driver = machine_elem.find('driver')
            if driver is not None:
                status = driver.get('status', '')
                if status == 'good':
                    machine.emulation_status = 'working'
                elif status == 'imperfect':
                    machine.emulation_status = 'imperfect'
                else:
                    machine.emulation_status = 'not_working'
            else:
                machine.emulation_status = 'unknown'

            # ROMs
            roms = []
            for rom_elem in machine_elem.findall('rom'):
                rom = Rom()
                rom.name = rom_elem.get('name', '')
                rom.size = int(rom_elem.get('size', '0'))
                rom.crc = rom_elem.get('crc', '')
                rom.sha1 = rom_elem.get('sha1', '')
                rom.merge = rom_elem.get('merge', '')
                rom.region = rom_elem.get('region', '')
                
                offset_str = rom_elem.get('offset', '0')
                try:
                    rom.offset = int(offset_str)  # tenta decimal
                except ValueError:
                    try:
                        rom.offset = int(offset_str, 16)  # tenta hexadecimal
                    except ValueError:
                        logger.warning(f"Offset inválido para ROM {rom.name}: '{offset_str}'. Usando 0.")
                        rom.offset = 0
                
                rom.status = rom_elem.get('status', 'good')
                rom.optional = rom_elem.get('optional', 'no') == 'yes'
                rom.bios = rom_elem.get('bios', '')
                roms.append(rom)
            machine.roms = roms

            # Disks (CHDs)
            disks = []
            for disk_elem in machine_elem.findall('disk'):
                disk = Disk()
                disk.name = disk_elem.get('name', '')
                disk.sha1 = disk_elem.get('sha1', '')
                disk.merge = disk_elem.get('merge', '')
                disk.region = disk_elem.get('region', '')
                try:
                    disk.index = int(disk_elem.get('index', '0'))
                except ValueError:
                    disk.index = 0
                disk.writable = disk_elem.get('writable', 'no') == 'yes'
                disk.status = disk_elem.get('status', 'good')
                disk.optional = disk_elem.get('optional', 'no') == 'yes'
                disks.append(disk)
            machine.disks = disks

            machines.append(machine)

        return machines