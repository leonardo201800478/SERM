"""Configuração do tipo de auditoria MAME.

O tipo de scan é metadado da auditoria, não um filtro. Ele define qual universo
catalográfico deve ser materializado no arquivo bruto do scan.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from ..runtime.paths import data_root

SETTINGS_FILE: Final[Path] = data_root() / "mame_scan_settings.json"
SCAN_TYPES: Final[dict[str, str]] = {
    "arcade": "Arcade",
    "software": "Software",
    "both": "Completa",
}


class MameScanSettingsService:
    @staticmethod
    def _read() -> dict[str, str]:
        try:
            raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}

    @classmethod
    def load(cls, profile_id: str) -> str:
        value = cls._read().get(str(profile_id), "arcade")
        return value if value in SCAN_TYPES else "arcade"

    @classmethod
    def save(cls, profile_id: str, scan_type: str) -> None:
        if scan_type not in SCAN_TYPES:
            raise ValueError(f"Tipo de scan MAME inválido: {scan_type}")
        data = cls._read()
        data[str(profile_id)] = scan_type
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def delete(cls, profile_id: str) -> None:
        data = cls._read()
        data.pop(str(profile_id), None)
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


__all__ = ["MameScanSettingsService", "SCAN_TYPES"]
