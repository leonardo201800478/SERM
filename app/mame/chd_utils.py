"""Compatibilidade para validação de CHDs usando o chdman do MAME.

O projeto não calcula mais o SHA-1 bruto do arquivo .chd e não interpreta o
cabeçalho CHD manualmente para decidir se um disco é válido. A validação
oficial é delegada ao ``chdman verify`` e o digest lógico é obtido por
``chdman info``.
"""
from __future__ import annotations

from pathlib import Path

from .chdman_validator import ChdmanError, chdman_info, chdman_verify, validate_chd


class ChdFormatError(ValueError):
    """Mantido por compatibilidade com consumidores antigos do módulo."""


def read_chd_header(path: str | Path) -> dict[str, int | str]:
    """Retorna informações CHD obtidas pelo ``chdman info``.

    O nome antigo da função é preservado para não quebrar imports existentes.
    """
    info = chdman_info(path)
    return {
        "version": 0,
        "logical_size": int(info.get("logical_size") or 0),
        "sha1": str(info.get("sha1") or "").lower(),
    }


__all__ = [
    "ChdFormatError",
    "ChdmanError",
    "chdman_info",
    "chdman_verify",
    "read_chd_header",
    "validate_chd",
]
