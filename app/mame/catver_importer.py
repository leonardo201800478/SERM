"""Importador do formato CatVer/CatList."""
from __future__ import annotations
from pathlib import Path
import re


def _slug(value: str) -> str:
    """Normaliza categoria para chave SQLite."""
    value=value.lower().replace("&","and")
    return re.sub(r"[^a-z0-9]+","_",value).strip("_") or "uncategorized"


def _read(path: Path):
    """Lê Category e VerAdded preservando somente pares chave/valor."""
    sections={"Category":{},"VerAdded":{}}
    section=""
    for raw in path.read_text(encoding="utf-8-sig",errors="replace").splitlines():
        line=raw.strip()
        if not line or line.startswith((";","#")):continue
        if line.startswith("[") and line.endswith("]"):
            section=line[1:-1].strip();continue
        if section in sections and "=" in line:
            k,v=line.split("=",1);sections[section][k.strip()]=v.strip()
    return sections["Category"],sections["VerAdded"]


class CatverImporter:
    """Atualiza categorias sem substituir o catálogo MAME."""
    def __init__(self,db):self.db=db

    def import_file(self,path:Path|None,run_id:int)->int:
        """Importa categorias e versão de inclusão das machines conhecidas."""
        if not path or not path.is_file():return 0
        categories,versions=_read(path);conn=self.db.conn;assert conn is not None;count=0
        conn.execute("DELETE FROM catver_entry")
        conn.execute("DELETE FROM machine_category")
        for machine,raw in categories.items():
            row=conn.execute("SELECT id FROM machine WHERE name=?",(machine,)).fetchone()
            if not row:continue
            main,_,sub=raw.partition("/");main=main.strip();sub=sub.strip() or None
            key=_slug(main)
            conn.execute("INSERT OR IGNORE INTO category(name,display_name,source) VALUES(?,?,?)",(key,main,"catver.ini"))
            cid=conn.execute("SELECT id FROM category WHERE name=?",(key,)).fetchone()[0]
            conn.execute("INSERT INTO catver_entry(dataset_run_id,machine_id,category_id,main_category,sub_category,version_added,source) VALUES(?,?,?,?,?,?,?)",(run_id,row[0],cid,main,sub,versions.get(machine),str(path)))
            conn.execute("INSERT OR IGNORE INTO machine_category(machine_id,category_id) VALUES(?,?)",(row[0],cid));count+=1
        conn.execute("UPDATE dataset_run SET catver_sha256=? WHERE id=?",(self._sha256(path),run_id));conn.commit();return count

    @staticmethod
    def _sha256(path):
        """Calcula SHA-256 do CatVer em streaming."""
        import hashlib
        h=hashlib.sha256()
        with path.open("rb") as f:
            while chunk:=f.read(1024*1024):h.update(chunk)
        return h.hexdigest()
