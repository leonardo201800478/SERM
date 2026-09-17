"""Utilitários para preservar e reiniciar checkpoints de scans MAME."""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..runtime.paths import scans_root
from .mame_scan_settings_service import MameScanSettingsService


class ScanCheckpointService:
    """Localiza checkpoints de scan e arquiva um stream antes de um novo scan."""

    @staticmethod
    def _stream_root() -> Path:
        root = scans_root() / "streaming"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def _checkpoint_path(path: Path) -> Path:
        return path.with_suffix(".checkpoint.json")

    @classmethod
    def _matches(cls, path: Path, profile) -> bool:
        try:
            with path.open("r", encoding="utf-8") as stream:
                header = json.loads(stream.readline())
        except (OSError, ValueError):
            return False
        if header.get("record_type") != "header":
            return False
        scan_type = MameScanSettingsService.load(str(profile.profile_id))
        wanted = [str(Path(p).expanduser().resolve()) for p in profile.source_directories]
        return (
            str(header.get("profile_id")) == str(profile.profile_id)
            and str(header.get("source")).casefold() == str(profile.source).casefold()
            and str(header.get("system")) == str(profile.system)
            and str(header.get("scan_type")) == str(scan_type)
            and header.get("source_paths") == wanted
        )

    @classmethod
    def _has_checkpoint(cls, path: Path) -> bool:
        checkpoint = cls._checkpoint_path(path)
        try:
            if checkpoint.is_file():
                payload = json.loads(checkpoint.read_text(encoding="utf-8"))
                if (
                    payload.get("format") == "SERM-SCAN-CHECKPOINT-V2"
                    and int(payload.get("completed_count", 0)) > 0
                ):
                    return True
        except (OSError, ValueError, TypeError):
            pass
        # Compatibilidade com streams antigos que gravavam machine_complete.
        try:
            with path.open("r", encoding="utf-8") as stream:
                next(stream, None)
                for raw in stream:
                    try:
                        record = json.loads(raw)
                    except ValueError:
                        continue
                    if record.get("record_type") == "machine_complete":
                        return True
        except OSError:
            return False
        return False

    @classmethod
    def latest(cls, profile) -> Path | None:
        candidates = sorted(
            (p for p in cls._stream_root().glob("scan_*.jsonl") if cls._matches(p, profile)),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for path in candidates:
            if cls._has_checkpoint(path):
                return path
        return None

    @classmethod
    def _checkpoint_summary(cls, path: Path) -> dict[str, object] | None:
        checkpoint = cls._checkpoint_path(path)
        if not checkpoint.is_file():
            return None
        try:
            payload = json.loads(checkpoint.read_text(encoding="utf-8"))
            if payload.get("format") != "SERM-SCAN-CHECKPOINT-V2":
                return None
            return {
                "path": path,
                "completed": int(payload.get("completed_count", 0)),
                "last_machine": str((payload.get("completed_machines") or [""])[-1]),
                "status": "cancelado" if payload.get("cancelled") else "incompleto",
            }
        except (OSError, ValueError, TypeError, IndexError):
            return None

    @staticmethod
    def _legacy_summary(path: Path) -> dict[str, object] | None:
        completed = 0
        last_machine = ""
        status = "incompleto"
        try:
            with path.open("r", encoding="utf-8") as stream:
                next(stream, None)
                for raw in stream:
                    try:
                        record = json.loads(raw)
                    except ValueError:
                        continue
                    if record.get("record_type") == "machine_complete":
                        completed += 1
                        last_machine = str(record.get("machine") or last_machine)
                    elif record.get("record_type") == "scan_end":
                        status = str(record.get("status") or status)
        except OSError:
            return None
        return {
            "path": path,
            "completed": completed,
            "last_machine": last_machine,
            "status": status,
        }

    @classmethod
    def summary(cls, profile) -> dict[str, object] | None:
        path = cls.latest(profile)
        if path is None:
            return None
        return cls._checkpoint_summary(path) or cls._legacy_summary(path)

    @classmethod
    def archive_latest(cls, profile) -> Path | None:
        path = cls.latest(profile)
        if path is None:
            return None
        stamp = time.strftime("%Y%m%d_%H%M%S")
        target = path.with_name(f"checkpoint_{stamp}_{path.name}")
        path.rename(target)
        sidecar = cls._checkpoint_path(path)
        if sidecar.is_file():
            sidecar.rename(cls._checkpoint_path(target))
        return target


__all__ = ["ScanCheckpointService"]
