"""Normalização eficiente do catálogo MAME a partir do ListXML.

O XML bruto permanece como fonte de verdade. Este módulo cria o catálogo
relacional necessário para filtros, reconstrução de ROMs/CHDs e construção de
sets, evitando a tabela genérica de milhões de nós XML.
"""
from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from collections.abc import Callable
from time import perf_counter
from typing import Any


class MameCatalogNormalizationError(RuntimeError):
    """Erro durante a normalização relacional do ListXML."""


class MameCatalogNormalizer:
    """Persiste o catálogo sem duplicar a árvore XML completa."""

    BATCH_SIZE = 1000

    def __init__(self, logger: Callable[[str], None] | None = None) -> None:
        self.logger = logger or (lambda _message: None)

    def _log(self, message: str) -> None:
        """Emite uma mensagem compacta de progresso."""
        self.logger(message)

    def normalize(self, db: sqlite3.Connection, import_id: int, root: ET.Element) -> dict[str, int | float]:
        """Normaliza todas as entidades conhecidas do ListXML em uma transação.

        A função não cria profiles, não interpreta INIs e não toma decisões de
        configuração. Ela somente transforma os dados fornecidos pelo MAME em
        tabelas relacionais consultáveis.
        """
        machines = root.findall("machine")
        started = perf_counter()
        self._clear_import(db, import_id)
        machine_ids: dict[str, int] = {}
        totals = {"machines": 0, "roms": 0, "disks": 0, "samples": 0, "displays": 0,
                  "chips": 0, "devices": 0, "device_refs": 0, "biossets": 0,
                  "inputs": 0, "controls": 0, "dipswitches": 0, "dipvalues": 0,
                  "configurations": 0, "confsettings": 0, "ports": 0, "adjusters": 0,
                  "drivers": 0, "features": 0, "slots": 0, "slot_options": 0,
                  "softwarelists": 0, "ramoptions": 0}

        for start in range(0, len(machines), self.BATCH_SIZE):
            batch = machines[start:start + self.BATCH_SIZE]
            for machine in batch:
                name = machine.attrib.get("name", "")
                if not name:
                    raise MameCatalogNormalizationError(f"Machine sem nome no import_id={import_id}.")
                machine_id = self._insert_machine(db, import_id, machine)
                machine_ids[name] = machine_id
                totals["machines"] += 1
                self._insert_children(db, machine_id, machine, totals)

            processed = min(start + self.BATCH_SIZE, len(machines))
            elapsed = perf_counter() - started
            rate = processed / elapsed if elapsed else 0.0
            eta = (len(machines) - processed) / rate if rate else 0.0
            self._log(
                f"MAME | CATALOG | {processed:,}/{len(machines):,} | "
                f"{processed * 100 / len(machines):6.2f}% | {rate:,.0f} máquinas/s | "
                f"ETA={self._format_seconds(eta)} | ROMs={totals['roms']:,} | "
                f"disks={totals['disks']:,} | displays={totals['displays']:,}"
            )

        elapsed = perf_counter() - started
        totals["elapsed_seconds"] = elapsed
        totals["machine_ids"] = len(machine_ids)
        return totals

    @staticmethod
    def _clear_import(db: sqlite3.Connection, import_id: int) -> None:
        """Remove dados derivados de uma importação antes de uma reingestão forçada."""
        # As tabelas filhas dependem das máquinas. A remoção das máquinas em
        # cascata limpa todo o catálogo derivado sem tocar no documento lossless.
        db.execute("DELETE FROM mame_machine WHERE import_id=?", (import_id,))

    @staticmethod
    def _insert_machine(db: sqlite3.Connection, import_id: int, machine: ET.Element) -> int:
        """Insere uma máquina e seus metadados básicos."""
        a = machine.attrib
        cur = db.execute(
            """INSERT INTO mame_machine
            (import_id,name,sourcefile,isbios,isdevice,ismechanical,runnable,cloneof,romof,
             sampleof,description,year,manufacturer,ingested_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
            (import_id, a.get("name", ""), a.get("sourcefile"), a.get("isbios"),
             a.get("isdevice"), a.get("ismechanical"), a.get("runnable"), a.get("cloneof"),
             a.get("romof"), a.get("sampleof"), machine.findtext("description"),
             machine.findtext("year"), machine.findtext("manufacturer")),
        )
        machine_id = int(cur.lastrowid)
        driver = machine.find("driver")
        d = driver.attrib if driver is not None else {}
        db.execute(
            """INSERT INTO mame_machine_metadata
            (machine_id,emulation_status,driver_status,savestate,requires_artwork,unofficial,nosoundhardware,incomplete)
            VALUES(?,?,?,?,?,?,?,?)""",
            (machine_id, d.get("status") or d.get("emulation"), d.get("status"),
             d.get("savestate"), d.get("requires_artwork"), d.get("unofficial"),
             d.get("nosoundhardware"), d.get("incomplete")),
        )
        return machine_id

    def _insert_children(self, db: sqlite3.Connection, machine_id: int, machine: ET.Element, totals: dict[str, int | float]) -> None:
        """Persiste os elementos filhos definidos pelo ListXML."""
        for element in machine.findall("biosset"):
            a = element.attrib
            db.execute("INSERT INTO mame_biosset(machine_id,name,description,default_flag) VALUES(?,?,?,?)",
                       (machine_id, a.get("name"), a.get("description"), a.get("default")))
            totals["biossets"] += 1
        for element in machine.findall("rom"):
            a = element.attrib
            db.execute("""INSERT INTO mame_rom(machine_id,name,bios,size,crc,sha1,md5,merge,region,offset,status,optional,dispose)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                       (machine_id, a.get("name"), a.get("bios"), self._int(a.get("size")), a.get("crc"),
                        a.get("sha1"), a.get("md5"), a.get("merge"), a.get("region"), a.get("offset"),
                        a.get("status"), a.get("optional"), a.get("dispose")))
            totals["roms"] += 1
        for element in machine.findall("disk"):
            a = element.attrib
            db.execute("""INSERT INTO mame_disk(machine_id,name,md5,sha1,merge,region,index_value,writable,status,optional)
                         VALUES(?,?,?,?,?,?,?,?,?,?)""",
                       (machine_id, a.get("name"), a.get("md5"), a.get("sha1"), a.get("merge"),
                        a.get("region"), a.get("index"), a.get("writable"), a.get("status"), a.get("optional")))
            totals["disks"] += 1
        for element in machine.findall("device_ref"):
            a = element.attrib
            db.execute("INSERT INTO mame_device_ref(machine_id,name,tag,mandatory) VALUES(?,?,?,?)",
                       (machine_id, a.get("name"), a.get("tag"), a.get("mandatory")))
            totals["device_refs"] += 1
        for element in machine.findall("sample"):
            db.execute("INSERT INTO mame_sample(machine_id,name) VALUES(?,?)", (machine_id, element.attrib.get("name")))
            totals["samples"] += 1
        for element in machine.findall("chip"):
            a = element.attrib
            db.execute("INSERT INTO mame_chip(machine_id,type,tag,name,clock) VALUES(?,?,?,?,?)",
                       (machine_id, a.get("type"), a.get("tag"), a.get("name"), a.get("clock")))
            totals["chips"] += 1
        for element in machine.findall("display"):
            a = element.attrib
            db.execute("""INSERT INTO mame_display
                (machine_id,tag,type,rotate,width,height,refresh_hz,refresh_raw,pixclock,htotal,hbend,hbstart,
                 vtotal,vbend,vbstart,hsync,vsync,xaspect,yaspect,orientation_raw)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                       (machine_id, a.get("tag"), a.get("type"), a.get("rotate"), self._int(a.get("width")),
                        self._int(a.get("height")), self._float(a.get("refresh")), a.get("refresh"),
                        a.get("pixclock"), a.get("htotal"), a.get("hbend"), a.get("hbstart"), a.get("vtotal"),
                        a.get("vbend"), a.get("vbstart"), a.get("hsync"), a.get("vsync"),
                        self._int(a.get("xaspect")), self._int(a.get("yaspect")), a.get("rotate")))
            totals["displays"] += 1
        self._insert_input(db, machine_id, machine, totals)
        self._insert_named_children(db, machine_id, machine, totals)

    def _insert_input(self, db: sqlite3.Connection, machine_id: int, machine: ET.Element, totals: dict[str, int | float]) -> None:
        """Persiste input e controles associados."""
        element = machine.find("input")
        if element is None:
            return
        a = element.attrib
        cur = db.execute("INSERT INTO mame_input(machine_id,players,coins,service,tilt) VALUES(?,?,?,?,?)",
                         (machine_id, self._int(a.get("players")), self._int(a.get("coins")),
                          self._int(a.get("service")), self._int(a.get("tilt"))))
        input_id = int(cur.lastrowid)
        totals["inputs"] += 1
        for control in element.findall("control"):
            c = control.attrib
            db.execute("""INSERT INTO mame_control
                (input_id,type,player,buttons,minimum,maximum,sensitivity,keydelta,reverse,ways)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                       (input_id, c.get("type"), self._int(c.get("player")), self._int(c.get("buttons")),
                        self._int(c.get("minimum")), self._int(c.get("maximum")), self._int(c.get("sensitivity")),
                        self._int(c.get("keydelta")), c.get("reverse"), c.get("ways")))
            totals["controls"] += 1

    def _insert_named_children(self, db: sqlite3.Connection, machine_id: int, machine: ET.Element, totals: dict[str, int | float]) -> None:
        """Persiste configurações, portas, drivers, slots, devices e listas de software."""
        for element in machine.findall("dipswitch"):
            a = element.attrib
            cur = db.execute("INSERT INTO mame_dipswitch(machine_id,name,tag,mask,value,default_value) VALUES(?,?,?,?,?,?)",
                             (machine_id, a.get("name"), a.get("tag"), a.get("mask"), a.get("value"), a.get("default")))
            did = int(cur.lastrowid); totals["dipswitches"] += 1
            for value in element.findall("dipvalue"):
                v = value.attrib
                db.execute("INSERT INTO mame_dipvalue(dipswitch_id,name,value,description) VALUES(?,?,?,?)",
                           (did, v.get("name"), v.get("value"), v.get("description"))); totals["dipvalues"] += 1
        for element in machine.findall("configuration"):
            a = element.attrib
            cur = db.execute("INSERT INTO mame_configuration(machine_id,name,tag,mask,value,default_value) VALUES(?,?,?,?,?,?)",
                             (machine_id, a.get("name"), a.get("tag"), a.get("mask"), a.get("value"), a.get("default")))
            cid = int(cur.lastrowid); totals["configurations"] += 1
            for value in element.findall("confsetting"):
                v = value.attrib
                db.execute("INSERT INTO mame_confsetting(configuration_id,name,value) VALUES(?,?,?)",
                           (cid, v.get("name"), v.get("value"))); totals["confsettings"] += 1
        for element in machine.findall("port"):
            a = element.attrib
            db.execute("INSERT INTO mame_port(machine_id,tag,type,mask,defvalue,condition) VALUES(?,?,?,?,?,?)",
                       (machine_id, a.get("tag"), a.get("type"), a.get("mask"), a.get("defvalue"), a.get("condition"))); totals["ports"] += 1
        for element in machine.findall("adjuster"):
            a = element.attrib
            db.execute("INSERT INTO mame_adjuster(machine_id,name,default_value,min_value,max_value) VALUES(?,?,?,?,?)",
                       (machine_id, a.get("name"), a.get("default"), a.get("minimum"), a.get("maximum"))); totals["adjusters"] += 1
        driver = machine.find("driver")
        if driver is not None:
            a = driver.attrib
            db.execute("""INSERT INTO mame_driver(machine_id,status,emulation,color,sound,graphic,cocktail,protection,savestate,requires_artwork,unofficial,incomplete,notes)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                       (machine_id, a.get("status"), a.get("emulation"), a.get("color"), a.get("sound"), a.get("graphic"),
                        a.get("cocktail"), a.get("protection"), a.get("savestate"), a.get("requires_artwork"),
                        a.get("unofficial"), a.get("incomplete"), a.get("notes"))); totals["drivers"] += 1
        for element in machine.findall("feature"):
            a = element.attrib
            db.execute("INSERT INTO mame_feature(machine_id,type,status) VALUES(?,?,?)", (machine_id, a.get("type"), a.get("status"))); totals["features"] += 1
        for element in machine.findall("device"):
            a = element.attrib
            db.execute("INSERT INTO mame_device(machine_id,type,tag,name,clock) VALUES(?,?,?,?,?)",
                       (machine_id, a.get("type"), a.get("tag"), a.get("name"), a.get("clock"))); totals["devices"] += 1
        for element in machine.findall("slot"):
            a = element.attrib
            cur = db.execute("INSERT INTO mame_slot(machine_id,name) VALUES(?,?)", (machine_id, a.get("name", "")))
            sid = int(cur.lastrowid); totals["slots"] += 1
            for option in element.findall("slotoption"):
                o = option.attrib
                db.execute("INSERT INTO mame_slot_option(slot_id,name,devname,is_default) VALUES(?,?,?,?)",
                           (sid, o.get("name", ""), o.get("devname"), o.get("default"))); totals["slot_options"] += 1
        for element in machine.findall("softwarelist"):
            a = element.attrib
            db.execute("INSERT INTO mame_softwarelist(machine_id,tag,name,status,filter) VALUES(?,?,?,?,?)",
                       (machine_id, a.get("tag"), a.get("name"), a.get("status"), a.get("filter"))); totals["softwarelists"] += 1
        for element in machine.findall("ramoption"):
            a = element.attrib
            db.execute("INSERT INTO mame_ramoption(machine_id,name,default_value) VALUES(?,?,?)",
                       (machine_id, a.get("name"), a.get("default"))); totals["ramoptions"] += 1

    @staticmethod
    def _int(value: str | None) -> int | None:
        """Converte inteiro opcional."""
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _float(value: str | None) -> float | None:
        """Converte número real opcional."""
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        """Formata ETA de maneira compacta."""
        seconds = max(0, int(seconds))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"


__all__ = ["MameCatalogNormalizationError", "MameCatalogNormalizer"]
