import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional
import subprocess
import logging

from app.config.app_config import AppConfig
from app.core.database import Database

logger = logging.getLogger(__name__)

class ListxmlExportService:
    def __init__(self, db_path: Path, mame_exe: Optional[Path] = None):
        self.db_path = db_path
        self.mame_exe = mame_exe or AppConfig().mame_path

    def generate_filtered_xml(self, machine_ids: List[str], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not machine_ids:
            self._create_empty_xml(output_path)
            return output_path
        return self._filter_from_mame(machine_ids, output_path)

    def _filter_from_mame(self, machine_ids: List[str], output_path: Path) -> Path:
        if not self.mame_exe or not self.mame_exe.exists():
            raise FileNotFoundError(f"MAME não encontrado: {self.mame_exe}")

        machine_set = set(machine_ids)
        result = subprocess.run(
            [str(self.mame_exe), "-listxml"],
            capture_output=True,
            text=True,
            check=True
        )
        root = ET.fromstring(result.stdout)

        new_root = ET.Element("mame")
        mame_elem = root.find("mame")
        if mame_elem is not None:
            for attr, value in mame_elem.attrib.items():
                new_root.set(attr, value)

        for machine in root.findall("machine"):
            if machine.get("name") in machine_set:
                new_root.append(machine)

        tree = ET.ElementTree(new_root)
        tree.write(str(output_path), encoding="utf-8", xml_declaration=True)
        logger.info(f"XML filtrado salvo em: {output_path}")
        return output_path

    def _create_empty_xml(self, output_path: Path) -> Path:
        root = ET.Element("mame")
        ET.ElementTree(root).write(str(output_path), encoding="utf-8", xml_declaration=True)
        return output_path

    def get_machine_ids_from_db(self, filter_criteria: dict = None) -> List[str]:
        db = Database(self.db_path)
        conn = db.conn
        cursor = conn.cursor()

        query = "SELECT name FROM machine WHERE 1=1"
        params = []
        if filter_criteria:
            if filter_criteria.get('working_arcade'):
                query += " AND working_arcade = 1"
            if filter_criteria.get('machine_category'):
                query += " AND machine_category = ?"
                params.append(filter_criteria['machine_category'])
            if filter_criteria.get('no_clones'):
                query += " AND (cloneof IS NULL OR cloneof = '')"

        cursor.execute(query, params)
        results = [row[0] for row in cursor.fetchall()]
        conn.close()
        return results