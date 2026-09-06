"""Arquivos brutos e imutáveis produzidos por uma auditoria."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..runtime.paths import scans_root


class ScanFileRepository:
    """Grava/localiza snapshots sem exigir todas as evidências em memória."""

    @staticmethod
    def _safe(value: str) -> str:
        value = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
        return value.strip("._-") or "unknown"

    @staticmethod
    def _mame_type_label(scan_type: str) -> str:
        return {"arcade": "Arcade", "software": "Software", "both": "Completa"}.get(str(scan_type).casefold(), str(scan_type))

    @classmethod
    def build_path(cls, result) -> Path:
        source = str(result.source)
        scan_type = str(getattr(result, "scan_type", "full"))
        if source.casefold() == "mame":
            root = scans_root() / "mame"
            version = cls._safe(result.catalog_label)
            type_label = cls._mame_type_label(scan_type)
            base = root / f"MAME - {version} - {type_label}.json"
            if not base.exists():
                return base
            existing = cls.load(base)
            if str(existing.get("scan_id", "")) == str(result.scan_id):
                return base
            return root / f"MAME - {version} - {type_label} - {cls._safe(result.scan_id)}.json"
        root = scans_root() / cls._safe(source.casefold())
        label = cls._safe(result.catalog_label)
        safe_type = cls._safe(scan_type)
        return root / f"{cls._safe(source)}_{label}_{safe_type}_{cls._safe(result.scan_id)}.json"

    @staticmethod
    def _evidence_payload(item) -> dict:
        if isinstance(item, dict):
            return item
        return {
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

    @classmethod
    def save(cls, result) -> Path:
        path = cls.build_path(result)
        path.parent.mkdir(parents=True, exist_ok=True)
        header = {
            "format": "SERM-SCAN-V1", "scan_id": result.scan_id, "profile_id": result.profile_id,
            "source": result.source, "system": result.system, "scan_type": getattr(result, "scan_type", "full"),
            "catalog_label": result.catalog_label, "catalog_hash": result.catalog_hash,
            "started_at": result.started_at, "finished_at": result.finished_at,
            "files_examined": result.files_examined, "archives_examined": result.archives_examined,
            "items_examined": result.items_examined, "errors": result.errors,
            "status_counts": dict(result.status_counts), "evidence": [],
        }
        stream_path = getattr(result, "evidence_stream_path", None)
        if stream_path and Path(stream_path).is_file():
            with path.open("w", encoding="utf-8", newline="\n") as output:
                prefix = json.dumps({k: v for k, v in header.items() if k != "evidence"}, ensure_ascii=False, separators=(",", ":"))
                output.write(prefix[:-1] + ',"evidence":[\n')
                first = True
                with Path(stream_path).open("r", encoding="utf-8") as source:
                    for line in source:
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if record.get("record_type") != "evidence":
                            continue
                        if not first:
                            output.write(",\n")
                        output.write(json.dumps({k: v for k, v in record.items() if k != "record_type"}, ensure_ascii=False, separators=(",", ":")))
                        first = False
                output.write("\n]}\n")
            return path

        with path.open("w", encoding="utf-8") as output:
            json.dump(header | {"evidence": [cls._evidence_payload(item) for item in result.evidence]}, output, indent=2, ensure_ascii=False)
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