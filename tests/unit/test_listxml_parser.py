import unittest
from app.mame.listxml import ListXmlParser

class TestListXmlParser(unittest.TestCase):
    def test_parse_minimal(self):
        xml = '''<?xml version="1.0"?>
        <mame>
            <machine name="pacman" sourcefile="pacman.cpp">
                <description>Pac-Man</description>
                <year>1980</year>
                <manufacturer>Namco</manufacturer>
                <rom name="pacman.6e" size="4096" crc="c1e6ab10" sha1="..."/>
            </machine>
        </mame>'''
        machines = ListXmlParser.parse(xml)
        self.assertEqual(len(machines), 1)
        machine = machines[0]
        self.assertEqual(machine.name, "pacman")
        self.assertEqual(machine.description, "Pac-Man")
        self.assertEqual(len(machine.roms), 1)
        rom = machine.roms[0]
        self.assertEqual(rom.name, "pacman.6e")
        self.assertEqual(rom.size, 4096)
        self.assertEqual(rom.crc, "c1e6ab10")