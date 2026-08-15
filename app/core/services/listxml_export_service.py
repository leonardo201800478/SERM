from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, List, Optional

from app.config.app_config import AppConfig
from app.core.database import Database
from app.core.models.filter_profile import FilterCriteria
from app.core.services.filter_service import FilterService


class ListxmlExportService:
    """Exporta subconjuntos sem reduzir o conteúdo estrutural do listxml."""

    def __init__(self, db_path: Path, mame_exe: Optional[Path] = None):
        self.db_path = Path(db_path)
        self.mame_exe = mame_exe or AppConfig().mame_path

    def generate_filtered_xml(self, machine_ids: List[str], output_path: Path, source_xml: Path | None = None) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if source_xml is None:
            if not self.mame_exe or not Path(self.mame_exe).exists():
                raise FileNotFoundError(f"MAME não encontrado: {self.mame_exe}")
            with tempfile.NamedTemporaryFile(prefix="mame-listxml-", suffix=".xml", delete=False) as tmp:
                temp_path = Path(tmp.name)
            try:
                with temp_path.open("wb") as out:
                    subprocess.run([str(self.mame_exe), "-listxml"], stdout=out, stderr=subprocess.PIPE, check=True)
                self.filter_xml(temp_path, machine_ids, output_path)
            finally:
                temp_path.unlink(missing_ok=True)
        else:
            self.filter_xml(Path(source_xml), machine_ids, output_path)
        return output_path

    def filter_xml(self, source_xml: Path, machine_ids: Iterable[str], output_path: Path) -> Path:
        wanted = set(machine_ids)
        output_path = Path(output_path)
        temp = output_path.with_suffix(output_path.suffix + ".partial")
        count = 0
        with temp.open("wb") as out:
            out.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
            context = ET.iterparse(str(source_xml), events=("start", "end"))
            _, root = next(context)
            root_attrs = "".join(f' {k}="{_xml_escape(v)}"' for k, v in root.attrib.items())
            out.write(f"<mame{root_attrs}>\n".encode("utf-8"))
            for event, elem in context:
                if event == "end" and elem.tag == "machine":
                    if elem.get("name") in wanted:
                        out.write(ET.tostring(elem, encoding="utf-8"))
                        out.write(b"\n")
                        count += 1
                    elem.clear()
            out.write(b"</mame>\n")
        os.replace(temp, output_path)
        if count != len(wanted):
            # Não falha: a saída continua válida e o chamador pode informar IDs não encontrados.
            pass
        return output_path

    @staticmethod
    def generate_missing_xml(source_xml: Path, scan_result, output_path: Path) -> Path:
        """Gera um listxml válido contendo máquinas com itens ausentes/ruins."""
        bad = {m.name for m in scan_result.machines if m.status.value in {"missing", "corrupted", "unavailable", "fixable"}}
        return ListxmlExportService(Path(""), Path("" )).filter_xml(source_xml, bad, output_path)

    def get_machine_ids_from_db(self, criteria: Optional[FilterCriteria] = None) -> List[str]:
            """Retorna os nomes das máquinas que atendem aos critérios informados."""
            db = Database(self.db_path)
            db.connect()
            try:
                filter_service = FilterService(db.conn)
                return filter_service.get_machine_names(criteria or FilterCriteria())
            finally:
                db.close()


def _xml_escape(value: str) -> str:
    return (str(value).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;"))
