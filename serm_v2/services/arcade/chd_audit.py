"""Auditoria física de CHDs do Arcade Studio V2.

A auditoria é orientada pelo catálogo MAME e pela identidade lógica do disco.
O arquivo .chd nunca é identificado pelo SHA-1 do contêiner: para CHDs que
expõem SHA-1, o campo ``rawsha1`` do cabeçalho é comparado ao ListXML.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ..chd_header import ChdFormatError, ChdHeaderReader


@dataclass(frozen=True, slots=True)
class ChdAuditRecord:
    """Uma ocorrência física ou catalogada na auditoria."""

    status: str
    path: str | None = None
    machine_name: str | None = None
    disk_name: str | None = None
    expected_sha1: str | None = None
    actual_sha1: str | None = None
    expected_md5: str | None = None
    actual_md5: str | None = None
    version: int | None = None
    logical_bytes: int | None = None
    file_size: int | None = None
    parent_sha1: str | None = None
    message: str = ""


@dataclass(frozen=True, slots=True)
class ChdAuditResult:
    """Resultado completo e determinístico de uma auditoria de CHDs."""

    records: tuple[ChdAuditRecord, ...]
    files_scanned: int
    valid_files: int
    matched_files: int
    missing_disks: int
    ambiguous_disks: int
    invalid_files: int
    orphan_files: int


class ArcadeChdAuditService:
    """Varre CHDs e cruza sua identidade lógica com o catálogo MAME."""

    def __init__(self, reader: ChdHeaderReader | None = None) -> None:
        self.reader = reader or ChdHeaderReader()

    def audit(
        self,
        *,
        source: Path,
        database: Path,
        import_id: int | None = None,
    ) -> ChdAuditResult:
        source = source.expanduser().resolve()
        if not source.is_dir():
            raise NotADirectoryError(f"Diretório de CHDs não encontrado: {source}")

        expected = self._load_expected(database, import_id)
        physical: list[ChdAuditRecord] = []
        by_sha1: dict[str, list[ChdAuditRecord]] = {}
        by_md5: dict[str, list[ChdAuditRecord]] = {}
        files_scanned = valid_files = invalid_files = 0

        for path in sorted(source.rglob("*.chd"), key=lambda item: str(item).casefold()):
            files_scanned += 1
            try:
                header = self.reader.read(path)
            except (OSError, ChdFormatError) as exc:
                invalid_files += 1
                physical.append(
                    ChdAuditRecord(
                        status="INVALID",
                        path=str(path),
                        file_size=path.stat().st_size if path.exists() else None,
                        message=str(exc),
                    )
                )
                continue

            valid_files += 1
            record = ChdAuditRecord(
                status="UNMATCHED",
                path=str(path),
                actual_sha1=header.raw_sha1 or None,
                actual_md5=header.md5 or None,
                version=header.version,
                logical_bytes=header.logical_bytes,
                file_size=header.file_size,
                parent_sha1=header.parent_sha1 or None,
            )
            physical.append(record)
            if header.raw_sha1:
                by_sha1.setdefault(header.raw_sha1.casefold(), []).append(record)
            if header.md5:
                by_md5.setdefault(header.md5.casefold(), []).append(record)

        records: list[ChdAuditRecord] = []
        matched_paths: set[str] = set()
        matched_files = ambiguous = missing = 0

        for machine, disk, sha1, md5 in expected:
            candidates: list[ChdAuditRecord] = []
            match_kind = "SHA1"
            if sha1:
                candidates = by_sha1.get(sha1.casefold(), [])
            elif md5:
                candidates = by_md5.get(md5.casefold(), [])
                match_kind = "MD5"

            if len(candidates) == 1:
                candidate = candidates[0]
                matched_files += 1
                matched_paths.add(candidate.path or "")
                records.append(
                    ChdAuditRecord(
                        status="OK",
                        path=candidate.path,
                        machine_name=machine,
                        disk_name=disk,
                        expected_sha1=sha1,
                        actual_sha1=candidate.actual_sha1,
                        expected_md5=md5,
                        actual_md5=candidate.actual_md5,
                        version=candidate.version,
                        logical_bytes=candidate.logical_bytes,
                        file_size=candidate.file_size,
                        parent_sha1=candidate.parent_sha1,
                        message=f"Identidade lógica confirmada por {match_kind}.",
                    )
                )
            elif len(candidates) > 1:
                ambiguous += 1
                records.append(
                    ChdAuditRecord(
                        status="AMBIGUOUS",
                        machine_name=machine,
                        disk_name=disk,
                        expected_sha1=sha1,
                        expected_md5=md5,
                        message=f"{len(candidates)} CHDs físicos possuem a mesma identidade lógica.",
                    )
                )
            else:
                missing += 1
                records.append(
                    ChdAuditRecord(
                        status="MISSING",
                        machine_name=machine,
                        disk_name=disk,
                        expected_sha1=sha1,
                        expected_md5=md5,
                        message="CHD catalogado não encontrado na origem física.",
                    )
                )

        for item in physical:
            if item.path not in matched_paths and item.status != "INVALID":
                records.append(
                    ChdAuditRecord(
                        status="ORPHAN",
                        path=item.path,
                        actual_sha1=item.actual_sha1,
                        actual_md5=item.actual_md5,
                        version=item.version,
                        logical_bytes=item.logical_bytes,
                        file_size=item.file_size,
                        parent_sha1=item.parent_sha1,
                        message="CHD válido sem correspondência no catálogo importado.",
                    )
                )
            elif item.status == "INVALID":
                records.append(item)

        return ChdAuditResult(
            records=tuple(records),
            files_scanned=files_scanned,
            valid_files=valid_files,
            matched_files=matched_files,
            missing_disks=missing,
            ambiguous_disks=ambiguous,
            invalid_files=invalid_files,
            orphan_files=sum(record.status == "ORPHAN" for record in records),
        )

    @staticmethod
    def _load_expected(
        database: Path,
        import_id: int | None,
    ) -> list[tuple[str, str, str | None, str | None]]:
        with sqlite3.connect(database) as connection:
            if import_id is None:
                row = connection.execute(
                    "SELECT id FROM mame_listxml_import WHERE status='completed' "
                    "ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if row is None:
                    raise RuntimeError("Nenhuma importação MAME concluída.")
                import_id = int(row[0])
            rows = connection.execute(
                """
                SELECT m.name, d.name, d.sha1, d.md5
                  FROM mame_disk d
                  JOIN mame_machine m ON m.id = d.machine_id
                 WHERE m.import_id = ?
                 ORDER BY m.name, d.name
                """,
                (import_id,),
            ).fetchall()
        return [
            (str(machine), str(disk), sha1 or None, md5 or None)
            for machine, disk, sha1, md5 in rows
        ]


__all__ = ["ArcadeChdAuditService", "ChdAuditRecord", "ChdAuditResult"]
