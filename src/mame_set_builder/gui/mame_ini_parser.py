"""
Leitor/escritor para mame.ini – formato chave-valor separado por espaços.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
import chardet

logger = logging.getLogger(__name__)

class MameIniParser:
    @staticmethod
    def detect_encoding(file_path: Path) -> str:
        try:
            with open(file_path, 'rb') as f:
                raw = f.read()
            result = chardet.detect(raw)
            encoding = result['encoding'] or 'utf-8'
            logger.info(f"🔍 Codificação detectada: {encoding} (confiança: {result.get('confidence', 0):.2f})")
            return encoding
        except Exception as e:
            logger.error(f"❌ Erro ao detectar codificação: {e}")
            return 'utf-8'

    @staticmethod
    def parse(file_path: Path) -> Dict[str, str]:
        config = {}
        logger.info(f"📂 Tentando ler arquivo: {file_path}")

        if not file_path.exists():
            logger.error(f"❌ Arquivo não encontrado: {file_path}")
            return config

        file_size = file_path.stat().st_size
        logger.info(f"📊 Tamanho do arquivo: {file_size} bytes")
        if file_size == 0:
            logger.warning("⚠️ Arquivo vazio!")
            return config

        encoding = MameIniParser.detect_encoding(file_path)
        logger.info(f"📝 Usando codificação: {encoding}")

        try:
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                lines = f.readlines()
            logger.info(f"✅ Leitura bem-sucedida com {encoding}: {len(lines)} linhas")
        except UnicodeDecodeError as e:
            logger.warning(f"⚠️ Erro com {encoding}, tentando fallback utf-8-sig...")
            try:
                with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                    lines = f.readlines()
                logger.info(f"✅ Leitura com fallback utf-8-sig: {len(lines)} linhas")
            except Exception as e2:
                logger.error(f"❌ Falha na leitura: {e2}")
                return config

        # Mostra primeiras 10 linhas
        logger.info("📄 Primeiras 10 linhas do arquivo:")
        for i, line in enumerate(lines[:10]):
            logger.info(f"   Linha {i+1}: {repr(line)}")

        line_count = 0
        comment_count = 0
        empty_count = 0
        parsed_count = 0

        for line_num, line in enumerate(lines, 1):
            original_line = line
            # Remove espaços no início e fim
            line = line.strip()
            if not line:
                empty_count += 1
                continue
            # Ignora comentários
            if line.startswith('#') or line.startswith(';'):
                comment_count += 1
                continue
            # Ignora seções (não existem no mame.ini, mas por precaução)
            if line.startswith('[') and line.endswith(']'):
                continue

            # Formato: chave espaços valor
            # Divide por espaços em branco (qualquer quantidade)
            parts = re.split(r'\s+', line, maxsplit=1)
            if len(parts) < 2:
                logger.debug(f"⚠️ Linha sem par chave-valor: {repr(original_line)}")
                continue

            key = parts[0].strip()
            value = parts[1].strip() if len(parts) > 1 else ""

            # Remove aspas externas
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]

            config[key] = value
            parsed_count += 1
            logger.debug(f"✅ {key} = {value}")

        logger.info(f"📊 Resumo do parsing:")
        logger.info(f"   Total de linhas: {len(lines)}")
        logger.info(f"   Linhas vazias: {empty_count}")
        logger.info(f"   Comentários: {comment_count}")
        logger.info(f"   Configurações parseadas: {parsed_count}")

        if parsed_count == 0:
            logger.warning("⚠️ Nenhuma configuração foi parseada! Verifique o formato do arquivo.")
            # Fallback: tentar ler caractere por caractere separando por espaços
            try:
                with open(file_path, 'r', encoding='windows-1252', errors='ignore') as f:
                    fallback_lines = f.readlines()
                for line in fallback_lines:
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith(';'):
                        continue
                    parts = re.split(r'\s+', line, maxsplit=1)
                    if len(parts) >= 2:
                        key = parts[0].strip()
                        value = parts[1].strip().strip('"')
                        config[key] = value
                logger.info(f"✅ Fallback parseou {len(config)} configurações")
            except Exception as e:
                logger.error(f"❌ Fallback falhou: {e}")

        return config

    @staticmethod
    def find_ini(exe_path: Optional[Path]) -> Path:
        if not exe_path or not exe_path.exists():
            logger.warning(f"⚠️ Executável inválido: {exe_path}")
            return Path()
        parent = exe_path.parent
        logger.info(f"🔍 Procurando mame.ini em: {parent}")
        ini = parent / "mame.ini"
        if ini.exists():
            logger.info(f"✅ Encontrado em: {ini}")
            return ini
        ini = parent / "ini" / "mame.ini"
        if ini.exists():
            logger.info(f"✅ Encontrado em: {ini}")
            return ini
        ini = parent.parent / "mame.ini"
        if ini.exists():
            logger.info(f"✅ Encontrado em: {ini}")
            return ini
        logger.warning(f"❌ mame.ini não encontrado a partir de {exe_path}")
        return Path()

    @staticmethod
    def save(file_path: Path, config: Dict[str, str], original_content: Optional[List[str]] = None) -> None:
        if original_content is None:
            with open(file_path, 'w', encoding='utf-8') as f:
                for key, value in config.items():
                    # Alinha com 20 espaços para ficar bonito
                    f.write(f"{key:<20}{value}\n")
            return

        updated_lines = []
        keys_updated = set()
        for line in original_content:
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or stripped.startswith(';') or stripped.startswith('['):
                updated_lines.append(line)
                continue
            parts = re.split(r'\s+', stripped, maxsplit=1)
            if len(parts) >= 1:
                key = parts[0]
                if key in config:
                    new_value = config[key]
                    # Mantém espaçamento original? Simples: alinha com 20
                    updated_lines.append(f"{key:<20}{new_value}\n")
                    keys_updated.add(key)
                    continue
            updated_lines.append(line)

        for key, value in config.items():
            if key not in keys_updated:
                updated_lines.append(f"{key:<20}{value}\n")

        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)