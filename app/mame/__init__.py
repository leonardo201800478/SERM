"""Integrações do pacote MAME Set Builder.

A validação de CHD com ``chdman`` pertence exclusivamente à reconstrução.
Durante o scan físico fazemos somente resolução determinística do caminho e
verificação de existência do arquivo. Isso mantém o scan rápido e evita ler
CHDs que nem existem.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .chdman_validator import ChdmanError, validate_chd


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
    """Substitui somente a localização de CHD do scanner físico.

    O scanner continua expected-driven: para cada disco são testados apenas
    caminhos derivados da própria machine, do ``disk.merge`` e da cadeia de
    parents. Não existe ``rglob`` nem busca global por CHD.
    """
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
    """Completa o cabeçalho do manifesto streaming sem uma segunda varredura.

    O scanner abre o JSONL antes dos workers para persistência incremental.
    A GUI, entretanto, passa o LISTXML ao método de compatibilidade
    ``write_manifest`` somente depois que o scan termina. A implementação
    anterior retornava imediatamente quando o manifesto já existia, deixando
    ``xml_path`` ausente no cabeçalho e tornando a reconstrução impossível.
    Aqui atualizamos somente a primeira linha de metadados; os registros de
    ROM/CHD já gravados não são recalculados nem relidos do HDD.
    """
    from .physical_rom_scanner import PhysicalRomScanner

    original_write_manifest = PhysicalRomScanner.write_manifest

    def write_manifest(self, xml_machines, xml_path, output_path, mame_version, source_paths):
        path = Path(getattr(self, "_manifest_path", output_path) or output_path)
        if path.is_file() and xml_path:
            try:
                lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
                if lines:
                    header = json.loads(lines[0])
                    if header.get("record_type") == "header":
                        header["xml_path"] = str(Path(xml_path).resolve())
                        header["mame_version"] = str(mame_version or header.get("mame_version") or "unknown")
                        header["source_paths"] = [str(Path(p).resolve()) for p in source_paths]
                        lines[0] = json.dumps(header, ensure_ascii=False) + "\n"
                        temporary = path.with_suffix(path.suffix + ".metadata.tmp")
                        temporary.write_text("".join(lines), encoding="utf-8")
                        temporary.replace(path)
                        self._manifest_path = path
                        return path
            except Exception:
                # Não destrói um manifesto válido por falha apenas de metadata.
                # A reconstrução ainda poderá diagnosticar o cabeçalho ausente.
                pass
        return original_write_manifest(self, xml_machines, xml_path, output_path, mame_version, source_paths)

    PhysicalRomScanner.write_manifest = write_manifest


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