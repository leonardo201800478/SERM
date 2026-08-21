"""Scanner físico expected-driven de ROMs e CHDs MAME.

O LISTXML/banco define o que deve ser procurado. O scanner nunca enumera o
HDD inteiro: consulta somente ``machine.zip``, ``machine/<rom>`` e
``machine/<disk>.chd``. SQLite e JSONL são atualizados por machine concluída.
CHDs não são lidos no scan; SHA-1/chdman permanecem na reconstrução.
"""
from __future__ import annotations
import hashlib, json, logging, sqlite3, time, zlib, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable
logger = logging.getLogger(__name__)

class PhysicalRomScanner:
    """Scanner físico orientado pelos requisitos do LISTXML."""
    CHUNK_SIZE = 1024 * 1024
    _SCAN_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS rom_scan_run (id INTEGER PRIMARY KEY AUTOINCREMENT,dataset_run_id INTEGER,source_count INTEGER NOT NULL DEFAULT 0,started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,finished_at TIMESTAMP,status TEXT NOT NULL,archive_count INTEGER NOT NULL DEFAULT 0,member_count INTEGER NOT NULL DEFAULT 0,loose_file_count INTEGER NOT NULL DEFAULT 0,bytes_read INTEGER NOT NULL DEFAULT 0,valid_match_count INTEGER NOT NULL DEFAULT 0,unmatched_count INTEGER NOT NULL DEFAULT 0,error TEXT);
    CREATE TABLE IF NOT EXISTS rom_source_match (id INTEGER PRIMARY KEY AUTOINCREMENT,dataset_run_id INTEGER,scan_run_id INTEGER,rom_id INTEGER,source_path TEXT NOT NULL,archive_member TEXT,source_kind TEXT NOT NULL,actual_size INTEGER NOT NULL,actual_crc TEXT NOT NULL,actual_sha1 TEXT,validation_status TEXT NOT NULL,bytes_read INTEGER NOT NULL DEFAULT 0,checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,error TEXT);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_run ON rom_source_match(dataset_run_id);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_scan_run ON rom_source_match(scan_run_id);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_rom ON rom_source_match(rom_id);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_hash ON rom_source_match(actual_crc,actual_size);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_sha1 ON rom_source_match(actual_sha1);
    """
    def __init__(self, db, source_dirs: Iterable[Path | str], max_workers: int = 4) -> None:
        self.db=db; self.source_dirs=self._normalize_paths(source_dirs); self.max_workers=max(1,int(max_workers or 1)); self._cancel_requested=False; self.last_scan_id=None; self.last_stats={}; self._expected_roms={}; self._expected_disks={}; self._manifest_path=None
    @staticmethod
    def _normalize_paths(paths):
        result=[]; seen=set()
        for value in paths:
            path=Path(value).expanduser(); key=str(path.absolute()).lower()
            if key not in seen: seen.add(key); result.append(path)
        return result
    def cancel(self): """Solicita cancelamento cooperativo."""; self._cancel_requested=True
    @property
    def cancelled(self): """Indica se o scan foi cancelado."""; return self._cancel_requested

    def scan(self,machine_names=None,run_id=None,progress=None,cancelled=None,machine_disks=None,*,manifest_path=None,xml_path=None,xml_machines=None,mame_version="unknown"):
        """Executa o scan e persiste SQLite/JSONL em paralelo às leituras."""
        conn=self._connection(); self._ensure_scan_tables(conn); self._validate_sources(); self._cancel_requested=False
        names=[str(n).strip() for n in (machine_names or []) if str(n).strip()]
        self._expected_roms=self._build_expected_roms(names); self._expected_disks=machine_disks if machine_disks is not None else self._build_expected_disks(names)
        started=time.monotonic(); conn.execute("INSERT INTO rom_scan_run (dataset_run_id,source_count,status) VALUES (?,?,'running')",(run_id,len(self.source_dirs))); scan_id=int(conn.execute("SELECT last_insert_rowid()").fetchone()[0]); self.last_scan_id=scan_id; conn.commit()
        stats=self._new_stats(scan_id,run_id,names); stats["expected_roms"]=sum(len(v) for v in self._expected_roms.values()); stats["expected_chds"]=sum(len(v) for v in self._expected_disks.values())
        self._manifest_path=Path(manifest_path or "data/database/scan/current_scan.jsonl.tmp"); self._manifest_path.parent.mkdir(parents=True,exist_ok=True); manifest=self._open_manifest(self._manifest_path,names,xml_path,mame_version)
        logger.info("Scan esperado iniciado: %d ROMs, %d CHDs, %d machines, %d workers.",stats["expected_roms"],stats["expected_chds"],len(names),self.max_workers)
        if progress: progress(0,f"Preparando scan | {len(names):,} machines | {stats['expected_roms']:,} ROMs | {stats['expected_chds']:,} CHDs")
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers,thread_name_prefix="rom-scan") as executor:
                futures={executor.submit(self._scan_machine,name,scan_id,cancelled):name for name in names}; completed=0
                for future in as_completed(futures):
                    self._check_cancelled(cancelled); machine=futures[future]; unit=future.result(); self._persist_unit(conn,unit); self._update_stats(stats,unit); self._write_unit_manifest(manifest,unit); completed+=1
                    message=self._progress_message(stats,machine,completed,len(names)); logger.info(message)
                    if progress: progress(min(100,completed*100//max(1,len(names))),message)
            stats["seconds"]=round(time.monotonic()-started,2); stats["status"]="completed"; self._finish_run(conn,scan_id,stats); self._finish_manifest(manifest,stats); self.last_stats=stats
            if progress: progress(100,self._summary_message(stats)); logger.info(self._summary_message(stats)); return stats
        except Exception as exc:
            stats["seconds"]=round(time.monotonic()-started,2); stats["status"]="cancelled" if str(exc)=="Operação cancelada." else "failed"; self._finish_run(conn,scan_id,stats,str(exc))
            try: manifest.write(json.dumps({"record_type":"scan_end","status":stats["status"],"error":str(exc)},ensure_ascii=False)+"\n"); manifest.flush(); manifest.close()
            except Exception: logger.exception("Falha finalizando manifesto parcial.")
            self.last_stats=stats
            if stats["status"]=="cancelled": logger.info("Scan físico cancelado pelo usuário."); return stats
            logger.exception("Falha no scan físico."); raise

    def _scan_machine(self,machine_name,scan_id,cancelled):
        """Escaneia ZIP, arquivos soltos e CHDs da própria machine."""
        unit=self._empty_unit(machine_name,scan_id); expected=self._expected_roms.get(machine_name,[])
        for base in self.source_dirs:
            self._check_cancelled(cancelled); zip_path=base/f"{machine_name}.zip"
            if zip_path.is_file(): unit["archives"]+=1; self._scan_expected_zip(zip_path,expected,unit,cancelled)
            machine_dir=base/machine_name
            if machine_dir.is_dir(): self._scan_expected_loose_dir(machine_dir,expected,unit,cancelled)
        for disk in self._expected_disks.get(machine_name,[]):
            self._check_cancelled(cancelled); result=self._scan_expected_chd(machine_name,disk,cancelled); unit["chds"]+=1
            if result["status"]=="present": unit["chds_present"]+=1
            elif result["status"]=="missing": unit["chds_missing"]+=1
            else: unit["chds_errors"]+=1
            unit["chd_results"][str(disk.get("name") or "")]=result
        found={int(row[0]) for row in unit["records"] if row[0] is not None}
        for candidate in expected:
            if candidate["rom_id"] not in found: unit["records"].append((candidate["rom_id"],"",None,"expected",0,"",None,"missing",0,"ROM não encontrada em machine.zip nem na pasta da machine")); unit["missing"]+=1
        return unit

    def _build_expected_roms(self,names):
        result={name:[] for name in names}
        if not names:return result
        p=",".join("?" for _ in names); rows=self.db.fetchall(f"SELECT m.name machine_name,r.id,r.machine_id,r.name,r.size,r.crc,r.sha1,r.merge,r.optional FROM rom r JOIN machine m ON m.id=r.machine_id WHERE m.name IN ({p}) ORDER BY m.name,r.id",names)
        for row in rows: result.setdefault(str(row["machine_name"]),[]).append({"rom_id":int(row["id"]),"machine_id":int(row["machine_id"]),"machine_name":str(row["machine_name"]),"name":str(row["name"] or "").replace("\\","/"),"size":int(row["size"] or 0),"crc":str(row["crc"] or "").strip().lower(),"sha1":str(row["sha1"] or "").strip().lower(),"merge":row["merge"],"optional":bool(row["optional"])})
        return result

    def _build_expected_disks(self,names):
        result={name:[] for name in names}
        if not names:return result
        p=",".join("?" for _ in names); rows=self.db.fetchall(f"SELECT m.name machine_name,d.name,d.sha1,d.merge,d.region,d.disk_index,d.writable,d.optional,d.size FROM disk d JOIN machine m ON m.id=d.machine_id WHERE m.name IN ({p}) ORDER BY m.name,d.disk_index,d.id",names)
        for row in rows: result.setdefault(str(row["machine_name"]),[]).append({"name":str(row["name"] or ""),"sha1":str(row["sha1"] or "").strip().lower(),"merge":row["merge"],"region":row["region"],"index":int(row["disk_index"] or 0),"writable":bool(row["writable"]),"optional":bool(row["optional"]),"size":int(row["size"] or 0)})
        return result

    def _scan_expected_zip(self,path,expected,unit,cancelled):
        try:
            with zipfile.ZipFile(path,"r") as archive:
                infos={i.filename.replace("\\","/"):i for i in archive.infolist() if not i.is_dir()}; basenames={Path(n).name:i for n,i in infos.items()}
                for c in expected:
                    self._check_cancelled(cancelled); info=infos.get(c["name"]) or basenames.get(Path(c["name"]).name)
                    if info is None: continue
                    unit["members"]+=1; size=int(info.file_size); crc=f"{info.CRC&0xFFFFFFFF:08x}"; status="valid" if (size==c["size"] if c["size"]>0 else True) and (crc==c["crc"] if c["crc"] else True) else "invalid"; sha1=None; read=0; error=None
                    if status=="valid" and c["sha1"]:
                        try:
                            with archive.open(info,"r") as stream: actual_size,_actual_crc,sha1=self._hash_stream(stream,cancelled)
                            read=actual_size; unit["bytes_read"]+=actual_size; status="valid" if sha1==c["sha1"] else "sha1_mismatch"
                        except (OSError,EOFError,RuntimeError,zipfile.BadZipFile) as exc: status="read_error"; error=str(exc); unit["read_errors"]+=1
                    if status=="valid":unit["valid"]+=1
                    elif status=="sha1_mismatch":unit["sha1_mismatch"]+=1
                    unit["records"].append((c["rom_id"],str(path),info.filename,"zip",size,crc,sha1,status,read,error))
        except (OSError,zipfile.BadZipFile,RuntimeError) as exc: unit["read_errors"]+=1; unit["errors"].append(f"{path}: {exc}")

    def _scan_expected_loose_dir(self,machine_dir,expected,unit,cancelled):
        for c in expected:
            self._check_cancelled(cancelled); path=machine_dir/Path(c["name"]).name
            if not path.is_file():continue
            try:
                size=path.stat().st_size; crc=self._crc_file(path,cancelled); status="valid" if (size==c["size"] if c["size"]>0 else True) and (crc==c["crc"] if c["crc"] else True) else "invalid"; sha1=None
                if status=="valid" and c["sha1"]: sha1=self._sha1_file(path,cancelled); status="valid" if sha1==c["sha1"] else "sha1_mismatch"
                if status=="valid":unit["valid"]+=1
                elif status=="sha1_mismatch":unit["sha1_mismatch"]+=1
                unit["loose"]+=1; unit["bytes_read"]+=size; unit["records"].append((c["rom_id"],str(path),None,"loose",size,crc,sha1,status,size,None))
            except (OSError,RuntimeError) as exc: unit["read_errors"]+=1; unit["records"].append((c["rom_id"],str(path),None,"loose",0,"",None,"read_error",0,str(exc)))

    def _scan_expected_chd(self,machine_name,disk,cancelled):
        name=str(disk.get("name") or "").strip()
        if not name:return {"status":"error","source_path":None,"error":"CHD sem nome"}
        filename=name if name.lower().endswith(".chd") else f"{name}.chd"
        for base in self.source_dirs:
            self._check_cancelled(cancelled); path=base/machine_name/filename
            if path.is_file():return {"status":"present","source_path":str(path),"error":None}
        return {"status":"missing","source_path":None,"error":"CHD não encontrado na pasta da machine"}

    def _persist_unit(self,conn,unit):
        for row in unit["records"]:self._record(conn,unit["scan_id"],*row)
        conn.commit()
    def _record(self,conn,scan_id,rom_id,source_path,archive_member,source_kind,size,crc,sha1,status,bytes_read,error):
        conn.execute("INSERT INTO rom_source_match (dataset_run_id,scan_run_id,rom_id,source_path,archive_member,source_kind,actual_size,actual_crc,actual_sha1,validation_status,bytes_read,checked_at,error) SELECT dataset_run_id,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,? FROM rom_scan_run WHERE id=?",(scan_id,rom_id,source_path or "",archive_member,source_kind,size,crc,sha1,status,bytes_read,error,scan_id))

    def _open_manifest(self,path,names,xml_path,mame_version):
        handle=path.open("w",encoding="utf-8",newline="\n"); header={"record_type":"header","schema_version":4,"scan_id":f"physical_{self.last_scan_id}","started_at":datetime.now(timezone.utc).isoformat(),"mame_version":mame_version,"xml_path":str(xml_path) if xml_path else "","source_paths":[str(p) for p in self.source_dirs],"machine_count_expected":len(names),"metadata":{"validation":"expected_driven","persist_mode":"streaming"}}; handle.write(json.dumps(header,ensure_ascii=False)+"\n"); handle.flush(); return handle
    def _write_unit_manifest(self,handle,unit):
        machine=unit["machine"]; expected={c["rom_id"]:c for c in self._expected_roms.get(machine,[])}; best={}
        for row in unit["records"]:
            if row[0] is None:continue
            if row[0] not in best or self._status_rank(row[7])<self._status_rank(best[row[0]][7]):best[row[0]]=row
        handle.write(json.dumps({"record_type":"machine","event":"started","machine":{"name":machine}},ensure_ascii=False)+"\n")
        for rid,c in expected.items():
            row=best.get(rid)
            if row:_,source,member,kind,size,crc,sha1,status,_read,error=row
            else:source=member=sha1=error=None;kind,size,crc,status="expected",0,"","missing"
            record={"machine":machine,"rom_name":c["name"],"expected_size":c["size"],"expected_crc":c["crc"],"expected_sha1":c["sha1"] or None,"merge":c["merge"],"required":not c["optional"],"optional":c["optional"],"status":status,"actual_size":size,"actual_crc":crc or None,"actual_sha1":sha1,"source":{"kind":kind,"archive":source,"member":member,"machine":machine} if source else None,"error":error}
            handle.write(json.dumps({"record_type":"rom","record":record},ensure_ascii=False)+"\n")
        for disk_name,disk in unit["chd_results"].items():
            definition=next((d for d in self._expected_disks.get(machine,[]) if str(d.get("name") or "")==disk_name),{}); record={"machine":machine,"disk_name":disk_name,"expected_size":int(definition.get("size") or 0),"expected_sha1":str(definition.get("sha1") or "").lower(),"required":not bool(definition.get("optional")),"optional":bool(definition.get("optional")),"status":disk["status"],"actual_size":0,"actual_sha1":None,"source":{"kind":"chd","archive":disk.get("source_path"),"member":None,"machine":machine} if disk.get("source_path") else None,"error":disk.get("error")}; handle.write(json.dumps({"record_type":"disk","record":record},ensure_ascii=False)+"\n")
        handle.write(json.dumps({"record_type":"machine","event":"finished","machine":{"name":machine,"status":"completed"}},ensure_ascii=False)+"\n");handle.flush()
    @staticmethod
    def _status_rank(status):return {"valid":0,"sha1_mismatch":1,"invalid":2,"read_error":3,"missing":4}.get(status,5)
    def _finish_manifest(self,handle,stats):handle.write(json.dumps({"record_type":"summary","status":stats["status"],"stats":stats},ensure_ascii=False)+"\n");handle.flush();handle.close()
    def write_manifest(self,xml_machines,xml_path,output_path,mame_version,source_paths):
        """Compatibilidade com a GUI: o manifesto já foi produzido em streaming."""
        if output_path.exists():return output_path
        if self._manifest_path and self._manifest_path.exists():return self._manifest_path
        raise RuntimeError("Manifesto de scan não foi criado.")
    def _build_expected_index(self,machine_names=None):
        result={}; selected=set(machine_names or self._expected_roms)
        for machine in selected:
            for row in self._expected_roms.get(machine,[]):result.setdefault((row["crc"],row["size"]),[]).append(row)
        return result
    @staticmethod
    def _new_stats(scan_id,run_id,names):return {"scan_id":scan_id,"dataset_run_id":run_id,"expected_roms":0,"expected_chds":0,"archives":0,"members":0,"loose":0,"chds":0,"chds_present":0,"chds_missing":0,"chds_errors":0,"chds_valid":0,"bytes_read":0,"valid":0,"missing":0,"sha1_mismatch":0,"unmatched":0,"read_errors":0,"seconds":0.0,"status":"running","machines":len(names),"machines_completed":0}
    def _update_stats(self,stats,unit):
        for key in ("archives","members","loose","bytes_read","valid","missing","sha1_mismatch","unmatched","read_errors","chds","chds_present","chds_missing","chds_errors"):stats[key]+=unit.get(key,0)
        stats["chds_valid"]=stats["chds_present"];stats["machines_completed"]+=1
    @staticmethod
    def _progress_message(stats,machine,completed,total):return f"Machine {completed:,}/{total:,}: {machine} | ROMs {stats['members']:,} verificadas | válidas {stats['valid']:,} | ausentes {stats['missing']:,} | CHDs {stats['chds_present']:,}/{stats['chds']:,} presentes | dados lidos {stats['bytes_read']/(1024**3):.2f} GiB"
    @staticmethod
    def _summary_message(stats):return f"Scan concluído: {stats['machines_completed']:,}/{stats['machines']:,} machines | ROMs válidas {stats['valid']:,} | ausentes {stats['missing']:,} | CHDs presentes {stats['chds_present']:,}/{stats['chds']:,} | tempo {stats['seconds']:.2f}s"
    def _finish_run(self,conn,scan_id,stats,error=None):
        conn.execute("UPDATE rom_scan_run SET finished_at=CURRENT_TIMESTAMP,status=?,archive_count=?,member_count=?,loose_file_count=?,bytes_read=?,valid_match_count=?,unmatched_count=?,error=? WHERE id=?",(stats["status"],stats["archives"],stats["members"],stats["loose"],stats["bytes_read"],stats["valid"],stats["unmatched"]+stats["missing"]+stats["sha1_mismatch"]+stats["read_errors"]+stats.get("chds_missing",0)+stats.get("chds_errors",0),error,scan_id));conn.commit()
    def _ensure_scan_tables(self,conn):conn.executescript(self._SCAN_TABLE_SQL);conn.commit()
    def _validate_sources(self):
        if not self.source_dirs:raise RuntimeError("Nenhuma origem física de ROM foi configurada.")
        for path in self.source_dirs:
            if not path.is_dir():raise FileNotFoundError(f"Origem física não encontrada: {path}")
    def _connection(self):
        if self.db.conn is None:self.db.connect()
        assert self.db.conn is not None;return self.db.conn
    def _check_cancelled(self,cancelled):
        if self._cancel_requested or (cancelled and cancelled()):raise RuntimeError("Operação cancelada.")
    def _hash_stream(self,stream,cancelled=None):
        crc=0;digest=hashlib.sha1();size=0
        while True:
            self._check_cancelled(cancelled);chunk=stream.read(self.CHUNK_SIZE)
            if not chunk:break
            size+=len(chunk);crc=zlib.crc32(chunk,crc);digest.update(chunk)
        return size,f"{crc&0xFFFFFFFF:08x}",digest.hexdigest()
    def _crc_file(self,path,cancelled=None):
        crc=0
        with path.open("rb") as stream:
            while True:
                self._check_cancelled(cancelled);chunk=stream.read(self.CHUNK_SIZE)
                if not chunk:break
                crc=zlib.crc32(chunk,crc)
        return f"{crc&0xFFFFFFFF:08x}"
    def _sha1_file(self,path,cancelled=None):
        digest=hashlib.sha1()
        with path.open("rb") as stream:
            while True:
                self._check_cancelled(cancelled);chunk=stream.read(self.CHUNK_SIZE)
                if not chunk:break
                digest.update(chunk)
        return digest.hexdigest()
    @staticmethod
    def _empty_unit(machine,scan_id):return {"machine":machine,"scan_id":scan_id,"archives":0,"members":0,"loose":0,"bytes_read":0,"valid":0,"missing":0,"sha1_mismatch":0,"unmatched":0,"read_errors":0,"chds":0,"chds_present":0,"chds_missing":0,"chds_errors":0,"records":[],"errors":[],"chd_results":{}}
