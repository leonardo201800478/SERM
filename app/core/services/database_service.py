import hashlib
import logging
from typing import Callable, Iterable, Optional

from app.core.models.machine import Machine
from app.mame.executable import MameExecutable
from app.mame.listxml_parser import iter_machines

logger = logging.getLogger(__name__)

# Quantas máquinas acumular antes de disparar um executemany() no banco.
_BATCH_SIZE = 500

ProgressCallback = Optional[Callable[[int, str], None]]


class DatabaseService:
    def __init__(self, conn):
        self.conn = conn

    # ------------------------------------------------------------------
    # API principal (streaming, recomendada)
    # ------------------------------------------------------------------

    def import_from_executable(
        self,
        mame: MameExecutable,
        progress_callback: ProgressCallback = None,
    ) -> int:
        """Importa o dataset completo direto do executável MAME, em streaming.

        Não materializa o XML inteiro em memória: o stdout do processo
        ``mame -listxml`` é consumido incrementalmente pelo parser
        (iterparse) e cada máquina é inserida no banco em lotes.

        Args:
            mame: instância de MameExecutable já apontando para o binário.
            progress_callback: opcional, chamado periodicamente como
                ``progress_callback(quantidade_processada, mensagem)``.

        Returns:
            Número total de máquinas importadas.
        """
        executable_path = str(mame.path)
        version = mame.version
        installation_id = self._upsert_installation(executable_path, version)

        if progress_callback:
            progress_callback(0, "Executando mame -listxml...")

        with mame.stream_listxml() as stdout:
            total = self._import_machines(
                iter_machines(stdout), installation_id, progress_callback
            )

        logger.info(f"Importação concluída. {total} máquinas inseridas/atualizadas.")
        return total

    def import_listxml(self, xml_string: str, executable_path: str, version: str) -> int:
        """Importa a partir de um XML já obtido como string.

        Mantido para compatibilidade com chamadores existentes (ex.: quando
        o XML já foi salvo em arquivo/variável). Sempre que possível,
        prefira ``import_from_executable``, que evita materializar o XML
        inteiro em memória.
        """
        installation_id = self._upsert_installation(executable_path, version)
        return self._import_machines(iter_machines(xml_string), installation_id, None)

    def update_chd_sizes(self, chd_sizes: dict) -> int:
        """Persiste tamanhos reais de CHDs (lidos do disco) na tabela `disk`.

        Args:
            chd_sizes: {(nome_da_maquina, nome_do_disco): tamanho_em_bytes},
                normalmente vindo de ``app.mame.chd_scanner.scan_chd_sizes``.

        Returns:
            Quantidade de registros de `disk` efetivamente atualizados.
        """
        cursor = self.conn.cursor()
        updated = 0
        for (machine_name, disk_name), size in chd_sizes.items():
            cursor.execute(
                """
                UPDATE disk SET size = ?
                WHERE name = ? AND machine_id = (SELECT id FROM machine WHERE name = ?)
                """,
                (size, disk_name, machine_name),
            )
            updated += cursor.rowcount
        self.conn.commit()
        return updated

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _upsert_installation(self, executable_path: str, version: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM mame_installation WHERE executable_path = ?",
            (executable_path,),
        )
        row = cursor.fetchone()
        if row:
            installation_id = row[0]
            cursor.execute(
                "UPDATE mame_installation SET version = ?, detected_at = CURRENT_TIMESTAMP WHERE id = ?",
                (version, installation_id),
            )
            logger.info(f"Instalação existente atualizada (ID {installation_id})")
        else:
            with open(executable_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            cursor.execute(
                "INSERT INTO mame_installation (version, executable_path, executable_hash) VALUES (?, ?, ?)",
                (version, executable_path, file_hash),
            )
            installation_id = cursor.lastrowid
            logger.info(f"Nova instalação criada (ID {installation_id})")
        self.conn.commit()
        return installation_id

    def _import_machines(
        self,
        machines: Iterable[Machine],
        installation_id: int,
        progress_callback: ProgressCallback,
    ) -> int:
        cursor = self.conn.cursor()
        total = 0
        batch: list[Machine] = []

        # Uma única transação para o dataset inteiro: muito mais rápido
        # que autocommit por máquina, e garante atomicidade (tudo ou nada).
        cursor.execute("BEGIN")
        try:
            for machine in machines:
                batch.append(machine)
                if len(batch) >= _BATCH_SIZE:
                    self._flush_batch(cursor, batch, installation_id)
                    total += len(batch)
                    batch.clear()
                    if progress_callback:
                        progress_callback(total, f"{total} máquinas processadas...")
            if batch:
                self._flush_batch(cursor, batch, installation_id)
                total += len(batch)
        except Exception:
            self.conn.rollback()
            logger.error("Falha durante a importação, transação revertida.", exc_info=True)
            raise
        else:
            self.conn.commit()

        return total

    def _flush_batch(self, cursor, batch: list[Machine], installation_id: int) -> None:
        cursor.executemany(
            """
            INSERT OR REPLACE INTO machine
            (name, description, year, manufacturer, sourcefile, cloneof, romof, sampleof,
             is_bios, is_device, is_mechanical, runnable, emulation_status, driver_status,
             savestate, requires_artwork, unofficial, nosoundhardware, incomplete,
             mame_installation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    m.name, m.description, m.year, m.manufacturer,
                    m.sourcefile, m.cloneof, m.romof, m.sampleof,
                    int(m.is_bios), int(m.is_device), int(m.is_mechanical), int(m.runnable),
                    m.emulation_status, m.driver_status,
                    int(m.savestate), int(m.requires_artwork), int(m.unofficial),
                    int(m.nosoundhardware), int(m.incomplete),
                    installation_id,
                )
                for m in batch
            ],
        )

        # Recupera os IDs recém-atribuídos para popular ROMs/disks.
        # INSERT OR REPLACE não garante lastrowid previsível em lote, então
        # buscamos pelo nome (único) após o insert.
        names = [m.name for m in batch]
        placeholders = ",".join(["?"] * len(names))
        cursor.execute(
            f"SELECT id, name FROM machine WHERE name IN ({placeholders})", names
        )
        name_to_id = {name: mid for mid, name in cursor.fetchall()}

        machine_ids = [name_to_id[m.name] for m in batch if m.name in name_to_id]
        if machine_ids:
            id_placeholders = ",".join(["?"] * len(machine_ids))
            cursor.execute(f"DELETE FROM rom WHERE machine_id IN ({id_placeholders})", machine_ids)
            cursor.execute(f"DELETE FROM disk WHERE machine_id IN ({id_placeholders})", machine_ids)

        rom_rows = [
            (
                name_to_id[m.name], r.name, r.size, r.crc, r.sha1, r.merge,
                r.region, r.offset, r.status, int(r.optional), r.bios,
            )
            for m in batch if m.name in name_to_id
            for r in m.roms
        ]
        if rom_rows:
            cursor.executemany(
                """
                INSERT INTO rom
                (machine_id, name, size, crc, sha1, merge, region, offset, status, optional, bios)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rom_rows,
            )

        disk_rows = [
            (
                name_to_id[m.name], d.name, d.sha1, d.merge, d.region,
                d.index, int(d.writable), d.status, int(d.optional),
            )
            for m in batch if m.name in name_to_id
            for d in m.disks
        ]
        if disk_rows:
            cursor.executemany(
                """
                INSERT INTO disk
                (machine_id, name, sha1, merge, region, idx, writable, status, optional)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                disk_rows,
            )
