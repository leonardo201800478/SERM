"""Importador streaming do LISTXML para todas as entidades úteis do SQLite."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


def a(e, n, d=""):
    """Obtém atributo XML."""
    return (e.get(n, d) if e is not None else d).strip()


def t(e, n):
    """Obtém texto de filho XML."""
    x=e.find(n)
    return (x.text or "").strip() if x is not None else ""


def y(v, default=False):
    """Converte yes/no para SQLite."""
    return int(default if not v else v.lower() in {"yes","true","1"})


def i(v, default=0):
    """Converte inteiro decimal/hexadecimal."""
    if not v:return default
    try:return int(v,0)
    except ValueError:
        try:return int(v)
        except ValueError:return default


def f(v, default=0.0):
    """Converte número real."""
    try:return float(v) if v else default
    except ValueError:return default


class DatasetImporter:
    """Substitui o dataset derivado do LISTXML sem tocar nos perfis."""
    def __init__(self, db, config=None):
        self.db=db
        self.config=config

    def import_xml(self, path: Path, run_id: int, progress=None, cancelled=None):
        """Importa machines/ROMs/disks e entidades auxiliares em streaming."""
        self._clear()
        conn=self.db.conn; assert conn is not None
        conn.commit(); conn.execute("BEGIN")
        machines=roms=disks=0
        try:
            for _, machine in ET.iterparse(path, events=("end",)):
                if machine.tag!="machine":continue
                m,r,d=self._machine(machine)
                machines+=m;roms+=r;disks+=d
                machine.clear()
                if progress and machines%100==0:progress(machines,f"LISTXML: {machines} machines importadas...")
                if cancelled and cancelled():raise RuntimeError("Operação cancelada.")
            conn.commit()
        except Exception:
            conn.rollback();raise
        conn.execute("UPDATE dataset_run SET machine_count=?,rom_count=?,disk_count=? WHERE id=?",(machines,roms,disks,run_id));conn.commit()
        return {"machines":machines,"roms":roms,"disks":disks,"catver":0,"chds":0}

    def _clear(self):
        """Limpa somente dados derivados do LISTXML."""
        for table in ("rom_source_match","chd_scan","catver_entry","machine_category","control","input","display","chip","device","bios","slot_option","slot","software_list","feature","chd_dependency","rom","disk","machine"):
            if self.db.table_exists(table):self.db.execute(f"DELETE FROM {table}")

    def _machine(self,e):
        """Persiste uma machine e seus filhos."""
        conn=self.db.conn;assert conn is not None
        d=e.find("driver")
        iid=self._installation_id()
        cur=conn.execute("""INSERT INTO machine(name,description,year,manufacturer,sourcefile,cloneof,romof,sampleof,is_bios,is_device,is_mechanical,runnable,emulation_status,driver_status,savestate,requires_artwork,unofficial,nosoundhardware,incomplete,mame_installation_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET description=excluded.description,year=excluded.year,manufacturer=excluded.manufacturer,sourcefile=excluded.sourcefile,cloneof=excluded.cloneof,romof=excluded.romof,sampleof=excluded.sampleof,is_bios=excluded.is_bios,is_device=excluded.is_device,is_mechanical=excluded.is_mechanical,runnable=excluded.runnable,emulation_status=excluded.emulation_status,driver_status=excluded.driver_status,savestate=excluded.savestate,requires_artwork=excluded.requires_artwork,unofficial=excluded.unofficial,nosoundhardware=excluded.nosoundhardware,incomplete=excluded.incomplete,mame_installation_id=excluded.mame_installation_id""",(a(e,"name"),t(e,"description"),t(e,"year"),t(e,"manufacturer"),a(e,"sourcefile"),a(e,"cloneof"),a(e,"romof"),a(e,"sampleof"),y(a(e,"isbios")),y(a(e,"isdevice")),y(a(e,"ismechanical")),y(a(e,"runnable"),True),a(d,"emulation"),a(d,"status"),y(a(d,"savestate")),y(a(d,"requires_artwork")),y(a(d,"unofficial")),y(a(d,"nosoundhardware")),y(a(d,"incomplete")),iid))
        mid=conn.execute("SELECT id FROM machine WHERE name=?",(a(e,"name"),)).fetchone()[0]
        roms=e.findall("rom");disks=e.findall("disk")
        for r in roms:conn.execute("INSERT INTO rom(machine_id,name,size,crc,sha1,merge,region,offset,status,optional,bios) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(mid,a(r,"name"),i(a(r,"size")),a(r,"crc").lower(),a(r,"sha1").lower(),a(r,"merge"),a(r,"region"),i(a(r,"offset")),a(r,"status","good"),y(a(r,"optional")),a(r,"bios")))
        for x in disks:conn.execute("INSERT INTO disk(machine_id,name,sha1,merge,region,disk_index,writable,status,optional,size) VALUES(?,?,?,?,?,?,?,?,?,?)",(mid,a(x,"name"),a(x,"sha1").lower(),a(x,"merge"),a(x,"region"),i(a(x,"index")),y(a(x,"writable")),a(x,"status","good"),y(a(x,"optional")),0))
        for b in e.findall("biosset"):conn.execute("INSERT INTO bios(machine_id,name,description,is_default) VALUES(?,?,?,?)",(mid,a(b,"name"),a(b,"description"),y(a(b,"default"))))
        for x in e.findall("device"):conn.execute("INSERT INTO device(machine_id,tag,name) VALUES(?,?,?)",(mid,a(x,"tag"),a(x,"name")))
        for x in e.findall("chip"):conn.execute("INSERT INTO chip(machine_id,type,tag,name,clock) VALUES(?,?,?,?,?)",(mid,a(x,"type"),a(x,"tag"),a(x,"name"),i(a(x,"clock"))))
        for x in e.findall("display"):conn.execute("INSERT INTO display(machine_id,tag,type,rotate,flipx,width,height,refresh) VALUES(?,?,?,?,?,?,?,?)",(mid,a(x,"tag"),a(x,"type"),i(a(x,"rotate")),y(a(x,"flipx")),i(a(x,"width")),i(a(x,"height")),f(a(x,"refresh"))))
        inp=e.find("input")
        if inp is not None:
            iid2=conn.execute("INSERT INTO input(machine_id,players,coins,service,tilt) VALUES(?,?,?,?,?)",(mid,i(a(inp,"players"),1),i(a(inp,"coins")),i(a(inp,"service")),y(a(inp,"tilt")))).lastrowid
            for c in inp.findall("control"):conn.execute("INSERT INTO control(input_id,type,player,buttons,minimum,maximum,sensitivity,keydelta,reverse,ways) VALUES(?,?,?,?,?,?,?,?,?,?)",(iid2,a(c,"type"),i(a(c,"player")),i(a(c,"buttons")),i(a(c,"minimum")),i(a(c,"maximum")),i(a(c,"sensitivity")),i(a(c,"keydelta")),y(a(c,"reverse")),i(a(c,"ways"))))
        for x in e.findall("feature"):conn.execute("INSERT INTO feature(machine_id,type,status,overall) VALUES(?,?,?,?)",(mid,a(x,"type"),a(x,"status"),a(x,"overall")))
        for x in e.findall("softwarelist"):conn.execute("INSERT INTO software_list(machine_id,tag,name,status,filter) VALUES(?,?,?,?,?)",(mid,a(x,"tag"),a(x,"name"),a(x,"status"),a(x,"filter")))
        for s in e.findall("slot"):
            sid=conn.execute("INSERT INTO slot(machine_id,name) VALUES(?,?)",(mid,a(s,"name"))).lastrowid
            for o in s.findall("slotoption"):conn.execute("INSERT INTO slot_option(slot_id,name,devname,is_default) VALUES(?,?,?,?)",(sid,a(o,"name"),a(o,"devname"),y(a(o,"default"))))
        return 1,len(roms),len(disks)

    def _installation_id(self):
        """Retorna a instalação MAME atual."""
        path=str(self.config.mame_path) if self.config and self.config.mame_path else self.db.fetchone("SELECT executable_path FROM mame_installation ORDER BY id DESC LIMIT 1")[0]
        row=self.db.fetchone("SELECT id FROM mame_installation WHERE executable_path=?",(path,))
        if not row:raise RuntimeError("Instalação MAME não encontrada.")
        return row[0]
