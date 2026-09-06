"""Camada estável do scanner MAME: retomada e heartbeat."""
from __future__ import annotations
import hashlib,json,sqlite3,time,zlib
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from ..runtime.paths import database_path,scans_root
from .mame_scan_settings_service import MameScanSettingsService
from .rom_scan_service import RomScanService,ScanResult,ScanEvidence,_MachineResult
_ORIGINAL_SCAN=RomScanService.scan
class StableRomScanService(RomScanService):
    HEARTBEAT_SECONDS=5.0
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self._heartbeat_at=0.0; self._heartbeat_machine=""; self._heartbeat_rom=""
    def _heartbeat(self,message):
        now=time.monotonic()
        if now-self._heartbeat_at>=self.HEARTBEAT_SECONDS:self._heartbeat_at=now;self._log("INFO",message)
    def _hash_stream(self,stream):
        crc=0;digest=hashlib.sha1();total=0
        while True:
            if self._cancelled:raise RuntimeError("Operação cancelada.")
            chunk=stream.read(self.CHUNK_SIZE)
            if not chunk:break
            total+=len(chunk);crc=zlib.crc32(chunk,crc);digest.update(chunk);self._heartbeat(f"SCAN | processando | machine={self._heartbeat_machine} | ROM={self._heartbeat_rom or '-'} | SHA1={total/1024/1024:.1f} MiB")
        return total,f"{crc&0xFFFFFFFF:08x}",digest.hexdigest()
    def _crc32(self,path):
        crc=0
        with Path(path).open("rb") as stream:
            while True:
                if self._cancelled:raise RuntimeError("Operação cancelada.")
                chunk=stream.read(self.CHUNK_SIZE)
                if not chunk:break
                crc=zlib.crc32(chunk,crc)
        return f"{crc&0xFFFFFFFF:08x}"
    def _sha1(self,path):
        with Path(path).open("rb") as stream:return self._hash_stream(stream)[2]
    def scan(self,profile,*,catalog_items=(),database=None):
        if str(profile.source).casefold()!="mame":return _ORIGINAL_SCAN(self,profile,catalog_items=catalog_items,database=database)
        return self._scan_mame_resumable(profile,database or database_path(),True)
    def scan_new(self,profile,*,database=None):
        if str(profile.source).casefold()!="mame":return _ORIGINAL_SCAN(self,profile,catalog_items=(),database=database)
        return self._scan_mame_resumable(profile,database or database_path(),False)
    def _scan_machine_with_heartbeat(self,machine,*args,**kwargs):
        self._heartbeat_machine=machine;self._heartbeat_rom="";return super()._scan_machine(machine,*args,**kwargs)
    def _machine_error(self,machine,exc):
        return _MachineResult(machine=machine,records=[ScanEvidence(machine_name=machine,rom_name="",status="ERROR",message="Falha inesperada durante a machine; será reprocessada na retomada",error=f"{type(exc).__name__}: {exc}")],errors=1)
    def _scan_mame_resumable(self,profile,db_path,resume=True):
        with sqlite3.connect(db_path) as c:
            latest=c.execute("SELECT id,source_hash,mame_build FROM mame_listxml_import ORDER BY imported_at DESC,id DESC LIMIT 1").fetchone()
            if latest is None:raise RuntimeError("Nenhum ListXML MAME importado.")
            import_id,source_hash,build=latest;scan_type=MameScanSettingsService.load(str(profile.profile_id))
            if scan_type=="software":raise RuntimeError("Tipo Software ainda não possui catálogo normalizado no V2.")
            machines=[str(r[0]) for r in c.execute("SELECT name FROM mame_machine WHERE import_id=? ORDER BY name",(import_id,))]
            columns={str(r[1]) for r in c.execute("PRAGMA table_info(mame_classification)")}
        result=ScanResult(scan_id=self._make_scan_id(profile),profile_id=str(profile.profile_id),source=str(profile.source),system=str(profile.system),started_at=time.time(),scan_type=scan_type,catalog_hash=str(source_hash),catalog_label=str(build or source_hash[:12]))
        sources=[Path(p).expanduser().resolve() for p in profile.source_directories]
        path,completed=self._find_resume_stream(result,profile,sources,machines,db_path) if resume else self._create_new_stream(result,profile,sources,machines)
        result.evidence_stream_path=str(path);pending=[m for m in machines if m not in completed]
        self._log("INFO",f"SCAN | MAME | modo={'retomada' if resume else 'novo'} | concluídas={len(completed):,}/{len(machines):,} | pendentes={len(pending):,}")
        workers=min(self.DEFAULT_WORKERS,max(1,len(pending)))
        with path.open("a",encoding="utf-8",newline="\n") as stream,ThreadPoolExecutor(max_workers=workers,thread_name_prefix="mame-scan") as executor:
            futures={executor.submit(self._scan_machine_with_heartbeat,m,db_path,int(import_id),sources,columns):m for m in pending};done=len(completed)
            for future in as_completed(futures):
                machine=futures[future]
                try:unit=future.result()
                except Exception as exc:unit=self._machine_error(machine,exc);self._log("ERROR",f"SCAN | machine={machine} | falha isolada: {type(exc).__name__}: {exc} | continuará")
                self._write_machine(stream,unit);stream.flush();done+=1;self._merge_unit_stats(result,unit)
                if self.progress_callback:self.progress_callback(done,len(machines))
                self._log("INFO",self._progress_message(result,machine,done,len(machines)))
            if not self._cancelled:self._write_jsonl(stream,{"record_type":"scan_end","status":"completed","finished_at":time.time(),"status_counts":dict(result.status_counts),"files_examined":result.files_examined,"archives_examined":result.archives_examined,"items_examined":result.items_examined,"errors":result.errors});stream.flush()
        result.finished_at=time.time();self._log_summary(result);return result
    def _create_new_stream(self,result,profile,sources,machines):
        root=scans_root()/"streaming";root.mkdir(parents=True,exist_ok=True);path=root/f"{result.scan_id}.jsonl";wanted=[str(p) for p in sources]
        with path.open("w",encoding="utf-8",newline="\n") as s:self._write_jsonl(s,{"record_type":"header","format":"SERM-SCAN-V2","scan_id":result.scan_id,"profile_id":result.profile_id,"source":result.source,"system":result.system,"scan_type":result.scan_type,"catalog_label":result.catalog_label,"catalog_hash":result.catalog_hash,"started_at":result.started_at,"source_paths":wanted,"machine_count_expected":len(machines),"metadata":{"validation":"expected_driven","persist_mode":"streaming","filters_applied":False,"resumable":True}})
        return path,set()
    def _find_resume_stream(self,result,profile,sources,machines,db_path):
        root=scans_root()/"streaming";root.mkdir(parents=True,exist_ok=True);wanted=[str(p) for p in sources]
        for path in sorted(root.glob("scan_*.jsonl"),key=lambda p:p.stat().st_mtime,reverse=True):
            try:
                with path.open("r",encoding="utf-8") as s:header=json.loads(s.readline())
            except (OSError,ValueError,UnicodeDecodeError):continue
            if header.get("record_type")!="header":continue
            if str(header.get("profile_id"))!=str(profile.profile_id) or str(header.get("source")).casefold()!=str(profile.source).casefold() or str(header.get("system"))!=str(profile.system):continue
            if str(header.get("scan_type"))!=str(result.scan_type) or str(header.get("catalog_hash"))!=str(result.catalog_hash) or str(header.get("catalog_label"))!=str(result.catalog_label) or header.get("source_paths")!=wanted:continue
            completed=self._completed_machines(path,machines,db_path);result.scan_id=str(header.get("scan_id") or result.scan_id);return path,completed
        return self._create_new_stream(result,profile,sources,machines)
    @staticmethod
    def _completed_machines(path,machines,db_path):
        valid=set(machines)
        if not valid:return set()
        ph=",".join("?" for _ in machines)
        with sqlite3.connect(db_path) as c:expected={str(n):int(k) for n,k in c.execute(f"SELECT m.name,COUNT(r.id) FROM mame_machine m LEFT JOIN mame_rom r ON r.machine_id=m.id WHERE m.name IN ({ph}) GROUP BY m.name",tuple(machines))}
        completed=set();current=None;count=0
        try:
            with path.open("r",encoding="utf-8") as s:
                next(s,None)
                for raw in s:
                    try:r=json.loads(raw)
                    except ValueError:break
                    if r.get("record_type")=="machine":
                        if current in valid and count>=expected.get(current,0):completed.add(current)
                        current=str(r.get("machine") or "");count=0
                    elif r.get("record_type")=="evidence" and current and r.get("machine_name")==current and r.get("rom_name"):count+=1
            if current in valid and count>=expected.get(current,0):completed.add(current)
        except OSError:return set()
        return completed
    @staticmethod
    def _last_completed(completed,ordered):
        for name in reversed(ordered):
            if name in completed:return name
        return None
_base_scan=RomScanService
_base_scan.scan=StableRomScanService.scan
_base_scan._hash_stream=StableRomScanService._hash_stream
_base_scan._crc32=StableRomScanService._crc32
_base_scan._sha1=StableRomScanService._sha1
_base_scan.scan_new=StableRomScanService.scan_new
__all__=["StableRomScanService"]
