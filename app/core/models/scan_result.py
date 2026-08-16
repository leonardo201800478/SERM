"""
MAME Set Builder
================

Modelos de resultado do escaneamento de ROMs.

Este módulo contém somente estruturas de dados.

Responsabilidades
-----------------
- Representar o resultado da verificação de uma ROM.
- Representar o resultado da verificação de um CHD.
- Agregar resultados por máquina.
- Agregar resultados de um scan completo.
- Fornecer propriedades auxiliares para a GUI e serviços.

Não contém
----------
- acesso ao filesystem;
- acesso ao SQLite;
- código Qt;
- execução de threads;
- lógica de busca de ROMs;
- lógica de cálculo de CRC/SHA1.

A lógica de escaneamento pertence a:

    app/mame/rom_scanner.py

A apresentação pertence a:

    app/gui/tabs/scan_roms_tab.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterator


# ============================================================================
# ENUMS
# ============================================================================


class ScanStatus(str, Enum):
    """
    Estados possíveis de um item escaneado.

    Os valores são strings para facilitar:

    - serialização;
    - persistência;
    - logging;
    - integração com a GUI;
    - comparação com valores vindos do XML.
    """

    VALID = "valid"
    MISSING = "missing"
    INVALID = "invalid"
    ERROR = "error"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"

    @property
    def is_success(self) -> bool:
        """Indica se o item foi encontrado e validado corretamente."""
        return self is ScanStatus.VALID

    @property
    def is_missing(self) -> bool:
        """Indica se o item não foi encontrado."""
        return self is ScanStatus.MISSING

    @property
    def is_error(self) -> bool:
        """Indica se ocorreu erro durante a verificação."""
        return self is ScanStatus.ERROR

    @property
    def is_problem(self) -> bool:
        """Indica se o item não está em estado válido."""
        return self is not ScanStatus.VALID


class ScanItemType(str, Enum):
    """Tipo de arquivo referenciado pelo LISTXML."""

    ROM = "rom"
    DISK = "disk"


# ============================================================================
# RESULTADO DE ROM / CHD
# ============================================================================


@dataclass(slots=True)
class RomScanResult:
    """
    Resultado da verificação de uma ROM ou CHD individual.

    Attributes:
        machine_name: Nome da máquina à qual o item pertence.
        rom_name: Nome da ROM/CHD conforme definido no XML.
        status: Resultado da validação.
        expected_size: Tamanho esperado em bytes.
        actual_size: Tamanho encontrado em bytes.
        expected_crc: CRC esperado.
        actual_crc: CRC encontrado.
        expected_sha1: SHA1 esperado.
        actual_sha1: SHA1 encontrado.
        path: Caminho do arquivo encontrado.
        archive_path: Caminho do ZIP que contém a ROM, quando aplicável.
        archive_member: Nome do arquivo dentro do ZIP.
        item_type: Tipo do item: ROM ou disk.
        merge: Valor do atributo ``merge`` do LISTXML.
        optional: Indica se a ROM foi marcada como opcional.
        message: Mensagem adicional do scanner.
        error: Mensagem de erro, quando existente.
    """

    machine_name: str
    rom_name: str

    status: ScanStatus = ScanStatus.UNKNOWN

    expected_size: int = 0
    actual_size: int = 0

    expected_crc: str = ""
    actual_crc: str = ""

    expected_sha1: str = ""
    actual_sha1: str = ""

    path: Path | None = None
    archive_path: Path | None = None
    archive_member: str | None = None

    item_type: ScanItemType = ScanItemType.ROM
    merge: str | None = None
    optional: bool = False

    message: str = ""
    error: str | None = None

    # ------------------------------------------------------------------------
    # PROPRIEDADES DE COMPATIBILIDADE
    # ------------------------------------------------------------------------

    @property
    def found(self) -> bool:
        """Indica se o item foi encontrado."""
        return self.status not in (ScanStatus.MISSING, ScanStatus.UNKNOWN)

    @property
    def valid(self) -> bool:
        """Indica se o item está correto."""
        return self.status is ScanStatus.VALID

    @property
    def invalid(self) -> bool:
        """Indica se o item foi encontrado, mas não corresponde ao esperado."""
        return self.status is ScanStatus.INVALID

    @property
    def missing(self) -> bool:
        """Indica se o item não foi encontrado."""
        return self.status is ScanStatus.MISSING

    @property
    def has_error(self) -> bool:
        """Indica se houve erro durante o processamento."""
        return self.status is ScanStatus.ERROR or bool(self.error)

    @property
    def filename(self) -> str:
        """Retorna o nome do arquivo encontrado."""
        if self.path is not None:
            return self.path.name
        if self.archive_member:
            return Path(self.archive_member).name
        return self.rom_name

    @property
    def location(self) -> Path | None:
        """Retorna a localização física mais relevante do item."""
        if self.archive_path is not None:
            return self.archive_path
        return self.path

    @property
    def expected_hash(self) -> str:
        """Retorna o hash esperado prioritário (CRC > SHA1)."""
        return self.expected_crc or self.expected_sha1

    @property
    def actual_hash(self) -> str:
        """Retorna o hash encontrado prioritário (CRC > SHA1)."""
        return self.actual_crc or self.actual_sha1

    @property
    def size_matches(self) -> bool:
        """Verifica se o tamanho encontrado corresponde ao esperado."""
        if self.expected_size <= 0:
            return False
        return self.expected_size == self.actual_size

    @property
    def crc_matches(self) -> bool:
        """Verifica correspondência de CRC."""
        return bool(self.expected_crc and self.actual_crc and
                    self.expected_crc.lower() == self.actual_crc.lower())

    @property
    def sha1_matches(self) -> bool:
        """Verifica correspondência de SHA1."""
        return bool(self.expected_sha1 and self.actual_sha1 and
                    self.expected_sha1.lower() == self.actual_sha1.lower())

    def to_dict(self) -> dict[str, Any]:
        """Converte o resultado para dicionário."""
        return {
            "machine_name": self.machine_name,
            "rom_name": self.rom_name,
            "status": self.status.value,
            "expected_size": self.expected_size,
            "actual_size": self.actual_size,
            "expected_crc": self.expected_crc,
            "actual_crc": self.actual_crc,
            "expected_sha1": self.expected_sha1,
            "actual_sha1": self.actual_sha1,
            "path": str(self.path) if self.path else None,
            "archive_path": str(self.archive_path) if self.archive_path else None,
            "archive_member": self.archive_member,
            "item_type": self.item_type.value,
            "merge": self.merge,
            "optional": self.optional,
            "message": self.message,
            "error": self.error,
        }


# ============================================================================
# RESULTADO DE MÁQUINA
# ============================================================================


@dataclass(slots=True)
class MachineScanResult:
    """
    Resultado agregado do escaneamento de uma máquina.

    Attributes:
        machine_name: Nome da máquina conforme o LISTXML.
        description: Descrição amigável da máquina.
        cloneof: Nome da máquina pai, quando for clone.
        roms: Resultados individuais das ROMs/CHDs.
        started: Indica se a máquina chegou a ser processada.
        error: Erro geral da máquina, caso exista.
    """

    machine_name: str
    description: str = ""
    cloneof: str | None = None
    roms: list[RomScanResult] = field(default_factory=list)
    started: bool = False
    error: str | None = None

    # ------------------------------------------------------------------------
    # CONTADORES
    # ------------------------------------------------------------------------

    @property
    def total(self) -> int:
        """Quantidade total de itens."""
        return len(self.roms)

    @property
    def found(self) -> int:
        """Quantidade de itens encontrados."""
        return sum(1 for r in self.roms if r.found)

    @property
    def valid(self) -> int:
        """Quantidade de itens válidos."""
        return sum(1 for r in self.roms if r.valid)

    @property
    def missing(self) -> int:
        """Quantidade de itens ausentes."""
        return sum(1 for r in self.roms if r.missing)

    @property
    def invalid(self) -> int:
        """Quantidade de itens inválidos."""
        return sum(1 for r in self.roms if r.invalid)

    @property
    def bad(self) -> int:
        """Alias para invalid (usado pela GUI)."""
        return self.invalid

    @property
    def error_count(self) -> int:
        """Quantidade de itens com erro."""
        return sum(1 for r in self.roms if r.has_error)

    @property
    def error(self) -> int:
        """Alias para error_count."""
        return self.error_count

    @property
    def cancelled(self) -> int:
        """Quantidade de itens cancelados."""
        return sum(1 for r in self.roms if r.status is ScanStatus.CANCELLED)

    # ------------------------------------------------------------------------
    # STATUS AGREGADO
    # ------------------------------------------------------------------------

    @property
    def is_complete(self) -> bool:
        """Indica se todos os itens foram processados."""
        return all(r.status is not ScanStatus.UNKNOWN for r in self.roms)

    @property
    def is_valid(self) -> bool:
        """Indica se todos os itens da máquina são válidos."""
        return self.total > 0 and self.valid == self.total

    @property
    def status(self) -> ScanStatus:
        """Calcula o status agregado da máquina."""
        if self.error_count > 0:
            return ScanStatus.ERROR
        if self.invalid > 0:
            return ScanStatus.INVALID
        if self.missing > 0:
            return ScanStatus.MISSING
        if self.cancelled > 0:
            return ScanStatus.CANCELLED
        if self.valid == self.total and self.total > 0:
            return ScanStatus.VALID
        return ScanStatus.UNKNOWN

    @property
    def has_problems(self) -> bool:
        """Indica se a máquina possui algum item com problema."""
        return any(r.status.is_problem for r in self.roms)

    # ------------------------------------------------------------------------
    # TAMANHOS
    # ------------------------------------------------------------------------

    @property
    def expected_size(self) -> int:
        """Tamanho total esperado em bytes."""
        return sum(max(0, r.expected_size) for r in self.roms)

    @property
    def actual_size(self) -> int:
        """Tamanho total encontrado em bytes."""
        return sum(max(0, r.actual_size) for r in self.roms)

    # ------------------------------------------------------------------------
    # MÉTODOS
    # ------------------------------------------------------------------------

    def add_result(self, result: RomScanResult) -> None:
        """Adiciona um resultado individual à máquina."""
        self.roms.append(result)

    def to_dict(self) -> dict[str, Any]:
        """Converte a máquina para dicionário."""
        return {
            "machine_name": self.machine_name,
            "description": self.description,
            "cloneof": self.cloneof,
            "started": self.started,
            "status": self.status.value,
            "total": self.total,
            "found": self.found,
            "valid": self.valid,
            "missing": self.missing,
            "bad": self.bad,
            "error": self.error_count,
            "expected_size": self.expected_size,
            "actual_size": self.actual_size,
            "roms": [r.to_dict() for r in self.roms],
            "error_message": self.error,
        }


# ============================================================================
# RESULTADO GERAL DO SCAN
# ============================================================================


@dataclass(slots=True)
class ScanResult:
    """
    Resultado completo de uma execução do RomScanner.

    Attributes:
        machines: Resultados agregados das máquinas.
        xml_path: LISTXML utilizado como fonte.
        started_at: Momento de início.
        finished_at: Momento de término.
        cancelled: Indica se o processo foi cancelado.
        error: Erro geral da execução.
    """

    machines: list[MachineScanResult] = field(default_factory=list)
    xml_path: Path | None = None
    started_at: Any = None
    finished_at: Any = None
    cancelled: bool = False
    error: str | None = None

    # ------------------------------------------------------------------------
    # CONTADORES
    # ------------------------------------------------------------------------

    @property
    def machine_count(self) -> int:
        """Número de máquinas."""
        return len(self.machines)

    @property
    def total(self) -> int:
        """Total de itens (ROMs + CHDs)."""
        return sum(m.total for m in self.machines)

    @property
    def found(self) -> int:
        """Itens encontrados."""
        return sum(m.found for m in self.machines)

    @property
    def valid(self) -> int:
        """Itens válidos."""
        return sum(m.valid for m in self.machines)

    @property
    def missing(self) -> int:
        """Itens ausentes."""
        return sum(m.missing for m in self.machines)

    @property
    def bad(self) -> int:
        """Itens inválidos."""
        return sum(m.bad for m in self.machines)

    @property
    def error_count(self) -> int:
        """Erros."""
        return sum(m.error_count for m in self.machines)

    @property
    def expected_size(self) -> int:
        """Tamanho total esperado em bytes."""
        return sum(m.expected_size for m in self.machines)

    @property
    def actual_size(self) -> int:
        """Tamanho total encontrado em bytes."""
        return sum(m.actual_size for m in self.machines)

    @property
    def is_complete(self) -> bool:
        """Indica se o scan terminou sem cancelamento/erro."""
        return not self.cancelled and self.error is None and self.finished_at is not None

    @property
    def is_valid(self) -> bool:
        """Indica se todos os itens encontrados estão válidos."""
        return self.total > 0 and self.valid == self.total

    # ------------------------------------------------------------------------
    # MÉTODOS AUXILIARES
    # ------------------------------------------------------------------------

    def problem_machines(self) -> Iterator[MachineScanResult]:
        """
        Gera as máquinas que possuem pelo menos um item com problema.

        Um problema é definido como:
            - ausente (MISSING)
            - inválido (INVALID)
            - erro (ERROR)

        Máquinas com todos os itens válidos não são incluídas.

        Yields:
            MachineScanResult para cada máquina com problemas.
        """
        for machine in self.machines:
            if machine.has_problems:
                yield machine

    def add_machine(self, machine: MachineScanResult) -> None:
        """Adiciona o resultado de uma máquina."""
        self.machines.append(machine)

    def get_machine(self, machine_name: str) -> MachineScanResult | None:
        """Procura uma máquina pelo nome."""
        for machine in self.machines:
            if machine.machine_name == machine_name:
                return machine
        return None

    def to_dict(self) -> dict[str, Any]:
        """Converte o resultado completo para dicionário."""
        return {
            "xml_path": str(self.xml_path) if self.xml_path else None,
            "started_at": self.started_at.isoformat() if hasattr(self.started_at, "isoformat") else self.started_at,
            "finished_at": self.finished_at.isoformat() if hasattr(self.finished_at, "isoformat") else self.finished_at,
            "cancelled": self.cancelled,
            "error": self.error,
            "machine_count": self.machine_count,
            "total": self.total,
            "found": self.found,
            "valid": self.valid,
            "missing": self.missing,
            "bad": self.bad,
            "error_count": self.error_count,
            "expected_size": self.expected_size,
            "actual_size": self.actual_size,
            "machines": [m.to_dict() for m in self.machines],
        }


# ============================================================================
# ALIASES DE COMPATIBILIDADE
# ============================================================================

RomResult = RomScanResult
MachineResult = MachineScanResult
ScanSummary = ScanResult


__all__ = [
    "ScanStatus",
    "ScanItemType",
    "RomScanResult",
    "MachineScanResult",
    "ScanResult",
    "RomResult",
    "MachineResult",
    "ScanSummary",
]