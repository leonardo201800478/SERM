"""Scanner físico orientado a conteúdo para ROMs MAME.

O scanner percorre arquivos físicos, abre cada ZIP uma única vez e lê cada
membro esperado em streaming. A decisão de validade usa tamanho + CRC32 e,
quando disponível, SHA1 do conteúdo descompactado. O CRC armazenado no
cabeçalho do ZIP nunca é usado sozinho como prova de integridade.
"""
from __future__ import annotations
import hashlib
import time
import zlib
import zipfile
from pathlib import Path
from typing import Callable

class PhysicalRomScanner:
    """Indexa ROMs físicas sem modificar a origem."""
    CHUNK=1024*1024
    def __init__(self,db,source_dirs):self.db=db;self.source_dirs=[Path(p) for p in source_dirs]

    def scan(self,run_id:int,progress:Callable[[int,str],None]|None=None,cancelled:Callable[[],bool]|None=None)->dict:
        """Percorre ZIPs e arquivos soltos e grava matches físicos."""
        conn=self.db.conn;assert conn is not None
        expected=self._expected_index()
        started=time.time();archives=members=loose=bytes_read=valid=unmatched=0
        conn.execute("INSERT INTO rom_scan_run(dataset_run_id,source_count,status) VALUES(?,?, 'running')",(run_id,len(self.source_dirs)))
        scan_id=conn.execute("SELECT last_insert_rowid()").fetchone()[0];conn.commit()
        try:
            for root in self.source_dirs:
                if not root.is_dir():continue
                for path in root.rglob("*"):
                    if cancelled and cancelled():raise RuntimeError("Operação cancelada.")
                    if path.is_file() and path.suffix.lower()==".zip":
                        a_count,m_count,b_count,v_count,u_count=self._scan_zip(path,expected,scan_id,cancelled)
                        archives+=a_count;members+=m_count;bytes_read+=b_count;valid+=v_count;unmatched+=u_count
                    elif path.is_file() and path.suffix.lower() not in {".chd",".zip"}:
                        b,v,u=self._scan_loose(path,expected,scan_id);loose+=1;bytes_read+=b;valid+=v;unmatched+=u
                    if progress and (members+loose)%100==0:
                        progress(members+loose,f"Scan físico: {members} membros ZIP, {loose} arquivos soltos, {bytes_read:,} bytes lidos")
            conn.execute("UPDATE rom_scan_run SET finished_at=CURRENT_TIMESTAMP,status='completed',archive_count=?,member_count=?,loose_file_count=?,bytes_read=?,valid_match_count=?,unmatched_count=? WHERE id=?",(archives,members,loose,bytes_read,valid,unmatched,scan_id));conn.commit()
            return {"scan_id":scan_id,"archives":archives,"members":members,"loose":loose,"bytes_read":bytes_read,"valid":valid,"unmatched":unmatched,"seconds":round(time.time()-started,2)}
        except Exception as exc:
            conn.execute("UPDATE rom_scan_run SET finished_at=CURRENT_TIMESTAMP,status='failed',error=? WHERE id=?",(str(exc),scan_id));conn.commit();raise

    def _expected_index(self):
        """Cria índice CRC+size -> ROMs e SHA1 para desempate."""
        index={}
        rows=self.db.fetchall("SELECT id,name,size,crc,sha1 FROM rom WHERE crc IS NOT NULL AND crc<>''")
        for row in rows:index.setdefault((row[3].lower(),int(row[2] or 0)),[]).append((row[0],row[4].lower() if row[4] else ""))
        return index

    def _scan_zip(self,path,expected,scan_id,cancelled):
        """Abre um ZIP uma vez e valida cada membro por conteúdo."""
        members=bytes_read=valid=unmatched=0
        with zipfile.ZipFile(path,"r") as zf:
            for info in zf.infolist():
                if info.is_dir():continue
                if cancelled and cancelled():raise RuntimeError("Operação cancelada.")
                size,crc,sha=self._hash_stream(zf.open(info,"r"));members+=1;bytes_read+=size
                matches=expected.get((crc,size),[])
                if matches and any(not wanted or wanted==sha for _,wanted in matches):
                    for rom_id,wanted in matches:
                        if not wanted or wanted==sha:
                            self._record(scan_id,rom_id,path,info.filename,"zip",size,crc,sha,"valid",size,None)
                            valid+=1
                else:
                    self._record(scan_id,None,path,info.filename,"zip",size,crc,sha,"unmatched",size,None);unmatched+=1
        return 1,members,bytes_read,valid,unmatched

    def _scan_loose(self,path,expected,scan_id):
        """Valida um arquivo solto pelo conteúdo."""
        size,crc,sha=self._hash_file(path);matches=expected.get((crc,size),[]);valid=0
        if matches:
            for rom_id,wanted in matches:
                if not wanted or wanted==sha:self._record(scan_id,rom_id,path,None,"loose",size,crc,sha,"valid",size,None);valid+=1
        else:self._record(scan_id,None,path,None,"loose",size,crc,sha,"unmatched",size,None)
        return size,valid,0 if matches else 1

    def _hash_file(self,path):
        """Calcula tamanho, CRC32 e SHA1 em streaming."""
        with path.open("rb") as f:return self._hash_stream(f)

    def _hash_stream(self,stream):
        """Calcula hashes sem carregar a ROM inteira em RAM."""
        crc=0;sha=hashlib.sha1();size=0
        while chunk:=stream.read(self.CHUNK):
            size+=len(chunk);crc=zlib.crc32(chunk,crc);sha.update(chunk)
        return size,f"{crc & 0xffffffff:08x}",sha.hexdigest()

    def _record(self,scan_id,rom_id,path,member,kind,size,crc,sha,status,bytes_read,error):
        """Persiste evidência física da validação."""
        self.db.execute("INSERT INTO rom_source_match(dataset_run_id,rom_id,source_path,archive_member,source_kind,actual_size,actual_crc,actual_sha1,validation_status,bytes_read,checked_at,error) VALUES((SELECT dataset_run_id FROM rom_scan_run WHERE id=?),?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,?)",(scan_id,rom_id,str(path),member,kind,size,crc,sha,status,bytes_read,error))
