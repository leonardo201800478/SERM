"""
Catálogo físico de fontes de ROMs para o MAME Set Builder.

Este módulo resolve uma limitação importante do scanner/reconstrutor:
uma ROM necessária por uma machine pode existir dentro do ZIP de outra
machine. O diagnóstico não deve depender de uma nova busca indiscriminada
durante a reconstrução.

O catálogo é construído durante o Scan ROMs e persiste somente metadados
necessários para localizar candidatos físicos:

    * caminho do arquivo de origem;
    * tipo da origem;
    * nome do membro do ZIP;
    * machine inferida do nome do ZIP;
    * nome do membro;
    * tamanho descompactado;
    * CRC32 armazenado no ZIP.

Para ZIPs não é necessário ler o conteúdo das ROMs durante a indexação:
o diretório central do ZIP já contém tamanho e CRC32. A integridade real
da ROM continua sendo validada durante a reconstrução, em streaming.

Arquivos soltos são indexados somente quando o tamanho pode corresponder
a alguma ROM esperada; nesses casos CRC32/SHA1 são calculados em streaming.

O catálogo é JSONL para não manter o fullset inteiro na RAM.
"""

from __future__ import annotations

import binascii
import hashlib
import json
import logging
import os
import threading
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 1024 * 1024
DEFAULT_INDEX_FILENAME = "rom_source_index.jsonl"


@dataclass(slots=True, frozen=True)
class RomSourceCandidate:
    """Fonte física candidata para uma ROM esperada."""

    kind: str
    archive: str
    member: str | None
    machine: str | None
    name: str
    size: int
    crc: str
    sha1: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Converte o candidato para JSON."""
        return asdict(self)


class RomSourceIndexWriter:
    """Escritor streaming do catálogo físico."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = None
        self._lock = threading.RLock()

    def open(self) -> None:
        """Abre um novo catálogo usando arquivo temporário."""
        with self._lock:
            if self._file is not None:
                return
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            self._file = tmp.open("w", encoding="utf-8", newline="\n")
            self._tmp_path = tmp

    def write(self, candidate: RomSourceCandidate) -> None:
        """Grava um candidato imediatamente."""
        with self._lock:
            if self._file is None:
                raise RuntimeError("Índice de fontes não está aberto.")
            self._file.write(
                json.dumps(
                    candidate.to_dict(),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )
            self._file.flush()

    def close(self, publish: bool = True) -> None:
        """Fecha e publica atomicamente o catálogo quando solicitado."""
        with self._lock:
            if self._file is None:
                return
            self._file.flush()
            self._file.close()
            self._file = None
            if publish:
                os.replace(self._tmp_path, self.path)
            else:
                try:
                    self._tmp_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Não foi possível remover índice temporário %s", self._tmp_path)

    def __enter__(self) -> RomSourceIndexWriter:
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close(publish=exc is None)


class RomSourceIndex:
    """Leitor streaming do catálogo de fontes."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def iter_candidates(self) -> Iterator[RomSourceCandidate]:
        """Itera candidatos sem carregar o índice inteiro na memória."""
        if not self.path.is_file():
            return
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    yield RomSourceCandidate(
                        kind=str(data.get("kind") or ""),
                        archive=str(data.get("archive") or ""),
                        member=data.get("member"),
                        machine=data.get("machine"),
                        name=str(data.get("name") or ""),
                        size=int(data.get("size") or 0),
                        crc=str(data.get("crc") or "").lower(),
                        sha1=data.get("sha1"),
                    )
                except (ValueError, TypeError, json.JSONDecodeError):
                    logger.warning("Registro inválido ignorado no catálogo: %s", line[:200])

    def find(self, *, crc: str, size: int, name: str | None = None) -> list[RomSourceCandidate]:
        """Retorna candidatos compatíveis por CRC/tamanho e, opcionalmente, nome."""
        crc = (crc or "").lower()
        name_lower = (name or "").lower()
        result: list[RomSourceCandidate] = []
        for candidate in self.iter_candidates():
            if candidate.size != size or candidate.crc != crc:
                continue
            if name_lower and candidate.name.lower() == name_lower:
                result.insert(0, candidate)
            else:
                result.append(candidate)
        return result


class RomSourceIndexer:
    """Constrói o catálogo físico do fullset de forma segura e incremental."""

    def __init__(
        self,
        source_paths: Iterable[str | Path],
        index_path: Path | str,
        *,
        expected_signatures: set[tuple[str, int]] | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        log_callback=None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        self.source_paths = [Path(p).expanduser() for p in source_paths]
        self.index_path = Path(index_path)
        self.expected_signatures = expected_signatures
        self.chunk_size = max(4096, int(chunk_size))
        self.log_callback = log_callback
        self.cancel_event = cancel_event or threading.Event()

    def _log(self, message: str, *args: object) -> None:
        logger.info(message, *args)
        if self.log_callback is not None:
            try:
                self.log_callback(message % args if args else message)
            except Exception:
                logger.exception("Erro no callback do catálogo físico.")

    @staticmethod
    def _machine_from_archive(path: Path) -> str | None:
        """Infere a machine pelo nome do ZIP, sem tratar isso como verdade lógica."""
        return path.stem if path.suffix.lower() == ".zip" else None

    @staticmethod
    def _crc_hex(value: int) -> str:
        return f"{value & 0xFFFFFFFF:08x}"

    def _should_index(self, crc: str, size: int) -> bool:
        if self.expected_signatures is None:
            return True
        return (crc.lower(), size) in self.expected_signatures

    def _index_zip(self, path: Path, writer: RomSourceIndexWriter) -> int:
        count = 0
        try:
            with zipfile.ZipFile(path, "r") as zf:
                machine = self._machine_from_archive(path)
                for info in zf.infolist():
                    if self.cancel_event.is_set():
                        return count
                    if info.is_dir():
                        continue
                    crc = self._crc_hex(info.CRC)
                    size = int(info.file_size)
                    if not self._should_index(crc, size):
                        continue
                    writer.write(
                        RomSourceCandidate(
                            kind="zip",
                            archive=str(path),
                            member=info.filename,
                            machine=machine,
                            name=Path(info.filename).name,
                            size=size,
                            crc=crc,
                        )
                    )
                    count += 1
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            self._log("ZIP ignorado no catálogo: %s (%s)", path, exc)
        return count

    def _hash_file(self, path: Path) -> tuple[int, str, str]:
        size = 0
        crc = 0
        sha1 = hashlib.sha1()
        with path.open("rb") as handle:
            while True:
                if self.cancel_event.is_set():
                    raise InterruptedError
                chunk = handle.read(self.chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                crc = binascii.crc32(chunk, crc)
                sha1.update(chunk)
        return size, self._crc_hex(crc), sha1.hexdigest()

    def _index_file(self, path: Path, writer: RomSourceIndexWriter) -> int:
        try:
            if self.expected_signatures is not None:
                size = path.stat().st_size
                if not any(sig[1] == size for sig in self.expected_signatures):
                    return 0
            size, crc, sha1 = self._hash_file(path)
            if not self._should_index(crc, size):
                return 0
            writer.write(
                RomSourceCandidate(
                    kind="file",
                    archive=str(path),
                    member=None,
                    machine=None,
                    name=path.name,
                    size=size,
                    crc=crc,
                    sha1=sha1,
                )
            )
            return 1
        except InterruptedError:
            return 0
        except (OSError, PermissionError) as exc:
            self._log("Arquivo ignorado no catálogo: %s (%s)", path, exc)
            return 0

    def build(self) -> dict[str, int | bool | str]:
        """Percorre as fontes uma vez e publica o catálogo somente ao concluir."""
        stats = {
            "archives": 0,
            "files": 0,
            "candidates": 0,
            "cancelled": False,
            "index": str(self.index_path),
        }
        self._log("Construindo catálogo físico do fullset...")
        with RomSourceIndexWriter(self.index_path) as writer:
            for base in self.source_paths:
                if self.cancel_event.is_set():
                    stats["cancelled"] = True
                    break
                if not base.exists() or not base.is_dir():
                    self._log("Origem inexistente ignorada: %s", base)
                    continue
                for path in base.rglob("*"):
                    if self.cancel_event.is_set():
                        stats["cancelled"] = True
                        break
                    if not path.is_file():
                        continue
                    suffix = path.suffix.lower()
                    if suffix == ".zip":
                        stats["archives"] += 1
                        stats["candidates"] += self._index_zip(path, writer)
                    elif suffix not in {".chd", ".7z", ".rar"}:
                        stats["files"] += 1
                        stats["candidates"] += self._index_file(path, writer)
                if stats["cancelled"]:
                    break
        self._log(
            "Catálogo físico concluído: %d ZIPs, %d arquivos, %d candidatos.",
            stats["archives"], stats["files"], stats["candidates"],
        )
        return stats
