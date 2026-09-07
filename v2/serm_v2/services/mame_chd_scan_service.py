"""Validação de CHDs do catálogo MAME durante o scan de ROMs."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .chd_header import ChdFormatError, ChdHeaderReader
from .rom_scan_service import ScanEvidence, _MachineResult


class MameChdScanService:
    """Localiza CHDs e valida a identidade lógica gravada no cabeçalho.

    O SHA-1 do arquivo ``.chd`` não é comparado ao ListXML. O ListXML usa a
    identidade do conteúdo lógico do disco; no CHD essa identidade está no
    campo ``rawsha1`` do cabeçalho. Para V1/V2, que não possuem SHA-1, o MD5
    lógico é usado quando o catálogo o fornece.
    """

    def __init__(self) -> None:
        self.header_reader = ChdHeaderReader()

    def scan_machine(
        self,
        *,
        machine: str,
        database: Path,
        import_id: int,
        sources: list[Path],
        unit: _MachineResult,
    ) -> None:
        disks = self._load_disks(database, import_id, machine)
        if not disks:
            return

        for disk in disks:
            if self._cancelled(unit):
                return

            disk_name = str(disk["name"] or "").strip()
            if not disk_name:
                continue

            expected_sha1 = str(disk["sha1"] or "").strip().casefold()
            expected_md5 = str(disk["md5"] or "").strip().casefold()
            optional = str(disk["optional"] or "").strip().casefold() in {
                "yes",
                "true",
                "1",
            }

            path = self._find_chd(machine, disk_name, sources)
            if path is None:
                unit.records.append(
                    ScanEvidence(
                        machine_name=machine,
                        rom_name=disk_name,
                        status="MISSING",
                        expected_sha1=expected_sha1,
                        expected_md5=expected_md5,
                        optional=optional,
                        message="CHD não encontrada no diretório da machine",
                    )
                )
                continue

            unit.files_examined += 1
            unit.items_examined += 1
            try:
                header = self.header_reader.read(path)
                unit.bytes_read += min(path.stat().st_size, 4096)
            except (OSError, ChdFormatError) as exc:
                unit.errors += 1
                unit.records.append(
                    ScanEvidence(
                        machine_name=machine,
                        rom_name=disk_name,
                        status="ERROR",
                        expected_sha1=expected_sha1,
                        expected_md5=expected_md5,
                        path=str(path),
                        optional=optional,
                        message="Cabeçalho CHD inválido ou inacessível",
                        error=str(exc),
                    )
                )
                continue

            actual_sha1 = (header.raw_sha1 or "").casefold()
            actual_md5 = (header.md5 or "").casefold()
            sha1_ok = bool(expected_sha1) and actual_sha1 == expected_sha1
            md5_ok = bool(expected_md5) and actual_md5 == expected_md5

            if expected_sha1:
                status = "CURRENT" if sha1_ok else "WRONG"
                message = (
                    "CHD encontrado; Data SHA1 do cabeçalho corresponde ao ListXML"
                    if sha1_ok
                    else "CHD encontrado, mas Data SHA1 diverge do ListXML"
                )
            elif expected_md5 and header.md5:
                status = "CURRENT" if md5_ok else "WRONG"
                message = (
                    "CHD encontrado; MD5 lógico corresponde ao ListXML"
                    if md5_ok
                    else "CHD encontrado, mas MD5 lógico diverge do ListXML"
                )
            else:
                status = "UNVERIFIABLE"
                message = (
                    "CHD válido, mas o formato não expõe o hash exigido pelo catálogo"
                )

            unit.records.append(
                ScanEvidence(
                    machine_name=machine,
                    rom_name=disk_name,
                    status=status,
                    expected_sha1=expected_sha1,
                    actual_sha1=actual_sha1,
                    expected_md5=expected_md5,
                    actual_md5=actual_md5,
                    path=str(path),
                    optional=optional,
                    message=message,
                )
            )

    @staticmethod
    def _load_disks(database: Path, import_id: int, machine: str) -> list[sqlite3.Row]:
        with sqlite3.connect(database) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(
                """
                SELECT d.name, d.md5, d.sha1, d.merge, d.optional
                  FROM mame_disk d
                  JOIN mame_machine m ON m.id = d.machine_id
                 WHERE m.import_id = ? AND m.name = ?
                 ORDER BY d.name
                """,
                (import_id, machine),
            ).fetchall()

    @staticmethod
    def _find_chd(machine: str, disk_name: str, sources: list[Path]) -> Path | None:
        filename = Path(disk_name).name
        if not filename.casefold().endswith(".chd"):
            filename = f"{filename}.chd"

        for source in sources:
            machine_dir = source / machine
            candidate = machine_dir / filename
            if candidate.is_file():
                return candidate

        return None

    @staticmethod
    def _cancelled(unit: _MachineResult) -> bool:
        return False


__all__ = ["MameChdScanService"]
