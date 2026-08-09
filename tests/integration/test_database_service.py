import unittest
import tempfile
from pathlib import Path
from app.database.database import Database
from app.core.services.database_service import DatabaseService

class TestDatabaseService(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = Path(self.temp_db.name)
        self.db = Database(self.db_path)
        self.db.connect()
        self.service = DatabaseService(self.db)

    def tearDown(self):
        self.db.conn.close()
        self.temp_db.close()
        self.db_path.unlink()

    def test_import_listxml(self):
        xml = '''<?xml version="1.0"?>
        <mame>
            <machine name="test" sourcefile="test.cpp">
                <description>Test Machine</description>
                <year>2025</year>
                <manufacturer>Test</manufacturer>
                <rom name="test.rom" size="1024" crc="12345678" sha1="..."/>
            </machine>
        </mame>'''
        self.service.import_listxml(xml, "dummy/mame.exe", "0.289")
        # Verificar se os dados foram inseridos
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM machine WHERE name='test'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['description'], "Test Machine")
        cursor.execute("SELECT * FROM rom WHERE machine_id=?", (row['id'],))
        rom_row = cursor.fetchone()
        self.assertIsNotNone(rom_row)
        self.assertEqual(rom_row['name'], "test.rom")