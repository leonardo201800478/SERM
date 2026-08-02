from pathlib import Path

from lxml import etree
from tqdm import tqdm

from core.database import Database
from core.models import Machine
from repositories.machine_repository import MachineRepository


class XMLParser:
    """
    Responsável por ler o listxml.xml do MAME e importar todas as
    máquinas para o banco SQLite.

    Utiliza iterparse para não carregar todo o XML em memória.
    """

    def __init__(self, xml_file: Path, database_file: Path):

        self.xml_file = xml_file
        self.database_file = database_file

    def parse(self):

        db = Database(self.database_file)

        repo = MachineRepository(db)

        print("Lendo listxml.xml...")

        context = etree.iterparse(
            str(self.xml_file),
            events=("end",),
            tag="machine",
            huge_tree=True,
            recover=True
        )

        total = 0

        for _, elem in tqdm(context, unit=" máquinas"):

            machine = self._parse_machine(elem)

            repo.insert(machine)

            total += 1

            # libera memória
            elem.clear()

            while elem.getprevious() is not None:
                del elem.getparent()[0]

        repo.flush()

        print()

        print(f"Máquinas importadas : {repo.count():,}")

        db.close()

        return total

    def _parse_machine(self, elem) -> Machine:

        machine = Machine(

            name=elem.get("name", ""),

            description="",

            cloneof=elem.get("cloneof"),

            romof=elem.get("romof"),

            manufacturer="",

            year="",

            sourcefile=elem.get("sourcefile", ""),

            runnable=elem.get("runnable", "yes") == "yes",

            isbios=elem.get("isbios", "no") == "yes",

            isdevice=elem.get("isdevice", "no") == "yes",

            ismechanical=elem.get("ismechanical", "no") == "yes",

        )

        for child in elem:

            tag = child.tag

            if tag == "description":

                machine.description = child.text or ""

            elif tag == "manufacturer":

                machine.manufacturer = child.text or ""

            elif tag == "year":

                machine.year = child.text or ""

            elif tag == "driver":

                status = child.get("status", "good")

                machine.working = status == "good"

            elif tag == "input":

                players = child.get("players")

                if players:

                    try:

                        machine.players = int(players)

                    except ValueError:

                        machine.players = 0

                for control in child.findall("control"):

                    ctype = control.get("type")

                    if ctype:

                        machine.controls.add(ctype)

        return machine