"""Validação de CHDs do catálogo MAME durante o scan de ROMs."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from .rom_scan_service import ScanEvidence, _MachineResult


class MameChdScanService:
    """Localiza CHDs esperados e valida exclusivamente SHA1/MD5."""

    CHUNK_SIZE = 1024 * 1024

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
                actual_sha1, actual_md5, size = self._hash_file(path)
                unit.bytes_read += size
            except OSError as exc:
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
                        message="Falha ao calcular hash do CHD",
                        error=str(exc),
                    )
                )
                continue

            sha1_ok = not expected_sha1 or actual_sha1 == expected_sha1
            md5_ok = not expected_md5 or actual_md5 == expected_md5
            has_expected_hash = bool(expected_sha1 or expected_md5)
            status = "CURRENT" if has_expected_hash and sha1_ok and md5_ok else "WRONG"

            if status == "CURRENT":
                message = "CHD encontrado; SHA1/MD5 correspondentes"
            else:
                message = "CHD encontrado, mas SHA1/MD5 divergem"

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
    def _load_disks(
        database: Path, import_id: int, machine: str
    ) -> list[sqlite3.Row]:
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
    def _find_chd(
        machine: str, disk_name: str, sources: list[Path]
    ) -> Path | None:
        filename = Path(disk_name).name
        if not filename.casefold().endswith(".chd"):
            filename = f"{filename}.chd"

        for source in sources:
            machine_dir = source / machine
            candidate = machine_dir / filename
            if candidate.is_file():
                return candidate

        return None

    @classmethod
    def _hash_file(cls, path: Path) -> tuple[str, str, int]:
        sha1 = hashlib.sha1(usedforsecurity=False)
        md5 = hashlib.md5(usedforsecurity=False)
        total = 0
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(cls.CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                sha1.update(chunk)
                md5.update(chunk)
        return sha1.hexdigest(), md5.hexdigest(), total

    @staticmethod
    def _cancelled(unit: _MachineResult) -> bool:
        # O scanner principal continua responsável pelo cancelamento global.
        return False


__all__ = ["MameChdScanService"]
