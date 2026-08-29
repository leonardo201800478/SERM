"""Exportação de subconjuntos do LISTXML sem reduzir conteúdo estrutural."""
from __future__ import annotations

import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path

from app.config.app_config import AppConfig
from app.core.models.filter_profile import FilterCriteria
from app.core.models.scan_result import ScanResult
from app.core.services.filter_service import FilterService
from app.database.database import Database


class ListxmlExportService:
    """Exporta subconjuntos preservando o subtree original de cada
    ``<machine>`` selecionada — nunca reconstrói nós a partir de um
    modelo reduzido do banco."""

    def __init__(self, db_path: Path, mame_exe: Path | None = None):
        self.db_path = Path(db_path)
        self.mame_exe = mame_exe or AppConfig().mame_path

    def generate_filtered_xml(
        self, machine_ids: list[str], output_path: Path, source_xml: Path | None = None,
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if source_xml is not None:
            return self.filter_xml(Path(source_xml), machine_ids, output_path)

        if not self.mame_exe or not Path(self.mame_exe).exists():
            raise FileNotFoundError(f"MAME não encontrado: {self.mame_exe}")

        with tempfile.NamedTemporaryFile(prefix="mame-listxml-", suffix=".xml", delete=False) as tmp:
            temp_path = Path(tmp.name)
        try:
            with temp_path.open("wb") as out:
                subprocess.run([str(self.mame_exe), "-listxml"], stdout=out, stderr=subprocess.PIPE, check=True)
            return self.filter_xml(temp_path, machine_ids, output_path)
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def filter_xml(source_xml: Path, machine_ids: Iterable[str], output_path: Path) -> Path:
        """Copia, em streaming, somente os elementos ``<machine>`` cujo
        atributo ``name`` está em ``machine_ids`` — sem normalizar nem
        perder nenhum atributo/elemento do XML original."""
        wanted = set(machine_ids)
        output_path = Path(output_path)
        temp = output_path.with_suffix(output_path.suffix + ".partial")

        with temp.open("wb") as out:
            out.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
            context = ET.iterparse(str(source_xml), events=("start", "end"))
            _, root = next(context)
            root_attrs = "".join(f' {k}="{_xml_escape(v)}"' for k, v in root.attrib.items())
            out.write(f"<mame{root_attrs}>\n".encode())

            for event, elem in context:
                if event == "end" and elem.tag == "machine":
                    if elem.get("name") in wanted:
                        out.write(ET.tostring(elem, encoding="utf-8"))
                        out.write(b"\n")
                    elem.clear()

            out.write(b"</mame>\n")

        os.replace(temp, output_path)
        return output_path

    @staticmethod
    def generate_missing_xml(source_xml: Path, scan_result: ScanResult, output_path: Path) -> Path:
        """Gera um LISTXML válido contendo as máquinas com ROMs/CHDs
        ausentes, inválidos ou com erro em ``scan_result``. Esse XML pode
        alimentar uma etapa posterior de aquisição autorizada — esta
        função não baixa nem executa nada."""
        problem_names = {m.machine_name for m in scan_result.problem_machines()}
        return ListxmlExportService.filter_xml(source_xml, problem_names, output_path)

    def get_machine_ids_from_db(self, criteria: FilterCriteria | None = None) -> list[str]:
        """Nomes (``machine.name``) das máquinas que atendem aos
        critérios — usados para localizar as máquinas no XML original."""
        db = Database(self.db_path)
        db.connect()
        try:
            filter_service = FilterService(db.conn)
            return filter_service.get_machine_names(criteria or FilterCriteria())
        finally:
            db.close()


def _xml_escape(value: str) -> str:
    return str(value).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")