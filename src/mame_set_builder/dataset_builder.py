"""
Orquestrador principal da Fase 2.
Detecta o MAME, executa -listxml, faz parsing streaming e insere no SQLite,
incluindo todas as novas tabelas.
"""

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
            # --- Inserir máquina ---
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
                    1 if machine_data["isbios"] else 0,
                    1 if machine_data["isdevice"] else 0,
                    1 if machine_data["ismechanical"] else 0,
                    1 if machine_data["runnable"] else 0,
                    machine_data["sourcefile"],
                )
            )
            machine_id = cur.lastrowid

            # --- ROMs ---
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

            # --- Disks ---
            for disk in machine_data["disks"]:
                conn.execute(
                    """INSERT INTO disk
                    (machine_id, name, sha1, merge, region, disk_index, writable, status, optional)
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

            # --- Driver ---
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

            # --- Input ---
            if machine_data.get("input"):
                input_data = machine_data["input"]
                cur = conn.execute(
                    """INSERT INTO input
                    (machine_id, service, tilt, coin)
                    VALUES (?, ?, ?, ?)""",
                    (
                        machine_id,
                        1 if input_data.get("service") == "yes" else 0,
                        1 if input_data.get("tilt") == "yes" else 0,
                        1 if input_data.get("coin") == "yes" else 0,
                    )
                )
                input_id = cur.lastrowid

                # Portas de entrada
                for port in machine_data.get("input_ports", []):
                    cur = conn.execute(
                        """INSERT INTO input_port
                        (input_id, tag, type, mask, defvalue)
                        VALUES (?, ?, ?, ?, ?)""",
                        (
                            input_id,
                            port.get("tag"),
                            port.get("type"),
                            port.get("mask"),
                            port.get("defvalue"),
                        )
                    )
                    port_id = cur.lastrowid

                    # Dip switches desta porta
                    for dip in port.get("dipswitches", []):
                        conn.execute(
                            """INSERT INTO dipswitch
                            (input_id, tag, name, mask, defvalue)
                            VALUES (?, ?, ?, ?, ?)""",
                            (
                                input_id,
                                dip.get("tag"),
                                dip.get("name"),
                                dip.get("mask"),
                                dip.get("defvalue"),
                            )
                        )

                # Configurações (globais)
                for conf in machine_data.get("configurations", []):
                    conn.execute(
                        """INSERT INTO configuration
                        (input_id, tag, name, mask, defvalue)
                        VALUES (?, ?, ?, ?, ?)""",
                        (
                            input_id,
                            conf.get("tag"),
                            conf.get("name"),
                            conf.get("mask"),
                            conf.get("defvalue"),
                        )
                    )

            # --- Displays ---
            for display in machine_data.get("displays", []):
                conn.execute(
                    """INSERT INTO display
                    (machine_id, tag, type, rotate, width, height, refresh,
                     pixclock, htotal, vtotal)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        machine_id,
                        display.get("tag"),
                        display.get("type"),
                        display.get("rotate"),
                        display.get("width"),
                        display.get("height"),
                        display.get("refresh"),
                        display.get("pixclock"),
                        display.get("htotal"),
                        display.get("vtotal"),
                    )
                )

            # --- Sound ---
            if machine_data.get("sound"):
                conn.execute(
                    """INSERT INTO sound
                    (machine_id, channels)
                    VALUES (?, ?)""",
                    (
                        machine_id,
                        machine_data["sound"].get("channels"),
                    )
                )

            # --- Chips ---
            for chip in machine_data.get("chips", []):
                conn.execute(
                    """INSERT INTO chip
                    (machine_id, tag, type, name, clock)
                    VALUES (?, ?, ?, ?, ?)""",
                    (
                        machine_id,
                        chip.get("tag"),
                        chip.get("type"),
                        chip.get("name"),
                        chip.get("clock"),
                    )
                )

            # --- Device references ---
            for dev in machine_data.get("device_refs", []):
                conn.execute(
                    """INSERT INTO device_ref
                    (machine_id, name)
                    VALUES (?, ?)""",
                    (machine_id, dev)
                )

            # --- Slots e opções ---
            for slot in machine_data.get("slots", []):
                cur = conn.execute(
                    """INSERT INTO slot
                    (machine_id, name)
                    VALUES (?, ?)""",
                    (machine_id, slot.get("name"))
                )
                slot_id = cur.lastrowid
                for opt in slot.get("options", []):
                    conn.execute(
                        """INSERT INTO slot_option
                        (slot_id, name, devname, is_default)
                        VALUES (?, ?, ?, ?)""",
                        (
                            slot_id,
                            opt.get("name"),
                            opt.get("devname"),
                            1 if opt.get("default") else 0,   # opt.get("default") é booleano
                        )
                    )

            # --- Software lists ---
            for sw in machine_data.get("softwarelists", []):
                conn.execute(
                    """INSERT INTO softwarelist
                    (machine_id, name, status, filter)
                    VALUES (?, ?, ?, ?)""",
                    (
                        machine_id,
                        sw.get("name"),
                        sw.get("status"),
                        sw.get("filter"),
                    )
                )

            # --- Features ---
            for feat in machine_data.get("features", []):
                conn.execute(
                    """INSERT INTO feature
                    (machine_id, name, value)
                    VALUES (?, ?, ?)""",
                    (
                        machine_id,
                        feat.get("name"),
                        feat.get("value"),
                    )
                )

            # --- RAM options ---
            for ram in machine_data.get("ramoptions", []):
                conn.execute(
                    """INSERT INTO ramoption
                    (machine_id, name, default_value)
                    VALUES (?, ?, ?)""",
                    (
                        machine_id,
                        ram.get("name"),
                        ram.get("default"),   # o valor original é "default"
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