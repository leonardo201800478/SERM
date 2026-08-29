"""Orquestração do dataset MAME: LISTXML, CatVer e CHD."""
from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path

from app.config.app_config import AppConfig
from app.database.dataset_schema import ensure_dataset_schema
from app.mame.catver_importer import CatverImporter
from app.mame.chd_dataset_scanner import ChdDatasetScanner
from app.mame.dataset_importer import DatasetImporter


class MameDatasetBuilder:
    """Executa a reconstrução completa do catálogo persistente."""
    def __init__(self, db, config: AppConfig | None = None):
        self.db=db; self.config=config or AppConfig()

    def run(self, progress:Callable[[int,str],None]|None=None, cancelled:Callable[[],bool]|None=None)->dict:
        """Gera LISTXML, importa o banco, aplica CatVer e verifica CHDs."""
        mame=self.config.mame_path
        if not mame or not mame.is_file():raise RuntimeError("Configure um executável MAME válido primeiro.")
        self.db.connect(); ensure_dataset_schema(self.db)
        version=self._version(mame); xml=self.config.DB_DIR/"listxml"/f"mame_{version}.xml"; xml.parent.mkdir(parents=True,exist_ok=True)
        catver=self._find_catver(); run_id=self._start_run(version,xml,catver)
        try:
            self._emit(progress,0,"Gerando LISTXML do MAME..."); self._generate_xml(mame,xml,cancelled)
            stats=DatasetImporter(self.db,self.config).import_xml(xml,run_id,progress,cancelled)
            self._emit(progress,stats["machines"],"Atualizando CatVer..."); stats["catver"]=CatverImporter(self.db).import_file(catver,run_id) if catver else 0
            self._emit(progress,stats["machines"],"Verificando CHDs..."); stats["chds"]=ChdDatasetScanner(self.db,self.config).scan(run_id,progress,cancelled)
            self._finish(run_id,"completed",stats); self._emit(progress,stats["machines"],"Dataset MAME concluído.")
            return {**stats,"run_id":run_id,"xml_path":str(xml)}
        except Exception as exc:
            self._finish(run_id,"failed",{},str(exc)); raise

    @staticmethod
    def _emit(cb,value,message):
        """Emite progresso sem depender da GUI."""
        if cb:cb(value,message)

    @staticmethod
    def _version(mame:Path)->str:
        """Obtém a versão do executável MAME."""
        p=subprocess.run([str(mame),"-version"],capture_output=True,text=True,encoding="utf-8",errors="ignore",timeout=10,shell=False)
        m=re.search(r"(?:MAME\s+)?([0-9]+(?:\.[0-9]+)+)",p.stdout+p.stderr,re.IGNORECASE); return m.group(1) if m else "unknown"

    def _find_catver(self)->Path|None:
        """Localiza CatVer configurado, ao lado do MAME ou no diretório de suporte."""
        candidates=[]; configured=getattr(self.config,"catver_path",None)
        if configured:candidates.append(Path(configured))
        if self.config.mame_path:candidates.append(self.config.mame_path.parent/"catver.ini")
        candidates.append(self.config.DB_DIR/"support"/"catver.ini")
        return next((p for p in candidates if p.is_file()),None)

    def _start_run(self,version,xml,catver)->int:
        """Registra a execução do dataset."""
        path=str(self.config.mame_path); row=self.db.fetchone("SELECT id FROM mame_installation WHERE executable_path=?",(path,))
        iid=row[0] if row else self.db.execute("INSERT INTO mame_installation(version,executable_path,executable_hash) VALUES(?,?,?)",(version,path,"" )).lastrowid
        cur=self.db.execute("INSERT INTO dataset_run(mame_installation_id,mame_version,xml_path,catver_path,status) VALUES(?,?,?,?, 'running')",(iid,version,str(xml),str(catver) if catver else None)); self.db.conn.commit(); return int(cur.lastrowid)

    def _generate_xml(self,executable,output,cancelled):
        """Executa -listxml e grava stdout em arquivo temporário."""
        tmp=output.with_suffix(output.suffix+".tmp"); p=subprocess.Popen([str(executable),"-listxml"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False)
        try:
            with tmp.open("wb") as out:
                assert p.stdout is not None
                while chunk:=p.stdout.read(1024*1024):
                    if cancelled and cancelled():p.kill();raise RuntimeError("Operação cancelada.")
                    out.write(chunk)
            err=p.stderr.read().decode("utf-8","replace") if p.stderr else ""; code=p.wait(timeout=120)
            if code:raise RuntimeError(f"mame -listxml falhou ({code}): {err.strip()}")
            tmp.replace(output)
        finally:
            if p.poll() is None:p.kill();p.wait()
            tmp.unlink(missing_ok=True)

    def _finish(self,run_id,status,stats,error=None):
        """Finaliza a execução persistida."""
        self.db.execute("UPDATE dataset_run SET status=?,finished_at=CURRENT_TIMESTAMP,error=?,machine_count=COALESCE(?,machine_count),rom_count=COALESCE(?,rom_count),disk_count=COALESCE(?,disk_count),chd_count=COALESCE(?,chd_count) WHERE id=?",(status,error,stats.get("machines"),stats.get("roms"),stats.get("disks"),stats.get("chds"),run_id));self.db.conn.commit()
