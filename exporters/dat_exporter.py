# exporters/dat_exporter.py
from pathlib import Path
from lxml import etree
from typing import List
from core.models import Machine

class DATExporter:
    def __init__(self, machines: List[Machine], output_file: Path, dat_name: str = "MAME Set Builder"):
        self.machines = machines
        self.output_file = output_file
        self.dat_name = dat_name

    def export(self):
        root = etree.Element("datafile")
        root.set("xmlns", "http://www.logiqx.com/DTDs/ROM-Management-Datafile.dtd")

        # Header
        header = etree.SubElement(root, "header")
        etree.SubElement(header, "name").text = self.dat_name
        etree.SubElement(header, "description").text = f"Set filtrado - {len(self.machines)} máquinas"
        etree.SubElement(header, "version").text = "1.0"
        etree.SubElement(header, "author").text = "leonardo201800478"

        # Para cada máquina, criar a tag <game>
        for machine in self.machines:
            game = etree.SubElement(root, "game")
            game.set("name", machine.name)

            desc = etree.SubElement(game, "description")
            desc.text = machine.description or machine.name

            if machine.manufacturer:
                etree.SubElement(game, "manufacturer").text = machine.manufacturer
            if machine.year:
                etree.SubElement(game, "year").text = machine.year

            # Se você tiver informações de ROM (crc, sha1, size), pode adicionar aqui.
            # Exemplo:
            # for rom in machine.roms:
            #     elem = etree.SubElement(game, "rom")
            #     elem.set("name", rom.name)
            #     elem.set("size", str(rom.size))
            #     elem.set("crc", rom.crc)

        # Escreve o arquivo
        tree = etree.ElementTree(root)
        tree.write(self.output_file, encoding="utf-8", xml_declaration=True, pretty_print=True)
        print(f"DAT exportado: {self.output_file}")