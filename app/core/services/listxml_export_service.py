"""Serviço para gerar um LISTXML do MAME a partir de critérios de filtro."""
from __future__ import annotations

import logging
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional

from app.config.app_config import AppConfig
from app.core.models.filter_profile import FilterCriteria
from app.core.services.filter_service import FilterService
from app.database.database import Database

logger = logging.getLogger(__name__)


class ListxmlExportService:
    """Gera um LISTXML contendo somente as máquinas selecionadas pelo filtro."""

    def __init__(self, db_path: Path, mame_exe: Optional[Path] = None):
        self.db_path = Path(db_path)
        self.mame_exe = Path(mame_exe) if mame_exe else AppConfig().mame_path

    def generate_filtered_xml(
        self,
        machine_names: List[str],
        output_path: Path,
    ) -> Path:
        """Gera o XML filtrado para os nomes de máquinas fornecidos."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not machine_names:
            return self._create_empty_xml(output_path)

        return self._filter_from_mame(machine_names, output_path)

    def get_machine_names_from_criteria(
        self,
        criteria: FilterCriteria,
    ) -> List[str]:
        """Aplica os critérios do perfil e retorna os nomes das máquinas."""
        database = Database(self.db_path)
        database.connect()

        try:
            filter_service = FilterService(database.conn)
            machine_ids = filter_service.apply_filters(criteria)

            if not machine_ids:
                return []

            placeholders = ",".join("?" for _ in machine_ids)
            cursor = database.conn.execute(
                f"""
                SELECT name
                FROM machine
                WHERE id IN ({placeholders})
                ORDER BY name
                """,
                machine_ids,
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            database.close()

    def get_machine_ids_from_db(
        self,
        filter_criteria: Optional[dict] = None,
    ) -> List[str]:
        """Mantém compatibilidade com a API antiga."""
        criteria = FilterCriteria()

        if filter_criteria:
            if filter_criteria.get("working_arcade"):
                criteria.emulation_status = ["working"]

            if filter_criteria.get("no_clones"):
                criteria.include_clones = False

            category = filter_criteria.get("machine_category")
            if category:
                normalized = str(category).strip().lower().replace(" ", "_")
                criteria.include_categories = [normalized]

        return self.get_machine_names_from_criteria(criteria)

    def _filter_from_mame(
        self,
        machine_names: List[str],
        output_path: Path,
    ) -> Path:
        """Executa ``mame -listxml`` em streaming e mantém apenas as máquinas selecionadas.

        O stdout é tratado como bytes deliberadamente. No Windows, usar
        ``subprocess.run(..., text=True)`` sem ``encoding=`` faz o Python usar a
        codificação da locale, que no ambiente do usuário é CP1252. O MAME pode
        produzir bytes UTF-8 que não são decodificáveis por CP1252, causando o
        ``UnicodeDecodeError`` observado.

        Além disso, o LISTXML completo pode ter centenas de MB. ``iterparse``
        evita materializar o XML inteiro em memória.
        """
        if not self.mame_exe or not self.mame_exe.exists():
            raise FileNotFoundError(f"MAME não encontrado: {self.mame_exe}")

        machine_set = set(machine_names)

        logger.info(
            "Executando MAME -listxml para gerar XML filtrado (%d máquinas).",
            len(machine_set),
        )

        # O stderr vai para um arquivo temporário para não correr o risco de
        # bloquear o processo MAME caso ele produza uma quantidade grande de
        # mensagens enquanto o stdout está sendo processado.
        with tempfile.TemporaryFile(mode="w+b") as stderr_file:
            process = subprocess.Popen(
                [str(self.mame_exe), "-listxml"],
                stdout=subprocess.PIPE,
                stderr=stderr_file,
                stdin=subprocess.DEVNULL,
                shell=False,
                bufsize=1024 * 1024,
            )

            if process.stdout is None:
                process.kill()
                process.wait()
                raise RuntimeError("Não foi possível abrir o stdout do MAME.")

            selected = 0
            root_started = False
            root_tag = "mame"
            root_attrs = {}

            try:
                # ET.iterparse aceita o pipe binário diretamente. Dessa forma
                # o parser respeita a declaração de encoding do XML e não usa a
                # CP1252 da console do Windows.
                context = ET.iterparse(
                    process.stdout,
                    events=("start", "end"),
                )

                with open(output_path, "wb") as output:
                    for event, element in context:
                        if event == "start" and not root_started:
                            root_started = True
                            root_tag = element.tag
                            root_attrs = dict(element.attrib)

                            root_element = ET.Element(root_tag, root_attrs)
                            root_bytes = ET.tostring(
                                root_element,
                                encoding="utf-8",
                                short_empty_elements=False,
                            )
                            root_open = root_bytes.split(b">", 1)[0] + b">"

                            output.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
                            output.write(root_open)
                            output.write(b"\n")
                            continue

                        if event == "end" and element.tag == "machine":
                            name = element.get("name")

                            if name in machine_set:
                                output.write(
                                    ET.tostring(
                                        element,
                                        encoding="utf-8",
                                        short_empty_elements=True,
                                    )
                                )
                                output.write(b"\n")
                                selected += 1

                            # Libera os filhos da máquina que já foi processada.
                            element.clear()

                    output.write(f"</{root_tag}>\n".encode("utf-8"))

            except ET.ParseError as exc:
                process.kill()
                process.wait()
                stderr_message = self._read_stderr(stderr_file)
                raise RuntimeError(
                    "O MAME produziu um LISTXML que não pôde ser interpretado. "
                    f"Detalhes do parser: {exc}. "
                    f"STDERR: {stderr_message or 'nenhum'}"
                ) from exc
            except Exception:
                if process.poll() is None:
                    process.kill()
                process.wait()
                raise
            finally:
                process.stdout.close()

            returncode = process.wait()
            stderr_message = self._read_stderr(stderr_file)

        if returncode != 0:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass

            raise RuntimeError(
                f"MAME -listxml terminou com código {returncode}. "
                f"STDERR: {stderr_message or 'nenhum'}"
            )

        if not root_started:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise RuntimeError("MAME não retornou um documento XML válido.")

        if selected == 0:
            logger.warning(
                "Nenhuma das %d máquinas selecionadas pelo perfil foi encontrada "
                "no LISTXML do MAME.",
                len(machine_set),
            )

        logger.info(
            "XML filtrado salvo em %s (%d máquinas selecionadas de %d).",
            output_path,
            selected,
            len(machine_set),
        )

        return output_path

    @staticmethod
    def _read_stderr(stderr_file) -> str:
        """Lê o stderr temporário sem deixar erros de codificação interromperem o fluxo."""
        stderr_file.seek(0)
        raw = stderr_file.read()
        if not raw:
            return ""

        return raw.decode("utf-8", errors="replace").strip()

    def _create_empty_xml(self, output_path: Path) -> Path:
        """Cria um LISTXML vazio quando nenhum filtro retorna máquinas."""
        root = ET.Element("mame")
        tree = ET.ElementTree(root)
        tree.write(
            str(output_path),
            encoding="utf-8",
            xml_declaration=True,
        )
        return output_path
