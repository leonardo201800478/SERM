"""
Lógica de cópia de arquivos do FULLSET para o diretório de destino.
"""

import shutil
import os
import logging
from pathlib import Path
from typing import Dict, Optional, List
from ..archives.scanner import FullsetScanner

logger = logging.getLogger(__name__)

class Copier:
    def __init__(self, scanner: FullsetScanner):
        self.scanner = scanner

    def copy_file(self, file_name: str, source_root: Path, dest_root: Path) -> bool:
        """
        Copia um arquivo (ou membro de archive) do FULLSET para o destino.
        Retorna True se bem-sucedido, False caso contrário.
        """
        # Busca o arquivo no índice
        found = self.scanner.find_file(file_name)
        if not found:
            logger.warning(f"Arquivo não encontrado no FULLSET: {file_name}")
            return False

        source_archive = Path(found['path'])
        member_name = found['name']
        dest_path = dest_root / member_name

        # Se o arquivo já existe no destino, pula (ou sobrescreve? Vamos manter imutável)
        if dest_path.exists():
            logger.debug(f"Arquivo já existe no destino: {dest_path}")
            return True

        # Determina o tipo de archive
        ext = source_archive.suffix.lower()
        if ext == '.zip' or ext == '.7z':
            # Extrair membro específico e copiar
            return self._extract_member(source_archive, member_name, dest_path)
        else:
            # Arquivo único (CHD, BIN, etc.) – copiar diretamente
            try:
                shutil.copy2(source_archive, dest_path)
                logger.info(f"Copiado: {source_archive} -> {dest_path}")
                return True
            except Exception as e:
                logger.error(f"Erro ao copiar {source_archive}: {e}")
                return False

    def _extract_member(self, archive_path: Path, member_name: str, dest_path: Path) -> bool:
        """Extrai um membro específico de um ZIP ou 7Z para o destino."""
        try:
            # Cria o diretório pai se não existir
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            ext = archive_path.suffix.lower()
            if ext == '.zip':
                import zipfile
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    zf.extract(member_name, path=dest_path.parent)
                    # Renomeia se necessário (o extract pode criar subpastas)
                    extracted = dest_path.parent / member_name
                    if extracted != dest_path:
                        extracted.rename(dest_path)
                logger.info(f"Extraído {member_name} de {archive_path} -> {dest_path}")
                return True
            elif ext == '.7z':
                import py7zr
                with py7zr.SevenZipFile(archive_path, 'r') as szf:
                    szf.extract(path=dest_path.parent, targets=[member_name])
                    extracted = dest_path.parent / member_name
                    if extracted != dest_path:
                        extracted.rename(dest_path)
                logger.info(f"Extraído {member_name} de {archive_path} -> {dest_path}")
                return True
            else:
                logger.warning(f"Formato não suportado para extração: {archive_path}")
                return False
        except Exception as e:
            logger.error(f"Erro ao extrair {member_name} de {archive_path}: {e}")
            return False