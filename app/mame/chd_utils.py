"""Utilitários para validar o digest de conteúdo de arquivos CHD MAME.

O SHA-1 listado pelo MAME para ``<disk>`` não é o SHA-1 bruto do arquivo
``.chd``. É o digest armazenado no cabeçalho CHD. O arquivo físico pode
mudar de tamanho/compressão sem mudar o conteúdo lógico.
"""
from __future__ import annotations

import struct
from pathlib import Path


class ChdFormatError(ValueError):
    """Indica um arquivo que não possui um cabeçalho CHD suportado."""


def read_chd_header(path: str | Path) -> dict[str, int | str]:
    """Lê versão, tamanho lógico e SHA-1 de conteúdo do cabeçalho CHD.

    Suporta CHD v3, v4 e v5, que são as versões relevantes para os sets
    modernos do MAME. O SHA-1 retornado é o digest ``sha1`` do cabeçalho,
    correspondente ao digest de conteúdo usado pelo MAME.
    """
    path = Path(path)
    with path.open("rb") as handle:
        header = handle.read(128)
    if len(header) < 16 or header[:8] != b"MComprHD":
        raise ChdFormatError(f"Arquivo não é um CHD válido: {path}")

    version = struct.unpack_from(">I", header, 12)[0]
    if version == 3:
        if len(header) < 100:
            raise ChdFormatError("Cabeçalho CHD v3 incompleto")
        logical_size = struct.unpack_from(">Q", header, 28)[0]
        sha1 = header[80:100].hex()
    elif version == 4:
        if len(header) < 68:
            raise ChdFormatError("Cabeçalho CHD v4 incompleto")
        logical_size = struct.unpack_from(">Q", header, 28)[0]
        sha1 = header[48:68].hex()
    elif version >= 5:
        if len(header) < 104:
            raise ChdFormatError("Cabeçalho CHD v5 incompleto")
        logical_size = struct.unpack_from(">Q", header, 32)[0]
        sha1 = header[84:104].hex()
    else:
        raise ChdFormatError(f"Versão CHD não suportada: {version}")

    return {"version": version, "logical_size": logical_size, "sha1": sha1}


def validate_chd(path: str | Path, expected_sha1: str | None, expected_logical_size: int = 0) -> tuple[bool, dict[str, int | str]]:
    """Valida o digest de conteúdo e, quando informado, o tamanho lógico."""
    info = read_chd_header(path)
    sha1 = str(info["sha1"]).lower()
    expected = (expected_sha1 or "").strip().lower()
    size_ok = expected_logical_size <= 0 or int(info["logical_size"]) == expected_logical_size
    sha1_ok = not expected or sha1 == expected
    return size_ok and sha1_ok, info
