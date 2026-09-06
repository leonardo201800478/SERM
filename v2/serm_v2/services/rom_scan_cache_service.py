"""Cache físico seguro para acelerar scans MAME sem pular validação.

O cache só é reutilizado quando o ZIP físico não mudou e o catálogo esperado
continua sendo o mesmo. Assim, a aceleração não altera a semântica do scan:
ela apenas evita reler um arquivo que já foi validado anteriormente.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..runtime.paths import scans_root
from .rom_scan_service import ScanEvidence, _MachineResult


class RomScanCacheService:
    """Cache persistente por machine/ZIP com escrita atômica."""

    FORMAT = "SERM-ROM-CACHE-V1"

    @staticmethod
    def _root() -> Path:
        root = scans_root() / "cache" / "mame"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @classmethod
    def _path(cls, machine: str, catalog_hash: str) -> Path:
        safe_machine = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in machine)
        safe_hash = "".join(ch for ch in catalog_hash if ch.isalnum())[:64] or "catalog"
        return cls._root() / f"{safe_hash}_{safe_machine}.json"

    @staticmethod
    def _file_signature(path: Path) -> dict[str, Any] | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        if not path.is_file():
            return None
        return {
            "path": str(path.resolve()),
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }

    @classmethod
    def load(
        cls,
        machine: str,
        catalog_hash: str,
        zip_path: Path,
    ) -> _MachineResult | None:
        """Retorna resultado somente se o ZIP tiver exatamente a mesma assinatura."""
        signature = cls._file_signature(zip_path)
        if signature is None:
            return None
        path = cls._path(machine, catalog_hash)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            return None
        if payload.get("format") != cls.FORMAT:
            return None
        if str(payload.get("machine")) != machine:
            return None
        if str(payload.get("catalog_hash")) != catalog_hash:
            return None
        if payload.get("zip") != signature:
            return None
        try:
            records = [ScanEvidence(**item) for item in payload.get("records", [])]
            return _MachineResult(
                machine=machine,
                records=records,
                files_examined=int(payload.get("files_examined", 1)),
                archives_examined=int(payload.get("archives_examined", 1)),
                items_examined=int(payload.get("items_examined", 0)),
                bytes_read=0,
                errors=0,
            )
        except (TypeError, ValueError):
            return None

    @classmethod
    def save(
        cls,
        machine: str,
        catalog_hash: str,
        zip_path: Path,
        result: _MachineResult,
    ) -> None:
        """Persiste apenas resultados sem erro; falhas nunca entram no cache."""
        if result.errors or not zip_path.is_file():
            return
        signature = cls._file_signature(zip_path)
        if signature is None:
            return
        path = cls._path(machine, catalog_hash)
        target = path.with_suffix(path.suffix + ".tmp")
        payload = {
            "format": cls.FORMAT,
            "machine": machine,
            "catalog_hash": catalog_hash,
            "zip": signature,
            "files_examined": result.files_examined,
            "archives_examined": result.archives_examined,
            "items_examined": result.items_examined,
            "records": [asdict(record) for record in result.records],
        }
        try:
            with target.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
                stream.write("\n")
                stream.flush()
            os.replace(target, path)
        except OSError:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass


__all__ = ["RomScanCacheService"]
