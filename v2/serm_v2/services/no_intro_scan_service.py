"""Scanner expected-driven para DATs No-Intro.

O DAT selecionado e a fonte de verdade. O scan nao aplica filtros nem heuristicas
para escolher variantes: Headered/Headerless, BigEndian/ByteSwapped,
Encrypted/Decrypted etc. sao DATs independentes.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import zipfile
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree

from ..runtime.paths import scans_root
from .rom_scan_service import ScanEvidence, ScanResult


class NoIntroScanError(RuntimeError):
    """Erro de catalogo ou execucao do scan No-Intro."""


@dataclass(slots=True, frozen=True)
class _ExpectedRom:
    game_name: str
    rom_name: str
    size: int
    crc: str
    md5: str
    sha1: str
    status: str
    fmt: str


class NoIntroScanService:
    """Executa auditoria bruta de um DAT No-Intro sem aplicar filtros."""

    CHUNK_SIZE = 1024 * 1024

    def __init__(self, *, progress_callback: Callable[[int, int], None] | None = None) -> None:
        self.progress_callback = progress_callback
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def scan(self, profile) -> ScanResult:
        started = time.time()
        dat_path = Path(profile.dat_path).expanduser().resolve() if profile.dat_path else None
        if dat_path is None or not dat_path.is_file():
            raise NoIntroScanError("O perfil No-Intro nao possui um DAT local valido.")

        sources = [Path(p).expanduser().resolve() for p in profile.source_directories]
        if not sources:
            raise NoIntroScanError("Nenhum diretorio de origem foi configurado para o scan No-Intro.")
        for source in sources:
            if not source.is_dir():
                raise NoIntroScanError(f"Diretorio de origem nao encontrado: {source}")

        expected, header = self._load_dat(dat_path)
        if not expected:
            raise NoIntroScanError(f"Nenhuma ROM encontrada no DAT: {dat_path}")

        date_label = self._catalog_label(dat_path, header)
        result = ScanResult(
            scan_id=self._make_scan_id(profile),
            profile_id=str(profile.profile_id),
            source="No-Intro",
            system=str(profile.system),
            started_at=started,
            catalog_label=f"{profile.system} - {date_label}",
            scan_type="full",
        )
        result.catalog_hash = self._sha256(dat_path)

        stream_path = scans_root() / "streaming" / f"{result.scan_id}.jsonl"
        stream_path.parent.mkdir(parents=True, exist_ok=True)
        result.evidence_stream_path = str(stream_path)

        games = self._group_by_game(expected)
        total = len(expected)
        completed = 0
        with stream_path.open("w", encoding="utf-8", newline="\n") as stream:
            self._write_jsonl(stream, {
                "record_type": "header",
                "format": "SERM-SCAN-V1",
                "scan_id": result.scan_id,
                "profile_id": result.profile_id,
                "source": result.source,
                "system": result.system,
                "scan_type": result.scan_type,
                "catalog_label": result.catalog_label,
                "catalog_hash": result.catalog_hash,
                "dat_path": str(dat_path),
                "started_at": started,
                "source_paths": [str(path) for path in sources],
                "machine_count_expected": len(games),
                "item_count_expected": total,
                "metadata": {
                    "validation": "expected_driven",
                    "persist_mode": "streaming",
                    "filters_applied": False,
                    "variant_selection": "selected_dat_is_authoritative",
                },
            })
            for game_name, items in games.items():
                if self._cancelled:
                    break
                self._scan_game(game_name, items, sources, result, stream)
                completed += len(items)
                if self.progress_callback:
                    self.progress_callback(completed, total)
                if completed == total or completed % 250 == 0:
                    stream.flush()

            self._write_jsonl(stream, {
                "record_type": "scan_end",
                "status": "cancelled" if self._cancelled else "completed",
                "finished_at": time.time(),
                "status_counts": dict(result.status_counts),
                "files_examined": result.files_examined,
                "archives_examined": result.archives_examined,
                "items_examined": result.items_examined,
                "errors": result.errors,
            })
            stream.flush()

        result.finished_at = time.time()
        return result

    def _scan_game(self, game_name: str, items: list[_ExpectedRom], sources: list[Path], result: ScanResult, stream) -> None:
        expected_by_name: dict[str, list[_ExpectedRom]] = {}
        for item in items:
            expected_by_name.setdefault(Path(item.rom_name).name.casefold(), []).append(item)

        occurrences: Counter[tuple[str, str, int, str]] = Counter()
        for source in sources:
            archive = source / f"{game_name}.zip"
            if archive.is_file():
                result.files_examined += 1
                result.archives_examined += 1
                self._scan_zip(archive, expected_by_name, occurrences, result, stream)

            # No-Intro DATs can also be represented as loose files. This path is
            # deterministic and does not enumerate the whole source tree.
            for item in items:
                loose = source / Path(item.rom_name).name
                if loose.is_file():
                    result.files_examined += 1
                    self._scan_loose(loose, item, occurrences, result, stream)

        for item in items:
            if occurrences[self._item_key(item)] == 0:
                self._emit(
                    self._evidence(item, "MISSING", message="Arquivo nao encontrado na fonte do scan."),
                    result,
                    stream,
                )

    def _scan_zip(self, archive: Path, expected_by_name, occurrences, result, stream) -> None:
        try:
            with zipfile.ZipFile(archive) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    candidates = expected_by_name.get(Path(info.filename).name.casefold())
                    if not candidates:
                        continue
                    result.items_examined += 1
                    for item in candidates:
                        key = self._item_key(item)
                        duplicate = occurrences[key] > 0
                        evidence = self._validate_zip_member(zf, info, item, archive, duplicate=duplicate)
                        if evidence is None:
                            continue
                        occurrences[key] += 1
                        self._emit(evidence, result, stream)
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            result.errors += 1
            self._log_error(result, stream, archive, exc)

    def _scan_loose(self, path: Path, item: _ExpectedRom, occurrences, result, stream) -> None:
        key = self._item_key(item)
        try:
            actual_size, crc, md5, sha1 = self._hash_file(path)
            duplicate = occurrences[key] > 0
            status = self._compare(item, actual_size, crc, md5, sha1)
            if status == "CURRENT" and duplicate:
                status = "DUPLICATE"
            evidence = self._evidence(
                item,
                status,
                actual_size=actual_size,
                actual_crc=crc,
                actual_md5=md5,
                actual_sha1=sha1,
                path=str(path),
            )
            occurrences[key] += 1
            self._emit(evidence, result, stream)
        except OSError as exc:
            result.errors += 1
            self._log_error(result, stream, path, exc)

    def _validate_zip_member(self, zf, info, item: _ExpectedRom, archive: Path, *, duplicate: bool) -> ScanEvidence:
        actual_size = int(info.file_size)
        actual_crc = f"{int(info.CRC) & 0xFFFFFFFF:08x}"
        expected_crc = item.crc.casefold()
        if actual_size != item.size or (expected_crc and actual_crc != expected_crc):
            return self._evidence(
                item,
                "WRONG",
                actual_size=actual_size,
                actual_crc=actual_crc,
                archive_path=str(archive),
                archive_member=info.filename,
                message="Tamanho/CRC divergente do DAT.",
            )

        md5 = ""
        sha1 = ""
        if item.md5 or item.sha1:
            md5, sha1 = self._hash_zip_member(zf, info)
        status = self._compare(item, actual_size, actual_crc, md5, sha1)
        if status == "CURRENT" and duplicate:
            status = "DUPLICATE"
        return self._evidence(
            item,
            status,
            actual_size=actual_size,
            actual_crc=actual_crc,
            actual_md5=md5,
            actual_sha1=sha1,
            archive_path=str(archive),
            archive_member=info.filename,
        )

    @staticmethod
    def _compare(item: _ExpectedRom, size: int, crc: str, md5: str, sha1: str) -> str:
        if size != item.size:
            return "WRONG"
        if item.crc and crc.casefold() != item.crc.casefold():
            return "WRONG"
        if item.md5 and md5.casefold() != item.md5.casefold():
            return "WRONG"
        if item.sha1 and sha1.casefold() != item.sha1.casefold():
            return "WRONG"
        return "CURRENT"

    @staticmethod
    def _item_key(item: _ExpectedRom) -> tuple[str, str, int, str]:
        return (item.game_name.casefold(), item.rom_name.casefold(), item.size, item.sha1.casefold())

    @staticmethod
    def _group_by_game(items: list[_ExpectedRom]) -> dict[str, list[_ExpectedRom]]:
        grouped: dict[str, list[_ExpectedRom]] = {}
        for item in items:
            grouped.setdefault(item.game_name, []).append(item)
        return grouped

    @staticmethod
    def _evidence(item: _ExpectedRom, status: str, **kwargs) -> ScanEvidence:
        return ScanEvidence(
            machine_name=item.game_name,
            rom_name=item.rom_name,
            status=status,
            expected_size=item.size,
            expected_crc=item.crc,
            expected_md5=item.md5,
            expected_sha1=item.sha1,
            message=kwargs.pop("message", ""),
            **kwargs,
        )

    @classmethod
    def _hash_zip_member(cls, zf, info) -> tuple[str, str]:
        md5 = hashlib.md5()
        sha1 = hashlib.sha1()
        with zf.open(info, "r") as handle:
            for chunk in iter(lambda: handle.read(cls.CHUNK_SIZE), b""):
                md5.update(chunk)
                sha1.update(chunk)
        return md5.hexdigest(), sha1.hexdigest()

    @classmethod
    def _hash_file(cls, path: Path) -> tuple[int, str, str, str]:
        crc = 0
        md5 = hashlib.md5()
        sha1 = hashlib.sha1()
        size = 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(cls.CHUNK_SIZE), b""):
                size += len(chunk)
                crc = zlib.crc32(chunk, crc)
                md5.update(chunk)
                sha1.update(chunk)
        return size, f"{crc & 0xFFFFFFFF:08x}", md5.hexdigest(), sha1.hexdigest()

    @classmethod
    def _sha256(cls, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(cls.CHUNK_SIZE), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _load_dat(path: Path) -> tuple[list[_ExpectedRom], dict[str, str]]:
        try:
            root = ElementTree.parse(path).getroot()
        except (OSError, ElementTree.ParseError) as exc:
            raise NoIntroScanError(f"DAT No-Intro invalido: {path}: {exc}") from exc

        header_node = root.find("header")
        header: dict[str, str] = {}
        if header_node is not None:
            for child in header_node:
                header[child.tag] = (child.text or "").strip()

        expected: list[_ExpectedRom] = []
        for game in root.findall(".//game"):
            game_name = str(game.attrib.get("name") or "").strip()
            if not game_name:
                continue
            for rom in game.findall("rom"):
                rom_name = str(rom.attrib.get("name") or "").strip()
                if not rom_name:
                    continue
                try:
                    size = int(rom.attrib.get("size") or 0)
                except ValueError:
                    size = 0
                expected.append(_ExpectedRom(
                    game_name=game_name,
                    rom_name=rom_name,
                    size=size,
                    crc=str(rom.attrib.get("crc") or "").casefold(),
                    md5=str(rom.attrib.get("md5") or "").casefold(),
                    sha1=str(rom.attrib.get("sha1") or "").casefold(),
                    status=str(rom.attrib.get("status") or "").casefold(),
                    fmt=str(rom.attrib.get("format") or "").strip(),
                ))
        return expected, header

    @staticmethod
    def _catalog_label(path: Path, header: dict[str, str]) -> str:
        match = re.search(r"(\d{8}-\d{6}|\d{8})", path.name)
        if match:
            return match.group(1)
        for key in ("date", "version"):
            value = header.get(key, "").strip()
            if value:
                return value
        return path.stem

    @staticmethod
    def _make_scan_id(profile) -> str:
        return f"scan_{time.strftime('%Y%m%d_%H%M%S')}_{abs(hash((profile.profile_id, time.time_ns()))) % 100000:05d}"

    @staticmethod
    def _write_jsonl(stream, record: dict) -> None:
        stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    def _emit(self, evidence: ScanEvidence, result: ScanResult, stream) -> None:
        result.status_counts[evidence.status] += 1
        result.evidence.append(evidence)
        self._write_jsonl(stream, {"record_type": "evidence", **self._serialize(evidence)})

    @staticmethod
    def _serialize(evidence: ScanEvidence) -> dict:
        return {
            "machine_name": evidence.machine_name, "rom_name": evidence.rom_name, "status": evidence.status,
            "expected_size": evidence.expected_size, "actual_size": evidence.actual_size,
            "expected_crc": evidence.expected_crc, "actual_crc": evidence.actual_crc,
            "expected_sha1": evidence.expected_sha1, "actual_sha1": evidence.actual_sha1,
            "expected_md5": evidence.expected_md5, "actual_md5": evidence.actual_md5,
            "path": evidence.path, "archive_path": evidence.archive_path, "archive_member": evidence.archive_member,
            "merge_name": evidence.merge_name, "optional": evidence.optional, "message": evidence.message,
            "error": evidence.error,
        }

    @staticmethod
    def _log_error(result: ScanResult, stream, path: Path, exc: Exception) -> None:
        result.status_counts["ERROR"] += 1
        NoIntroScanService._write_jsonl(stream, {
            "record_type": "error", "path": str(path), "error": f"{type(exc).__name__}: {exc}"
        })


__all__ = ["NoIntroScanError", "NoIntroScanService"]
