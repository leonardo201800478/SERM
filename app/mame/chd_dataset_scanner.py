"""Scanner de CHDs físicos usando chdman sem opção de reparo."""
from __future__ import annotations
import re
import subprocess
from pathlib import Path
from app.config.app_config import AppConfig

class ChdDatasetScanner:
    """Localiza CHDs no rompath e verifica integridade."""
    def __init__(self,db,config:AppConfig):self.db=db;self.config=config

    def scan(self,run_id:int,progress=None,cancelled=None)->int:
        """Verifica todos os CHDs esperados no catálogo atual."""
        conn=self.db.conn;assert conn is not None
        chdman=self._find_chdman();count=0
        rows=conn.execute("SELECT d.id,d.machine_id,m.name,d.name FROM disk d JOIN machine m ON m.id=d.machine_id").fetchall()
        for disk_id,machine_id,machine,disk in rows:
            if cancelled and cancelled():raise RuntimeError("Operação cancelada.")
            path=self._find(machine,disk)
            if not path:continue
            status="found";error=None;sha=data=None
            if chdman:status,error,sha,data=self._verify(chdman,path)
            conn.execute("INSERT OR REPLACE INTO chd_scan(dataset_run_id,machine_id,disk_id,path,file_size,header_sha1,data_sha1,verify_status,checked_at,error) VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,?)",(run_id,machine_id,disk_id,str(path),path.stat().st_size,sha,data,status,error))
            conn.execute("UPDATE disk SET size=?,status=? WHERE id=?",(path.stat().st_size,"good" if status in {"found","verified"} else "bad",disk_id));count+=1
            if progress and count%20==0:progress(count,f"CHD: {count} encontrados/verificados...")
        conn.execute("UPDATE dataset_run SET chd_count=? WHERE id=?",(count,run_id));conn.commit();return count

    def _find(self,machine,disk):
        """Procura CHD pela convenção <rompath>/<machine>/<disk>.chd."""
        for root in self.config.source_dirs:
            p=Path(root)/machine/(disk+".chd")
            if p.is_file():return p
        return None

    def _find_chdman(self):
        """Localiza o chdman distribuído com MAME."""
        if not self.config.mame_path:return None
        for name in ("chdman.exe","chdman"):
            p=self.config.mame_path.parent/name
            if p.is_file():return p
        return None

    @staticmethod
    def _verify(chdman:Path,path:Path):
        """Executa verify/info sem --fix e captura SHA1 do CHD."""
        try:
            v=subprocess.run([str(chdman),"verify","-i",str(path)],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=3600,shell=False)
            i=subprocess.run([str(chdman),"info","-i",str(path)],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=120,shell=False)
            out=(i.stdout or "")+"\n"+(i.stderr or "")
            sha=re.search(r"^SHA1:\s*([0-9a-fA-F]{40})",out,re.M);data=re.search(r"^Data SHA1:\s*([0-9a-fA-F]{40})",out,re.M)
            err=None if v.returncode==0 else ((v.stdout or "")+(v.stderr or ""))[-1000:]
            return ("verified" if v.returncode==0 else "invalid",err,sha.group(1).lower() if sha else None,data.group(1).lower() if data else None)
        except Exception as exc:return "error",str(exc),None,None
