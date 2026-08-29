import tempfile
import unittest
from pathlib import Path

from app.core.services.database_service import DatabaseService
from app.database.database import Database


class TestDatabaseService(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = Path(self.temp_db.name)
        self.db = Database(self.db_path)
        self.db.connect()
        # DatabaseService espera uma conexão sqlite3, não o wrapper Database.
        self.service = DatabaseService(self.db.conn)

        # import_listxml calcula o hash SHA-256 do "executável" na primeira
        # importação, então precisa apontar para um arquivo que existe de
        # verdade (mesmo que não seja um binário MAME real).
        self.fake_exe = tempfile.NamedTemporaryFile(suffix='.exe', delete=False)
        self.fake_exe.write(b"fake mame binary")
        self.fake_exe.close()

    def tearDown(self):
        self.db.conn.close()
        self.temp_db.close()
        self.db_path.unlink()
        Path(self.fake_exe.name).unlink()

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
        self.service.import_listxml(xml, self.fake_exe.name, "0.289")
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