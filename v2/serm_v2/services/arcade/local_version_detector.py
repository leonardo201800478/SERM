"""Detecta a versão declarada por arquivos locais do projeto-SNAPS."""

from __future__ import annotations

import re
from pathlib import Path


_VERSION_RE = re.compile(r"\b(?:v(?:ersion)?\s*)?(0\.\d{3})\b", re.IGNORECASE)
_MAME_VERSION_RE = re.compile(r"\bMAME\s+v?(0\.\d{3})\b", re.IGNORECASE)


def detect_local_version(path: Path) -> str | None:
    """Retorna a versão encontrada no próprio arquivo ou no nome do ZIP.

    A ordem de prioridade é: cabeçalho explícito MAME, versão declarada no
    cabeçalho, versão no nome do arquivo. Somente o início de arquivos de
    texto é lido.
    """
    path = Path(path)
    if not path.is_file():
        return None

    version = _version_from_filename(path.name)
    if path.suffix.casefold() == ".zip":
        return version

    try:
        with path.open("rb") as stream:
            data = stream.read(64 * 1024)
    except OSError:
        return version

    text = data.decode("utf-8-sig", errors="replace")
    explicit = _MAME_VERSION_RE.search(text)
    if explicit:
        return explicit.group(1)

    # Os DATs do projeto-SNAPS podem declarar a versão como "v0.289" ou
    # "Version 0.289", enquanto os INIs normalmente usam apenas "0.289".
    # A busca fica limitada ao início do arquivo para evitar capturar números
    # pertencentes ao conteúdo das entradas.
    header = text[:16 * 1024]
    generic = _VERSION_RE.search(header)
    if generic:
        return generic.group(1)
    return version


def _version_from_filename(filename: str) -> str | None:
    """Extrai versões publicadas no nome de ZIP/arquivo."""
    stem = Path(filename).stem
    patterns = (
        r"(?:MAME_samples_|nplayers|pS_(?:category|version|messinfo|SupportFiles_))"
        r"(0\d{2}|0\.\d{3})",
        r"\b(0\.\d{3})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, stem, re.IGNORECASE)
        if not match:
            continue
        value = match.group(1)
        if value.startswith("0") and "." not in value:
            return f"0.{value[1:]}"
        return value
    return None


__all__ = ["detect_local_version"]
