"""Scanner de ROMs MAME orientado a I/O e tolerante a fontes ruins."""
from __future__ import annotations

import logging
import os
import tempfile
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from app.core.models.scan_result import ScanResult, MachineScanResult, RomFile, ScanStatus
from app.mame.integrity import digest_file, digest_stream, matches_digest

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[int, int, str], None]

# Chave do índice de arquivos: (crc em hex minúsculo de 8 dígitos, tamanho em bytes)
ArchiveIndexKey = Tuple[str, int]


class RomScanner:
    def __init__(
        self,
        rom_paths: List[Path],
        *,
        workers: int | None = None,
        chunk_size: int = 1024 * 1024,
        enable_alternate_search: bool = True,
    ):
        self.rom_paths = [Path(p) for p in rom_paths if Path(p).is_dir()]
        self.workers = max(1, min(workers or (os.cpu_count() or 2), 16))
        self.chunk_size = chunk_size
        self.enable_alternate_search = enable_alternate_search
        self._digest_cache: dict[tuple[str, int, int, bool], object] = {}

        # Índice (crc, size) -> [(archive, member), ...] de todos os ZIPs
        # das origens, construído UMA ÚNICA VEZ por scan.
        #
        # Antes, cada ROM ausente/corrompida disparava _search_alternate()
        # reabrindo e relendo TODOS os ZIPs da origem do zero. Com milhares
        # de arquivos isso é lentíssimo e dava a impressão de que o scan
        # "travava" logo no primeiro erro — na verdade ele continuava
        # rodando, só que reescaneando o diretório inteiro repetidamente.
        # Ler apenas o diretório central (infolist) de cada ZIP é rápido
        # mesmo para dezenas de milhares de arquivos, e feito só uma vez.
        self._archive_index: Dict[ArchiveIndexKey, List[Tuple[Path, str]]] | None = None
        self._archive_index_lock = threading.Lock()

    # ------------------------------------------------------------------
    # ÍNDICE DE ARQUIVOS (construído uma vez, reutilizado por todo o scan)
    # ------------------------------------------------------------------

    def build_archive_index(
        self,
        *,
        force: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Constrói o índice (crc, size) -> candidatos das origens.

        Lê apenas o diretório central de cada ZIP (``infolist()``), sem
        descompactar nada. Chamado automaticamente por ``scan_machines`` e
        deve ser chamado explicitamente pelo chamador quando o scan é
        feito máquina-a-máquina (ver ``ScanRomsTab._do_scan``), antes do
        laço de escaneamento.

        Idempotente: se já foi construído, não refaz o trabalho a menos
        que ``force=True``.
        """
        with self._archive_index_lock:
            if self._archive_index is not None and not force:
                return

            index: Dict[ArchiveIndexKey, List[Tuple[Path, str]]] = {}
            archives: List[Path] = []
            for root in self.rom_paths:
                try:
                    archives.extend(root.glob("*.zip"))
                except OSError as exc:
                    logger.warning(f"Não foi possível listar {root}: {exc}")

            total = len(archives)
            logger.info(f"Construindo índice de {total} arquivo(s) ZIP das origens...")

            for count, archive in enumerate(archives, start=1):
                try:
                    with zipfile.ZipFile(archive, "r") as zf:
                        for info in zf.infolist():
                            if info.is_dir():
                                continue
                            key = (f"{info.CRC & 0xFFFFFFFF:08x}", info.file_size)
                            index.setdefault(key, []).append((archive, info.filename))
                except (OSError, zipfile.BadZipFile) as exc:
                    # Um ZIP corrompido não impede a indexação dos demais.
                    logger.warning(f"Não foi possível indexar {archive}: {exc}")

                if progress_callback and (count % 200 == 0 or count == total):
                    progress_callback(count, total, str(archive))

            self._archive_index = index
            logger.info(
                f"Índice de arquivos concluído: {len(index)} chave(s) (crc,size) únicas "
                f"em {total} arquivo(s)."
            )

    def invalidate_archive_index(self) -> None:
        """Força a reconstrução do índice na próxima chamada."""
        with self._archive_index_lock:
            self._archive_index = None

    # ------------------------------------------------------------------
    # API PRINCIPAL
    # ------------------------------------------------------------------

    def scan_machines(
        self, machines: List[dict], *, progress_callback: ProgressCallback | None = None
    ) -> ScanResult:
        self.build_archive_index()

        result = ScanResult(version="unknown")
        jobs = [(machine, rom_info) for machine in machines for rom_info in machine.get("roms", [])]
        completed = 0
        by_machine: dict[str, MachineScanResult] = {
            m.get("name", ""): MachineScanResult(
                name=m.get("name", ""), description=m.get("description", ""), cloneof=m.get("cloneof")
            )
            for m in machines
        }
        with ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="mame-scan") as pool:
            futures = {
                pool.submit(self._scan_rom, rom_info, machine.get("name", "")): (machine.get("name", ""), rom_info)
                for machine, rom_info in jobs
            }
            for future in as_completed(futures):
                machine_name, rom_info = futures[future]
                try:
                    by_machine[machine_name].roms.append(future.result())
                except Exception:
                    # Falha isolada em uma ROM não pode derrubar o scan.
                    logger.exception("Falha isolada ao validar ROM de %s", machine_name)
                    by_machine[machine_name].roms.append(
                        self._corrupted_rom_placeholder(rom_info)
                    )
                completed += 1
                if progress_callback:
                    progress_callback(completed, len(jobs), machine_name)

        result.machines = [by_machine[m.get("name", "")] for m in machines]
        for machine in result.machines:
            machine.update_status()
            machine.total_size = sum(r.size for r in machine.roms if r.status == ScanStatus.OK)
        result.total_machines = len(result.machines)
        result.update_summary()
        return result

    def _scan_single_machine(self, machine_data: dict) -> MachineScanResult:
        """Escaneia uma única máquina.

        Não constrói o índice de arquivos sozinho — quem chama em laço
        (ex.: ``ScanRomsTab._do_scan``) deve chamar ``build_archive_index``
        uma única vez ANTES do laço, para não repetir o trabalho a cada
        máquina.
        """
        name = machine_data.get("name", "")
        machine_result = MachineScanResult(
            name=name, description=machine_data.get("description", ""), cloneof=machine_data.get("cloneof")
        )
        rom_infos = machine_data.get("roms", [])

        if not rom_infos:
            machine_result.update_status()
            return machine_result

        with ThreadPoolExecutor(max_workers=min(self.workers, max(1, len(rom_infos)))) as pool:
            futures = {pool.submit(self._scan_rom, rom_info, name): rom_info for rom_info in rom_infos}
            for future in as_completed(futures):
                rom_info = futures[future]
                try:
                    machine_result.roms.append(future.result())
                except Exception:
                    # Uma ROM com falha (corrompida, XML inconsistente etc.)
                    # não pode derrubar o scan da máquina, nem do restante
                    # do set. Registramos e seguimos.
                    logger.exception(
                        "Falha isolada ao validar ROM '%s' da máquina '%s'",
                        rom_info.get("name", "?"),
                        name,
                    )
                    machine_result.roms.append(self._corrupted_rom_placeholder(rom_info))

        machine_result.update_status()
        machine_result.total_size = sum(r.size for r in machine_result.roms if r.status == ScanStatus.OK)
        return machine_result

    @staticmethod
    def _corrupted_rom_placeholder(rom_info: dict) -> RomFile:
        return RomFile(
            name=rom_info.get("name", ""),
            size=int(rom_info.get("size", 0) or 0),
            crc=(rom_info.get("crc", "") or "").lower(),
            sha1=(rom_info.get("sha1") or "").lower() or None,
            merge=rom_info.get("merge"),
            status=ScanStatus.CORRUPTED,
        )

    # ------------------------------------------------------------------
    # VALIDAÇÃO DE UMA ROM
    # ------------------------------------------------------------------

    def _scan_rom(self, rom_info: dict, machine_name: str) -> RomFile:
        expected = RomFile(
            name=rom_info.get("name", ""),
            size=int(rom_info.get("size", 0) or 0),
            crc=(rom_info.get("crc", "") or "").lower(),
            sha1=(rom_info.get("sha1") or "").lower() or None,
            merge=rom_info.get("merge"),
            status=ScanStatus.MISSING,
        )
        candidates: list[tuple[str, Path]] = []
        for root in self.rom_paths:
            for archive_name in {machine_name, expected.merge} - {None, ""}:
                archive = root / f"{archive_name}.zip"
                if archive.is_file():
                    candidates.append(("zip", archive))
                archive7z = root / f"{archive_name}.7z"
                if archive7z.is_file():
                    candidates.append(("7z", archive7z))
            loose = root / expected.name
            if loose.is_file():
                candidates.append(("file", loose))

        saw_corrupt = False
        for kind, path in candidates:
            try:
                actual = self._validate_candidate(kind, path, expected.name, bool(expected.sha1))
                if actual is None:
                    continue
                expected.found_in = path
                expected.found_member = expected.name if kind in {"zip", "7z"} else None
                expected.actual_size, expected.actual_crc, expected.actual_sha1 = (
                    actual.size,
                    actual.crc,
                    actual.sha1,
                )
                if matches_digest(actual, size=expected.size, crc=expected.crc, sha1=expected.sha1 or ""):
                    expected.status = ScanStatus.OK
                    return expected
                saw_corrupt = True
            except (OSError, zipfile.BadZipFile, KeyError, NotImplementedError) as exc:
                # Candidato específico com problema (item ausente no ZIP,
                # arquivo corrompido, etc.) — isolado. Tenta o próximo
                # candidato / a busca alternativa, sem propagar o erro.
                logger.warning("Falha ao ler candidato %s: %s", path, exc)
                saw_corrupt = True

        # Segunda etapa: procurar o mesmo conteúdo em outro set ou com
        # outro nome interno, usando o índice pré-construído — rápido,
        # sem reabrir todos os ZIPs de novo para cada ROM.
        alternate = self._search_alternate(expected)
        if alternate is not None:
            expected.found_in, expected.found_member = alternate[0], alternate[1]
            actual = alternate[2]
            expected.actual_size, expected.actual_crc, expected.actual_sha1 = (
                actual.size,
                actual.crc,
                actual.sha1,
            )
            expected.status = ScanStatus.FIXABLE
            return expected

        expected.status = ScanStatus.CORRUPTED if saw_corrupt else ScanStatus.MISSING
        return expected

    def _search_alternate(self, expected: RomFile):
        if not self.enable_alternate_search:
            return None

        # Índice ainda não construído (chamada avulsa/legada, sem passar
        # pelo fluxo normal): constrói sob demanda uma única vez, em vez
        # de escanear tudo de novo a cada ROM.
        if self._archive_index is None:
            self.build_archive_index()

        try:
            crc_key = f"{int(expected.crc or '0', 16) & 0xFFFFFFFF:08x}"
        except ValueError:
            return None

        candidates = self._archive_index.get((crc_key, expected.size), [])
        for archive, member in candidates:
            try:
                with zipfile.ZipFile(archive, "r") as zf:
                    with zf.open(member, "r") as stream:
                        actual = digest_stream(
                            stream, need_sha1=bool(expected.sha1), chunk_size=self.chunk_size
                        )
            except (OSError, zipfile.BadZipFile, KeyError) as exc:
                logger.warning(
                    "Falha ao ler candidato alternativo %s!%s: %s", archive, member, exc
                )
                continue
            if matches_digest(actual, size=expected.size, crc=expected.crc, sha1=expected.sha1 or ""):
                return archive, member, actual
        return None

    def _validate_candidate(self, kind: str, path: Path, member: str, need_sha1: bool):
        if kind == "file":
            return digest_file(path, need_sha1=need_sha1, chunk_size=self.chunk_size)
        if kind == "zip":
            with zipfile.ZipFile(path, "r") as archive:
                info = archive.getinfo(member)
                with archive.open(info, "r") as stream:
                    return digest_stream(stream, need_sha1=need_sha1, chunk_size=self.chunk_size)
        if kind == "7z":
            try:
                import py7zr
            except ImportError as exc:
                raise NotImplementedError("backend py7zr não instalado") from exc
            with py7zr.SevenZipFile(path, mode="r") as archive:
                entries = {entry.filename: entry for entry in archive.list()}
                entry = entries.get(member)
                if entry is None:
                    return None
                uncompressed = int(getattr(entry, "uncompressed", 0) or 0)
                if uncompressed > 64 * 1024 * 1024:
                    raise NotImplementedError("membro 7Z maior que 64 MiB exige backend de streaming")
                with tempfile.TemporaryDirectory(prefix="mame-7z-") as temp_dir:
                    archive.extract(path=temp_dir, targets=[member])
                    extracted = Path(temp_dir) / member
                    if not extracted.is_file():
                        return None
                    return digest_file(extracted, need_sha1=need_sha1, chunk_size=self.chunk_size)
        return None