import xml.etree.ElementTree as ET
from app.core.models.machine import Machine
from app.core.models.rom import Rom
from typing import List

class ListXmlParser:
    @staticmethod
    def parse(xml_string: str) -> List[Machine]:
        root = ET.fromstring(xml_string)
        machines = []
        for machine_elem in root.findall('machine'):
            machine = Machine()
            machine.name = machine_elem.get('name', '')
            machine.sourcefile = machine_elem.get('sourcefile', '')
            machine.is_device = machine_elem.get('isdevice', 'no') == 'yes'
            machine.is_mechanical = machine_elem.get('ismechanical', 'no') == 'yes'
            machine.runnable = machine_elem.get('runnable', 'yes') == 'yes'

            desc_elem = machine_elem.find('description')
            if desc_elem is not None:
                machine.description = desc_elem.text or ''
            year_elem = machine_elem.find('year')
            if year_elem is not None:
                machine.year = year_elem.text or ''
            manuf_elem = machine_elem.find('manufacturer')
            if manuf_elem is not None:
                machine.manufacturer = manuf_elem.text or ''

            machine.cloneof = machine_elem.get('cloneof', '')
            machine.romof = machine_elem.get('romof', '')
            machine.sampleof = machine_elem.get('sampleof', '')

            # Extrai ROMs
            roms = []
            for rom_elem in machine_elem.findall('rom'):
                rom = Rom()
                rom.name = rom_elem.get('name', '')
                rom.size = int(rom_elem.get('size', '0'))
                rom.crc = rom_elem.get('crc', '')
                rom.sha1 = rom_elem.get('sha1', '')
                rom.merge = rom_elem.get('merge', '')
                rom.region = rom_elem.get('region', '')
                rom.offset = int(rom_elem.get('offset', '0'))
                rom.status = rom_elem.get('status', 'good')
                rom.optional = rom_elem.get('optional', 'no') == 'yes'
                rom.bios = rom_elem.get('bios', '')
                roms.append(rom)
            machine.roms = roms
            machines.append(machine)
        return machines