"""Aquisição e normalização das bases de jogos dos emuladores."""
from __future__ import annotations

import logging
import os
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CatalogResult:
    """Resultado auditável da aquisição de um catálogo."""

    emulator: str
    path: Path
    source: str
    machine_count: int


class EmulatorCatalogService:
    """Gera fontes de catálogo sem misturar aquisição com filtragem."""

    def __init__(self, catalog_root: Path | None = None) -> None:
        self.catalog_root = Path(catalog_root or Path("data") / "database" / "catalog")

    def generate_mame(self, executable: Path) -> CatalogResult:
        """Gera o LISTXML completo do MAME instalado."""
        exe = self._require_executable(executable, "mame")
        output = self._target("mame", "listxml.xml")
        self._run_xml_command("mame", exe, ["-noreadconfig", "-listxml"], output)
        return CatalogResult("mame", output, "mame_listxml", self._count_machines(output))

    def generate_fbneo(self, executable: Path) -> CatalogResult:
        """Gera o LISTXML do FBNeo usando ``-listinfo``."""
        exe = self._require_executable(executable, "fbneo")
        output = self._target("fbneo", "listxml.xml")
        self._run_xml_command("fbneo", exe, ["-listinfo"], output)
        return CatalogResult("fbneo", output, "fbneo_listinfo", self._count_machines(output))

    def generate_supermodel(self, root: Path) -> CatalogResult:
        """Converte ``Config/Games.xml`` do Supermodel para LISTXML."""
        root = Path(root).expanduser().resolve()
        source = root / "Config" / "Games.xml"
        if not source.is_file():
            raise FileNotFoundError(f"Games.xml do Supermodel não encontrado: {source}")
        output = self._target("supermodel", "listxml.xml")
        count = self._convert_supermodel_games(source, output)
        return CatalogResult("supermodel", output, "supermodel_games_xml", count)

    def generate_flycast_from_mame(
        self,
        source_xml: Path,
        machine_names: Iterable[str],
    ) -> CatalogResult:
        """Cria o catálogo Flycast a partir de um LISTXML MAME existente."""
        source = Path(source_xml).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"LISTXML de origem não encontrado: {source}")
        names = {str(name).strip() for name in machine_names if str(name).strip()}
        output = self._target("flycast", "listxml.xml")
        count = self._filter_listxml(source, names, output)
        return CatalogResult("flycast", output, "mame_listxml_filtered", count)

    def generate_all(
        self,
        *,
        mame_executable: Path | None = None,
        fbneo_executable: Path | None = None,
        supermodel_root: Path | None = None,
        flycast_source_xml: Path | None = None,
        flycast_machine_names: Iterable[str] = (),
    ) -> list[CatalogResult]:
        """Gera todos os catálogos cujas fontes já estão configuradas."""
        results: list[CatalogResult] = []
        jobs = (
            ("mame", lambda: self.generate_mame(mame_executable) if mame_executable else None),
            ("fbneo", lambda: self.generate_fbneo(fbneo_executable) if fbneo_executable else None),
            ("supermodel", lambda: self.generate_supermodel(supermodel_root) if supermodel_root else None),
            (
                "flycast",
                lambda: self.generate_flycast_from_mame(flycast_source_xml, flycast_machine_names)
                if flycast_source_xml
                else None,
            ),
        )
        for name, job in jobs:
            try:
                result = job()
                if result is not None:
                    results.append(result)
            except Exception:
                logger.exception("Emulator catalog: falha | emulator=%s", name)
        return results

    def _target(self, emulator: str, filename: str) -> Path:
        """Cria e retorna o caminho persistente do catálogo."""
        target_dir = self.catalog_root / emulator
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / filename

    @staticmethod
    def _require_executable(executable: Path, emulator: str) -> Path:
        """Aceita somente arquivo executável real já instalado."""
        path = Path(executable).expanduser().resolve()
        if path.suffix.casefold() != ".exe":
            raise ValueError(f"Executável inválido para {emulator}: {path}")
        if not path.is_file():
            raise FileNotFoundError(f"Executável de {emulator} não encontrado: {path}")
        return path

    @staticmethod
    def _run_xml_command(emulator: str, executable: Path, arguments: list[str], output: Path) -> None:
        """Executa uma CLI de catálogo sem shell e grava a saída atomicamente."""
        temp = output.with_suffix(output.suffix + ".partial")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = None
        if hasattr(subprocess, "STARTUPINFO"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
        logger.info(
            "Emulator catalog: iniciando | emulator=%s | executable=%s | args=%s",
            emulator,
            executable,
            arguments,
        )
        try:
            with temp.open("wb") as stream:
                result = subprocess.run(
                    [str(executable), *arguments],
                    cwd=str(executable.parent),
                    stdin=subprocess.DEVNULL,
                    stdout=stream,
                    stderr=subprocess.PIPE,
                    shell=False,
                    creationflags=creationflags,
                    startupinfo=startupinfo,
                    timeout=300,
                    check=False,
                )
            stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
            if result.returncode != 0:
                raise RuntimeError(f"{emulator} terminou com código {result.returncode}: {stderr.strip()}")
            if not temp.is_file() or temp.stat().st_size == 0:
                raise RuntimeError(f"{emulator} não produziu catálogo XML")
            EmulatorCatalogService._validate_xml(temp)
            os.replace(temp, output)
            logger.info(
                "Emulator catalog: concluído | emulator=%s | output=%s | bytes=%d",
                emulator,
                output,
                output.stat().st_size,
            )
        except Exception:
            temp.unlink(missing_ok=True)
            raise

    @staticmethod
    def _convert_supermodel_games(source: Path, output: Path) -> int:
        """Converte o Games.xml oficial do Supermodel para LISTXML."""
        temp = output.with_suffix(output.suffix + ".partial")
        count = 0
        try:
            tree = ET.parse(source)
            root = tree.getroot()
            out_root = ET.Element("mame", {"build": "supermodel"})
            for game in root.findall("game"):
                name = (game.get("name") or "").strip()
                if not name:
                    continue
                attrs = {"name": name}
                parent = (game.get("parent") or "").strip()
                if parent:
                    attrs["cloneof"] = parent
                machine = ET.SubElement(out_root, "machine", attrs)
                identity = game.find("identity")
                if identity is not None:
                    for child_name, tag in (("title", "description"), ("year", "year"), ("manufacturer", "manufacturer")):
                        value = (identity.findtext(child_name) or "").strip()
                        if value:
                            ET.SubElement(machine, tag).text = value
                hardware = game.find("hardware")
                if hardware is not None:
                    platform = (hardware.findtext("platform") or "").strip()
                    if platform:
                        ET.SubElement(machine, "feature", {"type": "platform", "status": platform})
                roms = game.find("roms")
                if roms is not None:
                    for region in roms.findall("region"):
                        region_name = (region.get("name") or "").strip()
                        for file_node in region.findall("file"):
                            rom_name = (file_node.get("name") or "").strip()
                            if not rom_name:
                                continue
                            rom_attrs = {"name": rom_name}
                            crc = (file_node.get("crc32") or "").strip().lower().removeprefix("0x")
                            if crc:
                                rom_attrs["crc"] = crc.zfill(8)
                            if region_name:
                                rom_attrs["region"] = region_name
                            ET.SubElement(machine, "rom", rom_attrs)
                count += 1
            ET.ElementTree(out_root).write(temp, encoding="utf-8", xml_declaration=True)
            EmulatorCatalogService._validate_xml(temp)
            os.replace(temp, output)
            return count
        except Exception:
            temp.unlink(missing_ok=True)
            raise

    @staticmethod
    def _filter_listxml(source: Path, names: set[str], output: Path) -> int:
        """Filtra máquinas de um LISTXML preservando o subtree original."""
        temp = output.with_suffix(output.suffix + ".partial")
        count = 0
        try:
            context = ET.iterparse(source, events=("start", "end"))
            _, root = next(context)
            out_root = ET.Element(root.tag, root.attrib)
            for event, element in context:
                if event != "end" or element.tag not in {"machine", "game"}:
                    continue
                if element.get("name") in names:
                    out_root.append(element)
                    count += 1
                else:
                    element.clear()
            ET.ElementTree(out_root).write(temp, encoding="utf-8", xml_declaration=True)
            EmulatorCatalogService._validate_xml(temp)
            os.replace(temp, output)
            return count
        except Exception:
            temp.unlink(missing_ok=True)
            raise

    @staticmethod
    def _validate_xml(path: Path) -> None:
        """Valida sintaxe XML antes de publicar o catálogo."""
        ET.parse(path)
        if path.stat().st_size <= 0:
            raise ValueError(f"Catálogo vazio: {path}")

    @staticmethod
    def _count_machines(path: Path) -> int:
        """Conta máquinas/game sem manter uma árvore completa em memória."""
        count = 0
        for _, element in ET.iterparse(path, events=("end",)):
            if element.tag in {"machine", "game"}:
                count += 1
                element.clear()
        return count
