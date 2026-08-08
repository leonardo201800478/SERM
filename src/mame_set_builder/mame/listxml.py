# src/mame_set_builder/mame/listxml.py
import xml.etree.ElementTree as ET
from typing import Iterator, Dict, Any
from .executable import MAMEExecutable

class ListXMLStream:
    def __init__(self, executable: MAMEExecutable):
        self.executable = executable

    def iter_machines(self) -> Iterator[Dict[str, Any]]:
        proc = self.executable.generate_listxml()
        context = ET.iterparse(proc.stdout, events=("end",))
        for event, elem in context:
            if elem.tag == "machine":
                machine_dict = self._parse_machine(elem)
                yield machine_dict
                elem.clear()
        proc.stdout.close()
        proc.wait()

    def _parse_machine(self, elem: ET.Element) -> Dict[str, Any]:
        data = {
            "name": elem.get("name"),
            "description": elem.get("description", ""),
            "year": elem.get("year", ""),
            "manufacturer": elem.get("manufacturer", ""),
            "cloneof": elem.get("cloneof", ""),
            "romof": elem.get("romof", ""),
            "sampleof": elem.get("sampleof", ""),
            "isbios": elem.get("isbios", "no") == "yes",
            "isdevice": elem.get("isdevice", "no") == "yes",
            "ismechanical": elem.get("ismechanical", "no") == "yes",
            "runnable": elem.get("runnable", "yes") == "yes",
            "sourcefile": elem.get("sourcefile", ""),
            "roms": [],
            "disks": [],
            "samples": [],
            "driver": {},
            "device_refs": [],
        }
        for child in elem:
            if child.tag == "rom":
                data["roms"].append(child.attrib)
            elif child.tag == "disk":
                data["disks"].append(child.attrib)
            elif child.tag == "sample":
                data["samples"].append(child.attrib.get("name"))
            elif child.tag == "driver":
                data["driver"] = child.attrib
            elif child.tag == "device_ref":
                data["device_refs"].append(child.attrib.get("name"))
        return data