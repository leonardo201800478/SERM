"""Motor de scan V2 orientado por perfil.

A camada de serviço não conhece widgets Qt. Cada evento é enviado ao logger e ao
callback opcional da interface, mantendo console e GUI sincronizados.
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable


LogCallback = Callable[[str, str], None]
ProgressCallback = Callable[[int, int], None]


@dataclass(slots=True, frozen=True)
class ScanItem:
    machine_name: str
    rom_name: str
    size: int
    crc32: str = ""
    sha1: str = ""
    optional: bool = False


@dataclass(slots=True)
class ScanResult:
    scan_id: str
    profile_id: str
    source: str
    system: str
    status_counts: Counter[str] = field(default_factory=Counter)
    files_examined: int = 0
    archives_examined: int = 0
    items_examined: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0
    errors: int = 0

    @property
    def elapsed_seconds(self) -> float:
        end = self.finished_at or time.time()
        return max(0.0, end - self.started_at)


class RomScanService:
    """Executa uma varredura segura e observável sobre fontes temporárias."""

    CHUNK_SIZE = 1024 * 1024
    LOG_EVERY_FILES = 250
    LOG_EVERY_SECONDS = 2.0

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        log_callback: LogCallback | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.logger = logger or logging.getLogger("serm.scan")
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self._cancelled = False

    def cancel(self) -> None:
        """Solicita cancelamento; o serviço encerra no próximo ponto seguro."""
        self._cancelled = True
        self._log("INFO", "CANCELAMENTO | solicitação recebida; encerrando no próximo checkpoint")

    def scan(self, profile, *, catalog_items: Iterable[ScanItem] = ()) -> ScanResult:
        scan_id = self._make_scan_id(profile)
        started = time.time()
        result = ScanResult(
            scan_id=scan_id,
            profile_id=str(profile.profile_id),
            source=str(profile.source),
            system=str(profile.system),
            started_at=started,
        )
        self._cancelled = False
        sources = [Path(p).expanduser().resolve() for p in profile.source_directories]
        self._log("INFO", "SCAN | início")
        self._log("INFO", f"SCAN | scan_id={scan_id}")
        self._log("INFO", f"SCAN | profile_id={profile.profile_id}")
        self._log("INFO", f"SCAN | fonte={profile.source} | sistema={profile.system}")
        self._log("INFO", f"SCAN | fontes={len(sources)} | recursivo={bool(profile.recursive)}")
        for index, source in enumerate(sources, 1):
            self._log("INFO", f"SCAN | fonte[{index}]={source}")

        files = list(self._iter_files(sources, bool(profile.recursive)))
        total = len(files)
        self._log("INFO", f"ARQUIVOS | candidatos={total}")
        self._log("INFO", "ARQUIVOS | indexação concluída; iniciando validação")

        last_log = time.monotonic()
        for index, path in enumerate(files, 1):
            if self._cancelled:
                result.status_counts["CANCELLED"] += 1
                self._log("WARNING", f"SCAN | cancelado no arquivo={index}/{total}")
                break
            try:
                self._inspect_file(path, result)
            except (OSError, zipfile.BadZipFile) as exc:
                result.errors += 1
                result.status_counts["ERROR"] += 1
                self._log("ERROR", f"ARQUIVO ERRO | arquivo={path} | {type(exc).__name__}: {exc}")
            if self.progress_callback:
                self.progress_callback(index, total)
            now = time.monotonic()
            if index == 1 or index % self.LOG_EVERY_FILES == 0 or now - last_log >= self.LOG_EVERY_SECONDS or index == total:
                self._log(
                    "INFO",
                    f"SCAN | progresso={index}/{total} | arquivos={result.files_examined} | "
                    f"archives={result.archives_examined} | itens={result.items_examined} | "
                    f"erros={result.errors}",
                )
                last_log = now

        # O matching físico contra o catálogo será conectado na próxima camada;
        # arquivos indexados não são marcados como OK sem validação do DAT.
        result.finished_at = time.time()
        self._log_summary(result)
        return result

    def _inspect_file(self, path: Path, result: ScanResult) -> None:
        result.files_examined += 1
        suffix = path.suffix.casefold()
        if suffix == ".zip":
            result.archives_examined += 1
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    result.items_examined += 1
        else:
            result.items_examined += 1

    def _iter_files(self, sources: list[Path], recursive: bool) -> Iterable[Path]:
        for source in sources:
            if not source.is_dir():
                self._log("WARNING", f"FONTE | diretório inexistente ou inválido={source}")
                continue
            iterator = source.rglob("*") if recursive else source.glob("*")
            for path in iterator:
                if path.is_file():
                    yield path

    def _log_summary(self, result: ScanResult) -> None:
        counts = " | ".join(f"{key}={value}" for key, value in sorted(result.status_counts.items())) or "nenhum resultado"
        self._log("INFO", "SCAN | finalizando")
        self._log("INFO", f"SCAN | resultado | {counts}")
        self._log(
            "INFO",
            f"SCAN | arquivos={result.files_examined} | archives={result.archives_examined} | "
            f"itens={result.items_examined} | erros={result.errors} | duração={result.elapsed_seconds:.2f}s",
        )
        self._log("INFO", f"SCAN | scan_id={result.scan_id} | profile_id={result.profile_id}")

    def _log(self, level: str, message: str) -> None:
        log_method = getattr(self.logger, level.casefold(), self.logger.info)
        log_method(message)
        if self.log_callback:
            self.log_callback(level, message)

    @staticmethod
    def _make_scan_id(profile) -> str:
        seed = f"{profile.profile_id}|{time.time_ns()}|{os.getpid()}".encode()
        return hashlib.sha1(seed).hexdigest()[:16]


__all__ = ["LogCallback", "ProgressCallback", "RomScanService", "ScanItem", "ScanResult"]
