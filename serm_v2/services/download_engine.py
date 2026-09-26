"""Motor de downloads HTTP reutilizável e otimizado para o SERM.

Usa HTTP Range quando o servidor oferece suporte, dividindo arquivos grandes em
segmentos independentes. Mantém segmentos temporários para permitir retomada
após cancelamento ou falha e cai automaticamente para uma conexão única quando
Range não está disponível.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import Lock


class DownloadEngineError(RuntimeError):
    """Erro acionável de aquisição HTTP."""


ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]


@dataclass(frozen=True, slots=True)
class DownloadEngineConfig:
    max_connections: int = 6
    segment_size: int = 32 * 1024 * 1024
    chunk_size: int = 1024 * 1024
    timeout: int = 60
    retries: int = 3
    user_agent: str = "SERM/2.x"


class DownloadEngine:
    """Baixa arquivos HTTP com paralelismo, retomada e validação atômica."""

    def __init__(self, config: DownloadEngineConfig | None = None) -> None:
        self.config = config or DownloadEngineConfig()

    def download(
        self,
        url: str,
        target: str | Path,
        *,
        expected_size: int | None = None,
        expected_sha256: str | None = None,
        headers: dict[str, str] | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_callback: CancelCallback | None = None,
    ) -> Path:
        destination = Path(target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file() and self._matches(destination, expected_size, expected_sha256):
            if progress_callback:
                size = destination.stat().st_size
                progress_callback(size, size)
            return destination

        work_dir = destination.parent / f".{destination.name}.download"
        work_dir.mkdir(parents=True, exist_ok=True)
        base_headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "application/octet-stream,*/*",
        }
        if headers:
            base_headers.update(headers)

        try:
            size, ranged = self._probe(url, expected_size, base_headers)
            if ranged and size is not None and size > self.config.segment_size:
                self._download_ranged(
                    url,
                    destination,
                    work_dir,
                    size,
                    base_headers,
                    progress_callback,
                    cancel_callback,
                )
            else:
                self._download_single(
                    url,
                    destination,
                    work_dir,
                    size,
                    base_headers,
                    progress_callback,
                    cancel_callback,
                )

            if expected_size is not None and destination.stat().st_size != expected_size:
                raise DownloadEngineError(
                    f"Tamanho inesperado: esperado {expected_size}, "
                    f"recebido {destination.stat().st_size} bytes."
                )
            if expected_sha256 and self.sha256(destination).casefold() != expected_sha256.casefold():
                raise DownloadEngineError("SHA-256 do download não confere.")
            return destination
        except DownloadEngineError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DownloadEngineError(f"Falha no download: {exc}") from exc

    def _probe(
        self,
        url: str,
        expected_size: int | None,
        headers: dict[str, str],
    ) -> tuple[int | None, bool]:
        request_headers = dict(headers)
        request_headers["Range"] = "bytes=0-0"
        try:
            request = urllib.request.Request(url, headers=request_headers)
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                if response.status != 206:
                    size = self._content_length(response)
                    return (expected_size or size), False
                content_range = response.headers.get("Content-Range", "")
                total = self._range_total(content_range)
                return (expected_size or total), bool(total)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
            return expected_size, False

    def _download_ranged(
        self,
        url: str,
        destination: Path,
        work_dir: Path,
        total: int,
        headers: dict[str, str],
        progress_callback: ProgressCallback | None,
        cancel_callback: CancelCallback | None,
    ) -> None:
        segment_count = min(
            self.config.max_connections,
            max(1, (total + self.config.segment_size - 1) // self.config.segment_size),
        )
        ranges = []
        for index in range(segment_count):
            start = index * total // segment_count
            end = ((index + 1) * total // segment_count) - 1
            ranges.append((index, start, end))

        progress_lock = Lock()
        completed = sum(
            self._segment_size(index, start, end, work_dir)
            for index, start, end in ranges
        )
        if progress_callback:
            progress_callback(completed, total)

        with ThreadPoolExecutor(max_workers=segment_count, thread_name_prefix="serm-dl") as executor:
            futures = {
                executor.submit(
                    self._download_segment,
                    url,
                    work_dir / f"segment-{index:04d}.part",
                    start,
                    end,
                    headers,
                    cancel_callback,
                    index,
                ): (start, end)
                for index, start, end in ranges
                if not self._segment_complete(work_dir / f"segment-{index:04d}.part", start, end)
            }
            for future in as_completed(futures):
                size = future.result()
                with progress_lock:
                    completed += size
                    if progress_callback:
                        progress_callback(completed, total)

        if cancel_callback and cancel_callback():
            raise DownloadEngineError("Download cancelado.")

        temporary = destination.with_name(f".{destination.name}.assembling")
        try:
            with temporary.open("wb") as output:
                for index, start, end in ranges:
                    part = work_dir / f"segment-{index:04d}.part"
                    if not self._segment_complete(part, start, end):
                        raise DownloadEngineError(f"Segmento {index + 1} incompleto.")
                    with part.open("rb") as source:
                        shutil.copyfileobj(source, output, length=self.config.chunk_size)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    def _download_segment(
        self,
        url: str,
        target: Path,
        start: int,
        end: int,
        headers: dict[str, str],
        cancel_callback: CancelCallback | None,
        index: int,
    ) -> int:
        expected = end - start + 1
        if self._segment_complete(target, start, end):
            return 0

        existing = target.stat().st_size if target.is_file() else 0
        if existing > expected:
            target.unlink(missing_ok=True)
            existing = 0
        if existing == expected:
            return 0

        range_start = start + existing
        last_error: Exception | None = None
        for attempt in range(self.config.retries):
            try:
                if cancel_callback and cancel_callback():
                    raise DownloadEngineError("Download cancelado.")
                existing = target.stat().st_size if target.is_file() else 0
                if existing > expected:
                    target.unlink(missing_ok=True)
                    existing = 0
                if existing == expected:
                    return expected
                range_start = start + existing
                request_headers = dict(headers)
                request_headers["Range"] = f"bytes={range_start}-{end}"
                request = urllib.request.Request(url, headers=request_headers)
                with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                    if response.status != 206:
                        raise DownloadEngineError(
                            f"Servidor não respeitou Range no segmento {index + 1}."
                        )
                    mode = "ab" if existing else "wb"
                    with target.open(mode) as output:
                        while True:
                            if cancel_callback and cancel_callback():
                                raise DownloadEngineError("Download cancelado.")
                            chunk = response.read(self.config.chunk_size)
                            if not chunk:
                                break
                            output.write(chunk)
                if self._segment_complete(target, start, end):
                    return expected
                raise DownloadEngineError(f"Segmento {index + 1} terminou incompleto.")
            except DownloadEngineError as exc:
                last_error = exc
                if "cancelado" in str(exc).casefold():
                    raise
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
            if attempt + 1 < self.config.retries:
                continue
        raise DownloadEngineError(
            f"Falha no segmento {index + 1}: {last_error}"
        ) from last_error

    def _download_single(
        self,
        url: str,
        destination: Path,
        work_dir: Path,
        total: int | None,
        headers: dict[str, str],
        progress_callback: ProgressCallback | None,
        cancel_callback: CancelCallback | None,
    ) -> None:
        temporary = work_dir / "single.part"
        existing = temporary.stat().st_size if temporary.is_file() else 0
        request_headers = dict(headers)
        if existing:
            request_headers["Range"] = f"bytes={existing}-"
        request = urllib.request.Request(url, headers=request_headers)
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                append = existing > 0 and response.status == 206
                if not append:
                    existing = 0
                done = existing
                with temporary.open("ab" if append else "wb") as output:
                    while True:
                        if cancel_callback and cancel_callback():
                            raise DownloadEngineError("Download cancelado.")
                        chunk = response.read(self.config.chunk_size)
                        if not chunk:
                            break
                        output.write(chunk)
                        done += len(chunk)
                        if progress_callback:
                            progress_callback(done, total or done)
            os.replace(temporary, destination)
        except DownloadEngineError:
            raise
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            raise DownloadEngineError(f"Falha no download: {exc}") from exc

    def _segment_size(self, index: int, start: int, end: int, work_dir: Path) -> int:
        part = work_dir / f"segment-{index:04d}.part"
        if self._segment_complete(part, start, end):
            return end - start + 1
        return 0

    @staticmethod
    def _segment_complete(path: Path, start: int, end: int) -> bool:
        return path.is_file() and path.stat().st_size == end - start + 1

    @staticmethod
    def _content_length(response: object) -> int | None:
        try:
            value = response.headers.get("Content-Length")
            return int(value) if value else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _range_total(value: str) -> int | None:
        if "/" not in value:
            return None
        raw = value.rsplit("/", 1)[1].strip()
        try:
            return int(raw)
        except ValueError:
            return None

    @staticmethod
    def _matches(path: Path, size: int | None, digest: str | None) -> bool:
        if size is not None and path.stat().st_size != size:
            return False
        return not digest or DownloadEngine.sha256(path).casefold() == digest.casefold()

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()


__all__ = ["DownloadEngine", "DownloadEngineConfig", "DownloadEngineError"]
