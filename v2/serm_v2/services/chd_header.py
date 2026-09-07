"""Leitor mínimo e seguro do cabeçalho CHD usado pelo SERM.

O ListXML do MAME compara o conteúdo lógico do disco. Por isso, calcular
``sha1(file.chd)`` é incorreto: o arquivo é um contêiner comprimido. Este
módulo lê somente o cabeçalho e expõe os hashes de dados gravados pelo formato.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


class ChdFormatError(ValueError):
    """CHD ausente, truncado ou com versão não suportada."""


@dataclass(frozen=True, slots=True)
class ChdHeader:
    """Identidade e metadados mínimos do CHD."""

    version: int
    logical_bytes: int
    hunk_bytes: int
    raw_sha1: str | None
    sha1: str | None
    md5: str | None
    parent_sha1: str | None
    file_size: int


class ChdHeaderReader:
    """Lê os cabeçalhos V1-V5 sem depender de chdman ou RomVault."""

    TAG = b"MComprHD"
    HEADER_SIZES = {1: 76, 2: 80, 3: 120, 4: 108, 5: 124}

    def read(self, path: Path) -> ChdHeader:
        """Lê a identidade do CHD sem descompactar seus hunks."""
        file_size = path.stat().st_size
        with path.open("rb") as stream:
            prefix = stream.read(16)
            if len(prefix) < 16 or prefix[:8] != self.TAG:
                raise ChdFormatError(f"Arquivo CHD inválido: {path}")
            length, version = struct.unpack(">II", prefix[8:16])
            header_size = self.HEADER_SIZES.get(version)
            if header_size is None:
                raise ChdFormatError(f"Versão CHD não suportada: {version}")
            if length != header_size:
                raise ChdFormatError(
                    f"Tamanho de cabeçalho CHD inválido: versão={version}, "
                    f"declarado={length}, esperado={header_size}"
                )
            stream.seek(0)
            header = stream.read(header_size)
            if len(header) != header_size:
                raise ChdFormatError(f"Cabeçalho CHD truncado: {path}")

        return self._parse(header, version, file_size)

    @staticmethod
    def _parse(header: bytes, version: int, file_size: int) -> ChdHeader:
        if version in (1, 2):
            # V1/V2 possuem MD5 do conteúdo bruto; não possuem SHA1.
            logical_bytes = (
                struct.unpack_from(">Q", header, 28)[0]
                if version == 2
                else struct.unpack_from(">I", header, 24)[0]
                * struct.unpack_from(">I", header, 28)[0]
                * struct.unpack_from(">I", header, 32)[0]
                * struct.unpack_from(">I", header, 36)[0]
            )
            hunk_bytes = struct.unpack_from(">I", header, 24)[0]
            md5 = header[44:60].hex()
            return ChdHeader(version, logical_bytes, hunk_bytes, None, None, md5, None, file_size)

        if version == 3:
            logical_bytes = struct.unpack_from(">Q", header, 28)[0]
            hunk_bytes = struct.unpack_from(">I", header, 76)[0]
            md5 = header[44:60].hex()
            raw_sha1 = header[80:100].hex()
            parent_sha1 = header[100:120].hex()
            return ChdHeader(version, logical_bytes, hunk_bytes, raw_sha1, raw_sha1, md5, parent_sha1, file_size)

        if version == 4:
            logical_bytes = struct.unpack_from(">Q", header, 28)[0]
            hunk_bytes = struct.unpack_from(">I", header, 44)[0]
            sha1 = header[48:68].hex()
            raw_sha1 = header[88:108].hex()
            parent_sha1 = header[68:88].hex()
            return ChdHeader(version, logical_bytes, hunk_bytes, raw_sha1, sha1, None, parent_sha1, file_size)

        # V5: raw SHA1 está no offset 64; SHA1 geral no offset 84.
        logical_bytes = struct.unpack_from(">Q", header, 32)[0]
        hunk_bytes = struct.unpack_from(">I", header, 56)[0]
        raw_sha1 = header[64:84].hex()
        sha1 = header[84:104].hex()
        parent_sha1 = header[104:124].hex()
        return ChdHeader(version, logical_bytes, hunk_bytes, raw_sha1, sha1, None, parent_sha1, file_size)


__all__ = ["ChdFormatError", "ChdHeader", "ChdHeaderReader"]
