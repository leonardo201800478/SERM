"""
Auditor – gera relatório sobre o estado dos arquivos no FULLSET.
"""

import logging
from typing import List, Dict, Optional
from ..domain.manifest import FileRequirement, FileType
from ..archives.scanner import FullsetScanner

logger = logging.getLogger(__name__)

class Auditor:
    def __init__(self, scanner: FullsetScanner):
        self.scanner = scanner

    def audit_manifest(self, manifest) -> Dict[str, List[Dict]]:
        """
        Verifica a presença de cada arquivo do manifesto no FULLSET.
        Retorna um dicionário com listas por status.
        """
        result = {
            "present": [],
            "missing": [],
            "partial": [],  # se houver checksums errados
        }

        for req in manifest.required_files:
            status = self.scanner.get_file_status(req)
            if status == "present":
                result["present"].append({"file": req.file_name, "source": req.source_machine})
            elif status == "missing":
                result["missing"].append({"file": req.file_name, "source": req.source_machine})
            else:
                result["partial"].append({"file": req.file_name, "status": status, "source": req.source_machine})

        logger.info(f"Auditoria: {len(result['present'])} presentes, {len(result['missing'])} faltando.")
        return result