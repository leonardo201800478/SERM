"""Integrações do pacote MAME Set Builder.

A validação de CHD com ``chdman`` pertence exclusivamente à reconstrução.
Durante o scan físico fazemos somente resolução determinística do caminho e
verificação de existência do arquivo. Isso mantém o scan rápido e evita ler
CHDs que nem existem.
"""
from __future__ import annotations

import json
import logging
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from .chdman_validator import ChdmanError, validate_chd

logger = logging.getLogger(__name__)


def _machine_parent_chain(scanner, machine_name: str) -> list[str]:
    """Retorna a cadeia ``machine -> parent -> ...`` sem varrer o HDD."""
    cache = getattr(scanner, "_parent_chain_cache", None)
    if cache is None:
        cache = {}
        scanner._parent_chain_cache = cache

    if machine_name in cache:
        return list(cache[machine_name])

    chain: list[str] = []
    seen: set[str] = set()
    current = str(machine_name or "").strip()

    while current and current not in seen:
        seen.add(current)
        chain.append(current)
        try:
            rows = scanner.db.fetchall(
                "SELECT cloneof FROM machine WHERE name = ? LIMIT 1",
                (current,),
            )
        except Exception:
            rows = []
        if not rows:
            break
        parent = str(rows[0]["cloneof"] or "").strip()
        if not parent or parent == current:
            break
        current = parent

    cache[machine_name] = tuple(chain)
    return chain


def _patch_chd_scan() -> None:
    """Substitui somente a localização de CHD do scanner físico."""
    from .physical_rom_scanner import PhysicalRomScanner

    def scan_expected_chd(self, machine_name: str, disk: dict, cancelled=None) -> dict:
        """Localiza um CHD esperado sem abrir, hashear ou validar seu conteúdo."""
        disk_name = str(disk.get("name") or "").strip()
        merge_machine = str(disk.get("merge") or "").strip()
        if not disk_name:
            return {"status": "error", "source_path": None, "source_machine": None, "error": "CHD sem nome"}

        filename = Path(disk_name).name
        if not filename.lower().endswith(".chd"):
            filename = f"{filename}.chd"

        machine_candidates: list[str] = []
        seen: set[str] = set()

        def add_machine(name: str) -> None:
            name = str(name or "").strip()
            if name and name not in seen:
                seen.add(name)
                machine_candidates.append(name)

        add_machine(machine_name)
        if merge_machine:
            add_machine(merge_machine)
        for parent in _machine_parent_chain(self, machine_name):
            add_machine(parent)

        candidates: list[tuple[str, Path]] = []
        for base in self.source_dirs:
            for candidate_machine in machine_candidates:
                self._check_cancelled(cancelled)
                candidates.append((candidate_machine, base / candidate_machine / filename))

        for source_machine, path in candidates:
            self._check_cancelled(cancelled)
            if path.is_file():
                try:
                    physical_size = path.stat().st_size
                except OSError:
                    physical_size = 0
                return {
                    "status": "present",
                    "source_path": str(path),
                    "source_machine": source_machine,
                    "physical_size": physical_size,
                    "logical_size": int(disk.get("size") or 0),
                    "expected_sha1": str(disk.get("sha1") or "").strip().lower() or None,
                    "error": None,
                }

        return {
            "status": "missing",
            "source_path": None,
            "source_machine": None,
            "physical_size": 0,
            "logical_size": int(disk.get("size") or 0),
            "expected_sha1": str(disk.get("sha1") or "").strip().lower() or None,
            "searched_paths": [str(path) for _machine, path in candidates],
            "error": "CHD não encontrado nos caminhos esperados",
        }

    def progress_message(stats: dict, machine: str, completed: int, total: int) -> str:
        """Mostra CHDs presentes/ausentes e progresso real de processamento."""
        processed = stats["chds"]
        expected = stats["expected_chds"]
        return (
            f"Machine {completed:,}/{total:,}: {machine} | "
            f"ROMs {stats['members']:,} verificadas | válidas {stats['valid']:,} | "
            f"ausentes {stats['missing']:,} | "
            f"CHDs {stats['chds_present']:,} presentes | "
            f"{stats['chds_missing']:,} ausentes | "
            f"processados {processed:,}/{expected:,} | "
            f"dados lidos {stats['bytes_read'] / (1024**3):.2f} GiB"
        )

    def summary_message(stats: dict) -> str:
        """Resumo final sem confundir processados com presentes."""
        return (
            f"Scan concluído: {stats['machines_completed']:,}/{stats['machines']:,} machines | "
            f"ROMs válidas {stats['valid']:,} | ausentes {stats['missing']:,} | "
            f"CHDs presentes {stats['chds_present']:,} | "
            f"ausentes {stats['chds_missing']:,} | "
            f"processados {stats['chds']:,}/{stats['expected_chds']:,} | "
            f"tempo {stats['seconds']:.2f}s"
        )

    PhysicalRomScanner._scan_expected_chd = scan_expected_chd
    PhysicalRomScanner._progress_message = staticmethod(progress_message)
    PhysicalRomScanner._summary_message = staticmethod(summary_message)


def _patch_streaming_manifest_metadata() -> None:
    """Atualiza somente o header do JSONL streaming, sem novo scan.

    O scan grava ROMs/CHDs incrementalmente. Ao terminar, a GUI informa o
    LISTXML usado e a versão do MAME. Esta compatibilidade corrige apenas a
    primeira linha do manifesto; os registros físicos nunca são recalculados.
    """
    from .physical_rom_scanner import PhysicalRomScanner
    from .reconstruction_engine import ReconstructionEngine

    original_write_manifest = PhysicalRomScanner.write_manifest
    original_load_header = ReconstructionEngine.load_manifest_header

    def _rewrite_header(path: Path, xml_path: Path, mame_version: str, source_paths) -> bool:
        """Reescreve atomicamente somente a primeira linha do JSONL."""
        if not path.is_file() or not xml_path or not Path(xml_path).is_file():
            return False
        temporary = path.with_name(path.name + ".metadata.tmp")
        try:
            with path.open("r", encoding="utf-8") as source, temporary.open("w", encoding="utf-8", newline="\n") as target:
                first = source.readline()
                if not first.strip():
                    return False
                header = json.loads(first)
                if header.get("record_type") != "header":
                    return False
                header["xml_path"] = str(Path(xml_path).resolve())
                if mame_version and str(mame_version).lower() != "unknown":
                    header["mame_version"] = str(mame_version)
                header["source_paths"] = [str(Path(p).resolve()) for p in source_paths if p]
                target.write(json.dumps(header, ensure_ascii=False) + "\n")
                shutil.copyfileobj(source, target, length=1024 * 1024)
            temporary.replace(path)
            return True
        except Exception:
            temporary.unlink(missing_ok=True)
            logger.exception("Falha atualizando metadata do manifesto: %s", path)
            return False

    def write_manifest(self, xml_machines, xml_path, output_path, mame_version, source_paths):
        """Atualiza o manifesto já criado pelo scan streaming."""
        path = Path(getattr(self, "_manifest_path", output_path) or output_path)
        if _rewrite_header(path, Path(xml_path) if xml_path else Path(), str(mame_version or "unknown"), source_paths):
            self._manifest_path = path
            return path
        return original_write_manifest(self, xml_machines, xml_path, output_path, mame_version, source_paths)

    def _discover_xml_for_manifest(path: Path, header: dict) -> Path | None:
        """Encontra LISTXML local compatível para manifests antigos sem xml_path."""
        if header.get("xml_path"):
            candidate = Path(str(header["xml_path"]))
            if candidate.is_file():
                return candidate

        scan_dir = path.parent
        expected = int(header.get("machine_count_expected") or 0)
        candidates: list[tuple[float, Path]] = []
        for xml in scan_dir.glob("*.xml"):
            try:
                root = ET.parse(xml).getroot()
                count = len(root.findall("machine"))
            except (OSError, ET.ParseError):
                continue
            if expected and count != expected:
                continue
            candidates.append((xml.stat().st_mtime, xml))

        if not candidates:
            return None
        candidates.sort(reverse=True)
        if len(candidates) > 1:
            logger.warning(
                "Mais de um LISTXML compatível com o manifesto; usando o mais recente: %s",
                candidates[0][1],
            )
        return candidates[0][1]

    def load_manifest_header(path):
        """Lê o header e recupera metadata ausente sem tocar nos registros do scan."""
        header = original_load_header(path)
        manifest = Path(path)
        if header.get("xml_path"):
            return header

        xml_path = _discover_xml_for_manifest(manifest, header)
        if xml_path is None:
            return header

        root = ET.parse(xml_path).getroot()
        build = str(root.get("build") or "").strip()
        version = header.get("mame_version")
        if not version or str(version).lower() == "unknown":
            version = build.split(" ", 1)[0] if build else "unknown"

        if _rewrite_header(manifest, xml_path, version, header.get("source_paths", [])):
            header["xml_path"] = str(xml_path.resolve())
            header["mame_version"] = version
            logger.info(
                "Metadata do manifesto reparada sem novo scan: LISTXML=%s | MAME=%s",
                xml_path,
                version,
            )
        return header

    PhysicalRomScanner.write_manifest = write_manifest
    ReconstructionEngine.load_manifest_header = staticmethod(load_manifest_header)


def _patch_reconstruction_chd_validation() -> None:
    """Mantém ``chdman`` somente na reconstrução/publicação de CHDs."""
    from .reconstruction_engine import ReconstructionEngine

    original_stream_source = ReconstructionEngine._stream_source

    def stream_source(self, item, source, staged) -> None:
        """Copia o CHD para staging e valida o container com chdman."""
        if not item.is_chd:
            return original_stream_source(self, item, source, staged)

        kind, source_path, _member = source
        if kind != "chd":
            raise ValueError(f"origem inválida para CHD: {kind}")
        staged.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, staged)
        try:
            valid, info = validate_chd(staged, expected_sha1=item.chd_sha1, expected_logical_size=0)
        except ChdmanError:
            staged.unlink(missing_ok=True)
            raise
        if not valid:
            staged.unlink(missing_ok=True)
            if not info.get("sha1_match", True):
                raise ValueError(
                    f"SHA-1 lógico do CHD incompatível: esperado={item.chd_sha1}, encontrado={info.get('sha1')}"
                )
            raise ValueError("CHD inválido segundo chdman")

    def validate_existing_chd(target, chd) -> bool:
        """Valida um CHD já publicado usando chdman."""
        if not target.is_file():
            return False
        try:
            valid, _info = validate_chd(target, expected_sha1=chd.chd_sha1, expected_logical_size=0)
            return valid
        except (ChdmanError, OSError, ValueError):
            return False

    ReconstructionEngine._stream_source = stream_source
    ReconstructionEngine._validate_existing_chd = staticmethod(validate_existing_chd)


_patch_chd_scan()
_patch_streaming_manifest_metadata()
_patch_reconstruction_chd_validation()

__all__ = ["ChdmanError", "validate_chd"]