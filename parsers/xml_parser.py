import xml.etree.ElementTree as ET
import sqlite3
import time
from core.models import Machine
from core.database import Database

class XMLParser:
    def __init__(self, xml_path, db_path):
        self.xml_path = xml_path
        self.db = Database(db_path)
        self.conn = self.db.conn
        self.cursor = self.conn.cursor()
        self.batch_size = 1000

    def _parse_boolean(self, value, default=0):
        if isinstance(value, str):
            value = value.lower()
            if value in ('yes', 'true', '1'):
                return 1
            if value in ('no', 'false', '0'):
                return 0
        return default

    def _parse_machine(self, elem):
        name = elem.get('name', '')
        description_elem = elem.find('description')
        description = description_elem.text if description_elem is not None else ''
        cloneof = elem.get('cloneof', '')
        romof = elem.get('romof', '')
        manufacturer_elem = elem.find('manufacturer')
        manufacturer = manufacturer_elem.text if manufacturer_elem is not None else ''
        year_elem = elem.find('year')
        year = year_elem.text if year_elem is not None else ''
        sourcefile = elem.get('sourcefile', '')

        runnable = self._parse_boolean(elem.get('runnable', '0'))
        isbios = self._parse_boolean(elem.get('isbios', '0'))
        isdevice = self._parse_boolean(elem.get('isdevice', '0'))
        ismechanical = self._parse_boolean(elem.get('ismechanical', '0'))

        machine = Machine(
            name=name,
            description=description,
            cloneof=cloneof,
            romof=romof,
            manufacturer=manufacturer,
            year=year,
            sourcefile=sourcefile,
            runnable=runnable,
            isbios=isbios,
            isdevice=isdevice,
            ismechanical=ismechanical,
            working=0,
            players=0
        )
        return machine

    def _insert_batch(self, machines):
        if not machines:
            return
        sql = """
            INSERT OR REPLACE INTO machine (
                name, description, cloneof, romof, manufacturer, year,
                sourcefile, runnable, isbios, isdevice, ismechanical,
                working, players, category, genre, genre_ows,
                machine_category, machine_type, resolution, version,
                working_arcade
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        values = []
        for m in machines:
            values.append((
                m.name, m.description, m.cloneof, m.romof, m.manufacturer, m.year,
                m.sourcefile, m.runnable, m.isbios, m.isdevice, m.ismechanical,
                m.working, m.players, m.category, m.genre, m.genre_ows,
                m.machine_category, m.machine_type, m.resolution, m.version,
                m.working_arcade
            ))
        self.cursor.executemany(sql, values)
        self.conn.commit()

    def parse(self):
        print(f"Lendo {self.xml_path}...")
        start_time = time.time()
        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        machines = []
        total = 0
        for elem in root.findall('machine'):
            machine = self._parse_machine(elem)
            machines.append(machine)
            total += 1
            if len(machines) >= self.batch_size:
                self._insert_batch(machines)
                machines.clear()
                if total % 10000 == 0:
                    elapsed = time.time() - start_time
                    rate = total / elapsed if elapsed > 0 else 0
                    print(f"  {total} máquinas [{elapsed:.1f}s, {rate:.0f} máquinas/s]")
        if machines:
            self._insert_batch(machines)
        elapsed = time.time() - start_time
        print(f"Total importado: {total:,} em {elapsed:.1f}s")
        return total

    def get_version(self):
        try:
            tree = ET.parse(self.xml_path)
            root = tree.getroot()
            mame_elem = root.find('mame')
            if mame_elem is not None:
                return mame_elem.get('version') or mame_elem.get('build')
        except Exception:
            pass
        return None

    def close(self):
        self.conn.close()