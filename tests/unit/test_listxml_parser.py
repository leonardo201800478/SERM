import io
import unittest

from app.mame.listxml import ListXmlParser  # shim de compatibilidade
from app.mame.listxml_parser import iter_machines

SAMPLE_XML = '''<?xml version="1.0"?>
<mame build="0.276">
    <machine name="pacman" sourcefile="pacman.cpp">
        <description>Pac-Man</description>
        <year>1980</year>
        <manufacturer>Namco</manufacturer>
        <driver status="good" savestate="supported" requiresartwork="no"
                unofficial="no" nosoundhardware="no" incomplete="no"/>
        <rom name="pacman.6e" size="4096" crc="c1e6ab10" sha1="abc" offset="0"/>
        <rom name="pacman.6f" size="4096" crc="1a6fb2d4" sha1="def" offset="1000"/>
    </machine>
    <machine name="mspacman" cloneof="pacman" romof="pacman" sourcefile="pacman.cpp">
        <description>Ms. Pac-Man</description>
        <year>1981</year>
        <manufacturer>Midway</manufacturer>
        <driver status="imperfect"/>
        <rom name="boot1" size="2048" crc="12345678" sha1="ghi" merge="boot1"/>
        <disk name="gamedisk" sha1="jkl" index="0"/>
    </machine>
    <machine name="neogeo" isbios="yes" runnable="no">
        <description>Neo-Geo BIOS</description>
    </machine>
</mame>'''


class TestIterMachines(unittest.TestCase):
    def test_parse_from_string(self):
        machines = list(iter_machines(SAMPLE_XML))
        self.assertEqual(len(machines), 3)

    def test_basic_fields(self):
        machines = {m.name: m for m in iter_machines(SAMPLE_XML)}
        pacman = machines["pacman"]
        self.assertEqual(pacman.description, "Pac-Man")
        self.assertEqual(pacman.year, "1980")
        self.assertEqual(pacman.manufacturer, "Namco")
        self.assertEqual(pacman.sourcefile, "pacman.cpp")
        self.assertEqual(len(pacman.roms), 2)

    def test_driver_status_mapping(self):
        machines = {m.name: m for m in iter_machines(SAMPLE_XML)}
        self.assertEqual(machines["pacman"].emulation_status, "working")
        self.assertEqual(machines["mspacman"].emulation_status, "imperfect")
        # Sem <driver>, deve cair em 'unknown'
        self.assertEqual(machines["neogeo"].emulation_status, "unknown")

    def test_driver_flags(self):
        pacman = {m.name: m for m in iter_machines(SAMPLE_XML)}["pacman"]
        self.assertTrue(pacman.savestate)
        self.assertFalse(pacman.requires_artwork)
        self.assertFalse(pacman.unofficial)

    def test_clone_relationship(self):
        mspacman = {m.name: m for m in iter_machines(SAMPLE_XML)}["mspacman"]
        self.assertEqual(mspacman.cloneof, "pacman")
        self.assertEqual(mspacman.romof, "pacman")

    def test_isbios_and_runnable(self):
        neogeo = {m.name: m for m in iter_machines(SAMPLE_XML)}["neogeo"]
        self.assertTrue(neogeo.is_bios)
        self.assertFalse(neogeo.runnable)

    def test_rom_offset_decimal_and_hex(self):
        pacman = {m.name: m for m in iter_machines(SAMPLE_XML)}["pacman"]
        rom_by_name = {r.name: r for r in pacman.roms}
        self.assertEqual(rom_by_name["pacman.6e"].offset, 0)
        # "1000" é interpretado como decimal (1000), pois é decimal válido
        self.assertEqual(rom_by_name["pacman.6f"].offset, 1000)

    def test_rom_hex_only_offset_falls_back_to_base16(self):
        xml = '''<mame>
            <machine name="test">
                <rom name="r1" size="1" crc="x" offset="1a"/>
            </machine>
        </mame>'''
        machine = next(iter_machines(xml))
        self.assertEqual(machine.roms[0].offset, 0x1A)

    def test_disk_parsing(self):
        mspacman = {m.name: m for m in iter_machines(SAMPLE_XML)}["mspacman"]
        self.assertEqual(len(mspacman.disks), 1)
        self.assertEqual(mspacman.disks[0].name, "gamedisk")
        self.assertEqual(mspacman.disks[0].sha1, "jkl")

    def test_accepts_file_like_object(self):
        stream = io.StringIO(SAMPLE_XML)
        machines = list(iter_machines(stream))
        self.assertEqual(len(machines), 3)

    def test_is_generator_not_list(self):
        result = iter_machines(SAMPLE_XML)
        self.assertTrue(hasattr(result, "__next__"))

    def test_backward_compat_shim(self):
        machines = ListXmlParser.parse(SAMPLE_XML)
        self.assertEqual(len(machines), 3)
        self.assertEqual(machines[0].name, "pacman")


if __name__ == "__main__":
    unittest.main()
