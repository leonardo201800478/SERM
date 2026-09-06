"""Relatórios e invariantes do catálogo MAME persistido."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..runtime.paths import database_path


class MameCatalogReport:
    """Consulta métricas do último ListXML e dos Machine Display Profiles."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or database_path()

    def summary(self) -> dict[str, int]:
        """Retorna contagens necessárias para validar o primeiro catálogo."""
        with sqlite3.connect(self.db_path) as db:
            latest = db.execute(
                "SELECT id FROM mame_listxml_import ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if latest is None:
                return {
                    "machine_entries": 0,
                    "runnable_systems": 0,
                    "devices": 0,
                    "displays": 0,
                    "profiles": 0,
                    "missing_profiles": 0,
                }
            import_id = int(latest[0])
            machine_entries = int(
                db.execute(
                    "SELECT COUNT(*) FROM mame_machine WHERE import_id=?", (import_id,)
                ).fetchone()[0]
            )
            runnable = int(
                db.execute(
                    "SELECT COUNT(*) FROM mame_machine WHERE import_id=? AND COALESCE(runnable,'yes')='yes' AND COALESCE(isdevice,'no')='no'",
                    (import_id,),
                ).fetchone()[0]
            )
            devices = int(
                db.execute(
                    "SELECT COUNT(*) FROM mame_machine WHERE import_id=? AND isdevice='yes'",
                    (import_id,),
                ).fetchone()[0]
            )
            displays = int(
                db.execute(
                    "SELECT COUNT(*) FROM mame_display d JOIN mame_machine m ON m.id=d.machine_id WHERE m.import_id=?",
                    (import_id,),
                ).fetchone()[0]
            )
            profiles = int(
                db.execute(
                    "SELECT COUNT(*) FROM mame_machine_display_profile p JOIN mame_machine m ON m.id=p.machine_id WHERE m.import_id=?",
                    (import_id,),
                ).fetchone()[0]
            )
            missing = int(
                db.execute(
                    "SELECT COUNT(*) FROM mame_machine_display_profile p JOIN mame_machine m ON m.id=p.machine_id WHERE m.import_id=? AND p.status='missing'",
                    (import_id,),
                ).fetchone()[0]
            )
            return {
                "machine_entries": machine_entries,
                "runnable_systems": runnable,
                "devices": devices,
                "displays": displays,
                "profiles": profiles,
                "missing_profiles": missing,
            }

    def validate(self, expected_machine_entries: int | None = None) -> list[str]:
        """Retorna falhas de consistência sem mascarar diferenças reais."""
        summary = self.summary()
        errors: list[str] = []
        if (
            expected_machine_entries is not None
            and summary["machine_entries"] != expected_machine_entries
        ):
            errors.append(
                f"machine_entries={summary['machine_entries']} != esperado={expected_machine_entries}"
            )
        if summary["profiles"] < summary["displays"]:
            errors.append("Há displays sem Machine Display Profile.")
        return errors


__all__ = ["MameCatalogReport"]
