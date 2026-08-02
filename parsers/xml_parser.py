import xml.etree.ElementTree as ET
from core.models import Machine
from core.database import Database
import sqlite3
import time

class XMLParser:
    def __init__(self, xml_file, db_path):
        self.xml_file = xml_file
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def parse(self):
        print("Lendo listxml.xml...")
        tree = ET.parse(self.xml_file)
        root = tree.getroot()
        total = 0
        batch = []
        start_time = time.time()
        for elem in root.iter('machine'):
            machine = self._parse_machine(elem)
            if machine:
                batch.append(machine)
                if len(batch) >= 1000:
                    self._insert_batch(batch)
                    total += len(batch)
                    batch.clear()
                    elapsed = time.time() - start_time
                    rate = total / elapsed if elapsed > 0 else 0
                    print(f"{total} máquinas [{elapsed:.0f}s, {rate:.0f} máquinas/s]")
        if batch:
            self._insert_batch(batch)
            total += len(batch)
        self.conn.commit()
        self.conn.close()
        return total

    def _parse_machine(self, elem):
        name = elem.get('name', '')
        # A descrição pode estar em <description> ou em atributo?
        description_elem = elem.find('description')
        description = description_elem.text if description_elem is not None else ''
        cloneof = elem.get('cloneof', '')
        romof = elem.get('romof', '')
        manufacturer_elem = elem.find('manufacturer')
        manufacturer = manufacturer_elem.text if manufacturer_elem is not None else ''
        year_elem = elem.find('year')
        year = year_elem.text if year_elem is not None else ''
        sourcefile = elem.get('sourcefile', '')
        runnable = int(elem.get('runnable', 0))
        isbios = int(elem.get('isbios', 0))
        isdevice = int(elem.get('isdevice', 0))
        ismechanical = int(elem.get('ismechanical', 0))

        # Para 'working', o MAME não tem um atributo direto, mas podemos inferir se há driver status
        # Vamos deixar como 0 e depois atualizar com os INIs.
        working = 0
        players = 0
        # Opcional: extrair número de jogadores de <input>? Não faremos agora.

        # Outros campos serão preenchidos pelos INIs
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
            working=working,
            players=players,
            # Os demais campos ficam vazios ou com valor padrão
        )
        return machine

    def _insert_batch(self, machines):
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