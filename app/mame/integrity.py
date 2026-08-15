"""Primitivas de validação de arquivos MAME com baixo uso de memória."""
from __future__ import annotations

import hashlib
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


@dataclass(frozen=True)
class DigestResult:
    size: int
    crc: str
    sha1: str | None = None


def digest_stream(stream: BinaryIO, *, need_sha1: bool = False, chunk_size: int = 1024 * 1024) -> DigestResult:
    """Calcula os digests lendo em blocos; nunca usa ``read()`` sem limite."""
    crc = 0
    sha1 = hashlib.sha1() if need_sha1 else None
    total = 0
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        crc = zlib.crc32(chunk, crc)
        if sha1 is not None:
            sha1.update(chunk)
    return DigestResult(total, f"{crc & 0xFFFFFFFF:08x}", sha1.hexdigest() if sha1 else None)


def digest_file(path: Path, *, need_sha1: bool = False, chunk_size: int = 1024 * 1024) -> DigestResult:
    with path.open("rb") as stream:
        return digest_stream(stream, need_sha1=need_sha1, chunk_size=chunk_size)


def matches_digest(actual: DigestResult, *, size: int, crc: str = "", sha1: str = "") -> bool:
    """Exige todos os identificadores disponíveis no XML.

    CRC é uma triagem rápida; quando SHA-1 é informado, ele também é obrigatório.
    """
    if actual.size != int(size):
        return False
    if crc and actual.crc.lower() != crc.lower():
        return False
    if sha1 and (actual.sha1 or "").lower() != sha1.lower():
        return False
    return True
