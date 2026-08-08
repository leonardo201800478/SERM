"""
Parser streaming para o XML do MAME -listxml (Fase 2).
Extrai informações completas: input, display, sound, chip, etc.
"""

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
            "input": None,
            "input_ports": [],
            "dipswitches": [],
            "configurations": [],
            "displays": [],
            "sound": None,
            "chips": [],
            "slots": [],
            "softwarelists": [],
            "features": [],
            "ramoptions": [],
        }

        for child in elem:
            tag = child.tag

            if tag == "rom":
                data["roms"].append(child.attrib)
            elif tag == "disk":
                data["disks"].append(child.attrib)
            elif tag == "sample":
                data["samples"].append(child.attrib.get("name"))
            elif tag == "driver":
                data["driver"] = child.attrib
            elif tag == "device_ref":
                data["device_refs"].append(child.attrib.get("name"))

            elif tag == "input":
                data["input"] = {
                    "service": child.get("service", ""),
                    "tilt": child.get("tilt", ""),
                    "coin": child.get("coin", ""),
                }
                for port in child:
                    if port.tag == "port":
                        port_data = {
                            "tag": port.get("tag", ""),
                            "type": port.get("type", ""),
                            "mask": port.get("mask"),
                            "defvalue": port.get("defvalue"),
                            "dipswitches": []
                        }
                        for sub in port:
                            if sub.tag == "dipswitch":
                                port_data["dipswitches"].append({
                                    "tag": sub.get("tag", ""),
                                    "name": sub.get("name", ""),
                                    "mask": sub.get("mask"),
                                    "defvalue": sub.get("defvalue"),
                                })
                            elif sub.tag == "configuration":
                                data["configurations"].append({
                                    "tag": sub.get("tag", ""),
                                    "name": sub.get("name", ""),
                                    "mask": sub.get("mask"),
                                    "defvalue": sub.get("defvalue"),
                                })
                        data["input_ports"].append(port_data)

            elif tag == "display":
                data["displays"].append({
                    "tag": child.get("tag", ""),
                    "type": child.get("type", ""),
                    "rotate": child.get("rotate"),
                    "width": child.get("width"),
                    "height": child.get("height"),
                    "refresh": child.get("refresh"),
                    "pixclock": child.get("pixclock"),
                    "htotal": child.get("htotal"),
                    "vtotal": child.get("vtotal"),
                })

            elif tag == "sound":
                data["sound"] = {
                    "channels": child.get("channels"),
                }

            elif tag == "chip":
                data["chips"].append({
                    "tag": child.get("tag", ""),
                    "type": child.get("type", ""),
                    "name": child.get("name", ""),
                    "clock": child.get("clock"),
                })

            elif tag == "slot":
                slot_data = {
                    "name": child.get("name", ""),
                    "options": []
                }
                for opt in child:
                    if opt.tag == "slotoption":
                        slot_data["options"].append({
                            "name": opt.get("name", ""),
                            "devname": opt.get("devname", ""),
                            "default": opt.get("default") == "yes",
                        })
                data["slots"].append(slot_data)

            elif tag == "softwarelist":
                data["softwarelists"].append({
                    "name": child.get("name", ""),
                    "status": child.get("status", ""),
                    "filter": child.get("filter", ""),
                })

            elif tag == "feature":
                data["features"].append({
                    "name": child.get("name", ""),
                    "value": child.get("value", ""),
                })

            elif tag == "ramoption":
                data["ramoptions"].append({
                    "name": child.get("name", ""),
                    "default": child.get("default", ""),
                })

        return data