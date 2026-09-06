"""Arquivos brutos e imutáveis produzidos por uma auditoria."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..runtime.paths import scans_root


class ScanFileRepository:
    """Grava e localiza o snapshot completo de cada scan."""

    @staticmethod
    def _safe(value: str) -> str:
        value = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
        return value.strip("._-") or "unknown"

    @classmethod
    def build_path(cls, result) -> Path:
        root = scans_root() / cls._safe(result.source.casefold())
        label = cls._safe(result.catalog_label)
        scan_type = cls._safe(getattr(result, "scan_type", "full"))
        return root / f"{cls._safe(result.source)}_{label}_{scan_type}_{cls._safe(result.scan_id)}.json"

    @classmethod
    def save(cls, result) -> Path:
        path = cls.build_path(result)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": "SERM-SCAN-V1",
            "scan_id": result.scan_id,
            "profile_id": result.profile_id,
            "source": result.source,
            "system": result.system,
            "scan_type": getattr(result, "scan_type", "full"),
            "catalog_label": result.catalog_label,
            "catalog_hash": result.catalog_hash,
            "started_at": result.started_at,
            "finished_at": result.finished_at,
            "files_examined": result.files_examined,
            "archives_examined": result.archives_examined,
            "items_examined": result.items_examined,
            "errors": result.errors,
            "status_counts": dict(result.status_counts),
            "evidence": [
                {
                    "machine_name": item.machine_name,
                    "rom_name": item.rom_name,
                    "status": item.status,
                    "expected_size": item.expected_size,
                    "actual_size": item.actual_size,
                    "expected_crc": item.expected_crc,
                    "actual_crc": item.actual_crc,
                    "expected_sha1": item.expected_sha1,
                    "actual_sha1": item.actual_sha1,
                    "expected_md5": item.expected_md5,
                    "actual_md5": item.actual_md5,
                    "path": item.path,
                    "archive_path": item.archive_path,
                    "archive_member": item.archive_member,
                    "merge_name": item.merge_name,
                    "optional": item.optional,
                    "message": item.message,
                    "error": item.error,
                    "categories": list(getattr(item, "categories", ())),
                    "cloneof": getattr(item, "cloneof", None),
                    "isbios": getattr(item, "isbios", None),
                    "isdevice": getattr(item, "isdevice", None),
                    "ismechanical": getattr(item, "ismechanical", None),
                    "runnable": getattr(item, "runnable", None),
                }
                for item in result.evidence
            ],
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> dict:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def latest_path(cls, scan_id: str) -> Path | None:
        root = scans_root()
        if not root.is_dir():
            return None
        matches = list(root.rglob(f"*_{scan_id}.json"))
        return matches[0] if matches else None


__all__ = ["ScanFileRepository"]
