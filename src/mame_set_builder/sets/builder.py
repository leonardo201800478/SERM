"""
Construtor de sets – orquestra a cópia de arquivos para o destino.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from ..domain.manifest import SetManifest, FileRequirement, FileType
from ..archives.scanner import FullsetScanner
from .copier import Copier
from .auditor import Auditor

logger = logging.getLogger(__name__)

class SetBuilder:
    def __init__(self, scanner: FullsetScanner):
        self.scanner = scanner
        self.copier = Copier(scanner)
        self.auditor = Auditor(scanner)

    def build(self, manifest: SetManifest, source_root: Optional[Path] = None,
              dest_root: Optional[Path] = None) -> Dict[str, Any]:
        """
        Constrói o set a partir do manifesto.
        Retorna relatório com status de cada arquivo.
        """
        if not manifest.required_files:
            logger.warning("Manifesto vazio: nenhum arquivo a copiar.")
            return {"total": 0, "copied": 0, "missing": 0, "failed": 0}

        # Define raízes
        source = source_root or Path(manifest.source_path) if manifest.source_path else None
        dest = dest_root or Path(manifest.destination_path) if manifest.destination_path else None

        if not source or not source.is_dir():
            raise ValueError(f"Diretório de origem inválido: {source}")
        if not dest:
            raise ValueError("Diretório de destino não definido")

        dest.mkdir(parents=True, exist_ok=True)

        report = {
            "total": len(manifest.required_files),
            "copied": 0,
            "missing": 0,
            "failed": 0,
            "details": []
        }

        # Agrupa arquivos por tipo (para organizar pastas)
        # ROMs e BIOS vão para roms/, samples para samples/, etc.
        for req in manifest.required_files:
            # Determina subpasta de destino
            subdir = self._get_dest_subdir(req.file_type)
            dest_subpath = dest / subdir
            dest_subpath.mkdir(parents=True, exist_ok=True)

            # Nome do arquivo destino
            dest_file = dest_subpath / req.file_name

            # Verifica se o arquivo existe no FULLSET
            found = self.scanner.find_file(req.file_name)
            if not found:
                # Verifica se é uma BIOS/device que pode estar com o nome da máquina
                if req.file_type in (FileType.BIOS, FileType.DEVICE):
                    # Tenta buscar pelo nome da máquina (ex.: "neogeo.zip")
                    alt_found = self.scanner.find_file(req.source_machine)
                    if alt_found:
                        found = alt_found
                        req.file_name = req.source_machine  # atualiza para o nome do archive
                        dest_file = dest_subpath / req.source_machine

            if found:
                # Copia o arquivo
                success = self.copier.copy_file(req.file_name, source, dest_subpath)
                if success:
                    report["copied"] += 1
                    report["details"].append({"file": req.file_name, "status": "copied"})
                else:
                    report["failed"] += 1
                    report["details"].append({"file": req.file_name, "status": "failed"})
            else:
                report["missing"] += 1
                report["details"].append({"file": req.file_name, "status": "missing"})

        logger.info(f"Construção concluída: {report['copied']} copiados, {report['missing']} faltando, {report['failed']} falhas.")
        return report

    def _get_dest_subdir(self, file_type: FileType) -> str:
        """Mapeia tipo de arquivo para subdiretório de destino."""
        mapping = {
            FileType.ROM: "roms",
            FileType.BIOS: "roms",
            FileType.DEVICE: "roms",
            FileType.DISK: "roms",      # CHDs geralmente ficam em roms/
            FileType.SAMPLE: "samples",
        }
        return mapping.get(file_type, "roms")