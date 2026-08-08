"""
Scanner do FULLSET – indexa arquivos (ZIP, 7Z, CHD) e seus membros.
"""

import os
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
import zipfile
import py7zr
from ..domain.manifest import FileRequirement

logger = logging.getLogger(__name__)

@dataclass
class ArchiveInfo:
    """Informações sobre um arquivo de archive (ZIP/7Z/CHD)."""
    path: str
    format: str          # "zip", "7z", "chd"
    size: int
    modified: float
    members: Dict[str, Dict] = field(default_factory=dict)  # nome do membro -> metadados

class FullsetScanner:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._create_tables()

    def _create_tables(self):
        """Cria tabelas para indexação do FULLSET, se não existirem."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                format TEXT NOT NULL,
                size INTEGER,
                modified_at REAL,
                scan_status TEXT   -- "ok", "error", "partial"
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS archive_member (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                archive_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                size INTEGER,
                crc TEXT,
                sha1 TEXT,
                member_path TEXT,
                FOREIGN KEY(archive_id) REFERENCES archive(id)
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_archive_path ON archive(path)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_member_name ON archive_member(name)
        """)
        self.conn.commit()

    def scan_directory(self, fullset_path: Path, max_files: int = 0) -> int:
        """
        Escaneia o diretório FULLSET em busca de arquivos de ROM/CHD/sample.
        Retorna o número de arquivos processados.
        """
        if not fullset_path.is_dir():
            raise ValueError(f"Caminho do FULLSET não é um diretório: {fullset_path}")

        count = 0
        # Extensões suportadas (MAYUS/MINÚSC)
        extensions = {'.zip', '.7z', '.chd', '.bin', '.cue'}
        for root, dirs, files in os.walk(fullset_path):
            for file in files:
                ext = Path(file).suffix.lower()
                if ext not in extensions:
                    continue
                file_path = Path(root) / file
                try:
                    self._scan_file(file_path)
                    count += 1
                    if max_files and count >= max_files:
                        logger.info(f"Limite de {max_files} arquivos atingido.")
                        return count
                except Exception as e:
                    logger.error(f"Erro ao escanear {file_path}: {e}")
        self.conn.commit()
        logger.info(f"Escaneamento concluído: {count} arquivos processados.")
        return count

    def _scan_file(self, file_path: Path):
        """Escaneia um único arquivo, determinando seu formato e indexando membros."""
        ext = file_path.suffix.lower()
        if ext == '.zip':
            self._scan_zip(file_path)
        elif ext == '.7z':
            self._scan_7z(file_path)
        elif ext == '.chd' or ext == '.bin' or ext == '.cue':
            self._scan_chd_or_raw(file_path)
        else:
            logger.warning(f"Formato não suportado: {file_path}")

    def _scan_zip(self, file_path: Path):
        """Escaneia um arquivo ZIP e indexa seus membros."""
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                members = []
                for info in zf.infolist():
                    members.append({
                        'name': info.filename,
                        'size': info.file_size,
                        'crc': f"{info.CRC:x}" if info.CRC else None,
                        # SHA1 não está disponível diretamente no zipfile
                    })
                self._save_archive(file_path, 'zip', members)
        except zipfile.BadZipFile:
            logger.warning(f"Arquivo ZIP corrompido: {file_path}")
            self._save_archive(file_path, 'zip', [], status='error')

    def _scan_7z(self, file_path: Path):
        """Escaneia um arquivo 7Z e indexa seus membros."""
        try:
            with py7zr.SevenZipFile(file_path, 'r') as szf:
                files = szf.getnames()
                members = []
                for name in files:
                    # Obter informações adicionais se possível
                    members.append({'name': name, 'size': 0, 'crc': None})
                self._save_archive(file_path, '7z', members)
        except Exception as e:
            logger.warning(f"Erro ao ler 7Z {file_path}: {e}")
            self._save_archive(file_path, '7z', [], status='error')

    def _scan_chd_or_raw(self, file_path: Path):
        """Para CHD/BIN/CUE, não há membros internos; o arquivo em si é o membro."""
        # Neste caso, consideramos o arquivo como um "membro" único
        members = [{
            'name': file_path.name,
            'size': file_path.stat().st_size,
            'crc': None,
            'sha1': None
        }]
        self._save_archive(file_path, file_path.suffix[1:], members)

    def _save_archive(self, file_path: Path, format: str, members: List[Dict], status: str = 'ok'):
        """Salva informações do archive e seus membros no banco de dados."""
        cursor = self.conn.execute(
            "SELECT id FROM archive WHERE path = ?", (str(file_path),)
        )
        row = cursor.fetchone()
        if row:
            archive_id = row['id']
            self.conn.execute(
                "UPDATE archive SET format=?, size=?, modified_at=?, scan_status=? WHERE id=?",
                (format, file_path.stat().st_size, file_path.stat().st_mtime, status, archive_id)
            )
            # Remove membros antigos
            self.conn.execute("DELETE FROM archive_member WHERE archive_id = ?", (archive_id,))
        else:
            cursor = self.conn.execute(
                "INSERT INTO archive (path, format, size, modified_at, scan_status) VALUES (?, ?, ?, ?, ?)",
                (str(file_path), format, file_path.stat().st_size, file_path.stat().st_mtime, status)
            )
            archive_id = cursor.lastrowid

        # Insere membros
        for member in members:
            self.conn.execute(
                """INSERT INTO archive_member
                (archive_id, name, size, crc, sha1, member_path)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (archive_id, member['name'], member.get('size'), member.get('crc'),
                 member.get('sha1'), member.get('member_path'))
            )

    def find_file(self, file_name: str) -> Optional[Dict[str, Any]]:
        """
        Busca por um arquivo no índice.
        Retorna o caminho do archive e o membro se encontrado.
        """
        cursor = self.conn.execute("""
            SELECT a.path, a.format, am.name, am.size, am.crc, am.sha1
            FROM archive_member am
            JOIN archive a ON am.archive_id = a.id
            WHERE am.name = ?
            LIMIT 1
        """, (file_name,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_file_status(self, requirement: FileRequirement) -> str:
        """
        Verifica o status de um FileRequirement no FULLSET.
        Retorna: "present", "missing", "wrong_size", "wrong_crc", etc.
        """
        # Mapeia o nome do arquivo (ex.: "pacman.6e") para um membro no índice
        found = self.find_file(requirement.file_name)
        if not found:
            return "missing"
        # Verifica CRC se disponível
        if requirement.crc and found.get('crc'):
            if requirement.crc.lower() != found['crc'].lower():
                return "wrong_crc"
        # Verifica tamanho se disponível
        if requirement.size and found.get('size'):
            if requirement.size != found['size']:
                return "wrong_size"
        return "present"