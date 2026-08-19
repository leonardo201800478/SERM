"""Política de decisão para auditoria e reconstrução de assets MAME.

Separa estado físico, estado documental do MAME e ação de reconstrução.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class MameDumpStatus(str, Enum):
    """Estado documental do dump informado pelo LISTXML."""

    GOOD = "good"
    BAD_DUMP = "baddump"
    NO_DUMP = "nodump"
    UNKNOWN = "unknown"


class ReconstructionAction(str, Enum):
    """Ação que a reconstrução deve tomar para um item."""

    KEEP = "keep"
    SEARCH = "search"
    IGNORE = "ignore"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class RomDecision:
    """Decisão auditável para uma ROM."""

    dump_status: MameDumpStatus
    action: ReconstructionAction
    executable: bool
    blocking: bool
    reason: str


def normalize_dump_status(value: Any) -> MameDumpStatus:
    """Normaliza o atributo ``status`` do LISTXML."""
    value = str(value or "").strip().lower()
    if value == "baddump":
        return MameDumpStatus.BAD_DUMP
    if value == "nodump":
        return MameDumpStatus.NO_DUMP
    if value in ("", "good"):
        return MameDumpStatus.GOOD
    return MameDumpStatus.UNKNOWN


def classify_rom(
    *,
    physical_status: str,
    expected_size: int = 0,
    actual_size: int = 0,
    expected_crc: str = "",
    actual_crc: str = "",
    expected_sha1: str = "",
    actual_sha1: str = "",
    mame_status: Any = "good",
    optional: bool = False,
) -> RomDecision:
    """Classifica uma ROM sem alterar o resultado original do scanner.

    ``baddump`` encontrado corretamente é utilizável; ``nodump`` ausente
    não é uma falha reconstruível; ROM opcional ausente não bloqueia a
    máquina; divergências de tamanho/CRC/SHA-1 são explicadas individualmente.
    """
    dump = normalize_dump_status(mame_status)
    physical = str(physical_status or "unknown").lower()

    if physical == "valid":
        if dump is MameDumpStatus.BAD_DUMP:
            return RomDecision(
                dump, ReconstructionAction.KEEP, True, False,
                "ROM encontrada e corresponde ao dump conhecido pelo MAME; "
                "o MAME a classifica como BAD DUMP, portanto ela é mantida "
                "porque é a melhor imagem conhecida para esta definição."
            )
        return RomDecision(
            dump, ReconstructionAction.KEEP, True, False,
            "ROM encontrada e validada por tamanho/CRC/SHA-1 conforme os "
            "dados disponíveis no LISTXML."
        )

    if physical == "missing":
        if dump is MameDumpStatus.NO_DUMP:
            return RomDecision(
                dump, ReconstructionAction.IGNORE, True, False,
                "ROM ausente, mas o MAME informa NO DUMP KNOWN; não existe "
                "um dump conhecido para procurar ou reconstruir."
            )
        if optional:
            return RomDecision(
                dump, ReconstructionAction.IGNORE, True, False,
                "ROM opcional ausente; sua ausência não deve impedir a "
                "execução mínima da máquina."
            )
        if dump is MameDumpStatus.BAD_DUMP:
            return RomDecision(
                dump, ReconstructionAction.SEARCH, False, True,
                "ROM BAD DUMP conhecida está ausente; procurar o dump "
                "conhecido é permitido, mas a máquina não pode ser declarada "
                "completa enquanto ele não for encontrado."
            )
        return RomDecision(
            dump, ReconstructionAction.SEARCH, False, True,
            "ROM obrigatória não encontrada; procurar em parent/merge e nas "
            "outras origens configuradas."
        )

    if physical in {"invalid", "sha1_mismatch"}:
        problems: list[str] = []
        if expected_size > 0 and actual_size != expected_size:
            problems.append(f"tamanho esperado {expected_size} bytes, encontrado {actual_size}")
        if expected_crc and actual_crc and expected_crc.lower() != actual_crc.lower():
            problems.append(f"CRC esperado {expected_crc.lower()}, encontrado {actual_crc.lower()}")
        if expected_sha1 and actual_sha1 and expected_sha1.lower() != actual_sha1.lower():
            problems.append("SHA-1 divergente")
        if not problems:
            problems.append("o arquivo físico não corresponde aos dados de identificação conhecidos")
        return RomDecision(
            dump, ReconstructionAction.SEARCH, False, not optional,
            "ROM encontrada, mas invalidada: " + "; ".join(problems) + "."
        )

    if physical in {"error", "archive_error", "read_error"}:
        return RomDecision(
            dump, ReconstructionAction.SEARCH, False, not optional,
            "Não foi possível validar a ROM devido a erro de leitura/acesso "
            "do arquivo ou do arquivo compactado."
        )

    return RomDecision(
        dump, ReconstructionAction.BLOCK, False, not optional,
        f"Estado físico não reconhecido ({physical_status!r}); o item não "
        "pode ser considerado seguro para reconstrução."
    )
