# src/mame_set_builder/dataset_builder.py
import logging
from pathlib import Path
from .mame.executable import MAMEExecutable
from .mame.listxml import ListXMLStream
from .database.connection import Database
from .database.repositories.dataset_repository import DatasetRepository

logger = logging.getLogger(__name__)

class DatasetBuilder:
    def __init__(self, mame_path: Path, db_path: Path):
        self.mame = MAMEExecutable(mame_path)
        self.db = Database(db_path)
        self.dataset_repo = DatasetRepository(self.db)

    def build(self) -> None:
        if not self.mame.validate():
            raise ValueError(f"Executável inválido: {self.mame.path}")

        version = self.mame.get_version()
        logger.info(f"Versão do MAME detectada: {version}")

        existing = self.dataset_repo.get_by_version(version)
        if existing:
            logger.info(f"Dataset para versão {version} já existe (id={existing['id']}). Pulando.")
            return

        dataset_id = self.dataset_repo.create(version, str(self.mame.path))

        stream = ListXMLStream(self.mame)
        conn = self.db.connect()
        machine_count = 0

        for machine_data in stream.iter_machines():
            cur = conn.execute(
                """INSERT INTO machine
                (dataset_id, name, description, year, manufacturer, cloneof, romof,
                 sampleof, isbios, isdevice, ismechanical, runnable, sourcefile)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    dataset_id,
                    machine_data["name"],
                    machine_data["description"],
                    machine_data["year"],
                    machine_data["manufacturer"],
                    machine_data["cloneof"],
                    machine_data["romof"],
                    machine_data["sampleof"],
                    machine_data["isbios"],
                    machine_data["isdevice"],
                    machine_data["ismechanical"],
                    machine_data["runnable"],
                    machine_data["sourcefile"],
                )
            )
            machine_id = cur.lastrowid

            for rom in machine_data["roms"]:
                conn.execute(
                    """INSERT INTO rom
                    (machine_id, name, size, crc, sha1, merge, region, offset,
                     status, optional, bios)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        machine_id,
                        rom.get("name"),
                        rom.get("size"),
                        rom.get("crc"),
                        rom.get("sha1"),
                        rom.get("merge"),
                        rom.get("region"),
                        rom.get("offset"),
                        rom.get("status"),
                        1 if rom.get("optional") == "yes" else 0,
                        rom.get("bios"),
                    )
                )

            for disk in machine_data["disks"]:
                conn.execute(
                    """INSERT INTO disk
                    (machine_id, name, sha1, merge, region, index, writable, status, optional)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        machine_id,
                        disk.get("name"),
                        disk.get("sha1"),
                        disk.get("merge"),
                        disk.get("region"),
                        disk.get("index"),
                        1 if disk.get("writable") == "yes" else 0,
                        disk.get("status"),
                        1 if disk.get("optional") == "yes" else 0,
                    )
                )

            driver = machine_data.get("driver", {})
            if driver:
                conn.execute(
                    """INSERT OR REPLACE INTO driver
                    (machine_id, status, emulation, cocktail, savestate, requiresartwork,
                     unofficial, nosoundhardware, incomplete)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        machine_id,
                        driver.get("status"),
                        driver.get("emulation"),
                        1 if driver.get("cocktail") == "yes" else 0,
                        1 if driver.get("savestate") == "yes" else 0,
                        1 if driver.get("requiresartwork") == "yes" else 0,
                        1 if driver.get("unofficial") == "yes" else 0,
                        1 if driver.get("nosoundhardware") == "yes" else 0,
                        1 if driver.get("incomplete") == "yes" else 0,
                    )
                )

            machine_count += 1
            if machine_count % 100 == 0:
                conn.commit()
                logger.info(f"{machine_count} máquinas inseridas...")

        conn.commit()
        logger.info(f"Dataset para versão {version} finalizado. Máquinas inseridas: {machine_count}")

    def close(self):
        self.db.close()