"""Leitura do catálogo Arcade normalizado do SERM V2."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Final

from ..domain.arcade import ArcadeDisplay, ArcadeGame, ArcadeRom, MachineKind
from ..domain.arcade_catalog import ArcadeCatalog
from ..runtime.paths import database_path


class ArcadeCatalogError(RuntimeError):
    """Erro ao consultar o catálogo Arcade persistido."""


class SqliteArcadeCatalog(ArcadeCatalog):
    """Implementação somente-leitura de ArcadeCatalog sobre SQLite."""

    MACHINE_BATCH_SIZE: Final[int] = 500

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else database_path()

    def count(self) -> int:
        """Retorna a quantidade de máquinas da última importação concluída."""
        with self._connect() as db:
            import_id = self._latest_import_id(db)
            if import_id is None:
                return 0
            row = db.execute(
                "SELECT COUNT(*) FROM mame_machine WHERE import_id=?", (import_id,)
            ).fetchone()
            return int(row[0]) if row else 0

    def get_game(self, name: str) -> ArcadeGame | None:
        """Carrega uma máquina pelo nome na última importação concluída."""
        if not name:
            return None
        with self._connect() as db:
            import_id = self._latest_import_id(db)
            if import_id is None:
                return None
            row = db.execute(
                """SELECT id,name,description,year,manufacturer,sourcefile,
                          cloneof,romof,isbios,isdevice,ismechanical,runnable
                   FROM mame_machine
                   WHERE import_id=? AND name=?""",
                (import_id, name),
            ).fetchone()
            if row is None:
                return None
            return self._load_game(db, row)

    def iter_games(self) -> Iterator[ArcadeGame]:
        """Itera pelo catálogo em lotes, evitando N+1 consultas."""
        with self._connect() as db:
            import_id = self._latest_import_id(db)
            if import_id is None:
                return
            offset = 0
            while True:
                rows = db.execute(
                    """SELECT id,name,description,year,manufacturer,sourcefile,
                              cloneof,romof,isbios,isdevice,ismechanical,runnable
                       FROM mame_machine
                       WHERE import_id=?
                       ORDER BY name
                       LIMIT ? OFFSET ?""",
                    (import_id, self.MACHINE_BATCH_SIZE, offset),
                ).fetchall()
                if not rows:
                    return
                machine_ids = [int(row[0]) for row in rows]
                roms = self._load_roms(db, machine_ids)
                displays = self._load_displays(db, machine_ids)
                for row in rows:
                    machine_id = int(row[0])
                    yield self._map_game(row, roms.get(machine_id, ()), displays.get(machine_id, ()))
                offset += len(rows)
                if len(rows) < self.MACHINE_BATCH_SIZE:
                    return

    def _load_game(self, db: sqlite3.Connection, row: sqlite3.Row) -> ArcadeGame:
        """Carrega ROMs e displays de uma única máquina."""
        machine_id = int(row[0])
        roms = self._load_roms(db, [machine_id]).get(machine_id, ())
        displays = self._load_displays(db, [machine_id]).get(machine_id, ())
        return self._map_game(row, roms, displays)

    @staticmethod
    def _load_roms(db: sqlite3.Connection, machine_ids: list[int]) -> dict[int, tuple[ArcadeRom, ...]]:
        """Carrega ROMs para um lote de máquinas."""
        if not machine_ids:
            return {}
        placeholders = ",".join("?" for _ in machine_ids)
        result: dict[int, list[ArcadeRom]] = {}
        for row in db.execute(
            f"""SELECT machine_id,name,size,crc,sha1,md5,merge,region
                FROM mame_rom
                WHERE machine_id IN ({placeholders})
                ORDER BY machine_id,id""",
            machine_ids,
        ):
            result.setdefault(int(row[0]), []).append(
                ArcadeRom(
                    name=str(row[1]),
                    size=int(row[2]) if row[2] is not None else None,
                    crc=row[3], sha1=row[4], md5=row[5], merge=row[6], region=row[7],
                )
            )
        return {machine_id: tuple(values) for machine_id, values in result.items()}

    @staticmethod
    def _load_displays(db: sqlite3.Connection, machine_ids: list[int]) -> dict[int, tuple[ArcadeDisplay, ...]]:
        """Carrega displays para um lote de máquinas."""
        if not machine_ids:
            return {}
        placeholders = ",".join("?" for _ in machine_ids)
        result: dict[int, list[ArcadeDisplay]] = {}
        for row in db.execute(
            f"""SELECT machine_id,tag,type,width,height,refresh_hz,rotate
                FROM mame_display
                WHERE machine_id IN ({placeholders})
                ORDER BY machine_id,id""",
            machine_ids,
        ):
            result.setdefault(int(row[0]), []).append(
                ArcadeDisplay(
                    tag=row[1], display_type=row[2],
                    width=int(row[3]) if row[3] is not None else None,
                    height=int(row[4]) if row[4] is not None else None,
                    refresh_hz=float(row[5]) if row[5] is not None else None,
                    rotate=row[6],
                )
            )
        return {machine_id: tuple(values) for machine_id, values in result.items()}

    @staticmethod
    def _map_game(
        row: sqlite3.Row,
        roms: tuple[ArcadeRom, ...],
        displays: tuple[ArcadeDisplay, ...],
    ) -> ArcadeGame:
        """Converte uma linha relacional no agregado de domínio."""
        return ArcadeGame(
            name=str(row[1]), description=row[2], year=row[3], manufacturer=row[4],
            sourcefile=row[5], cloneof=row[6], romof=row[7],
            machine_kind=SqliteArcadeCatalog._machine_kind(row[8], row[9], row[10], row[11]),
            runnable=SqliteArcadeCatalog._flag(row[11], default=True),
            roms=roms, displays=displays,
        )

    @staticmethod
    def _machine_kind(isbios: object, isdevice: object, ismechanical: object, runnable: object) -> MachineKind:
        """Classifica a entrada segundo os atributos do ListXML."""
        if SqliteArcadeCatalog._flag(isbios):
            return MachineKind.BIOS
        if SqliteArcadeCatalog._flag(isdevice):
            return MachineKind.DEVICE
        if SqliteArcadeCatalog._flag(ismechanical):
            return MachineKind.MECHANICAL
        if not SqliteArcadeCatalog._flag(runnable, default=True):
            return MachineKind.NON_RUNNABLE
        return MachineKind.SYSTEM

    @staticmethod
    def _flag(value: object, *, default: bool = False) -> bool:
        """Interpreta flags textuais sem tratar qualquer string como verdadeira."""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def _latest_import_id(db: sqlite3.Connection) -> int | None:
        """Obtém a importação concluída mais recente."""
        row = db.execute(
            """SELECT id FROM mame_listxml_import
               WHERE status='completed' ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        return int(row[0]) if row else None

    def _connect(self) -> sqlite3.Connection:
        """Abre SQLite em modo somente leitura."""
        if not self.db_path.is_file():
            raise ArcadeCatalogError(f"Banco SERM não encontrado: {self.db_path}")
        db = sqlite3.connect(f"file:{self.db_path.as_posix()}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        return db


__all__ = ["ArcadeCatalogError", "SqliteArcadeCatalog"]
