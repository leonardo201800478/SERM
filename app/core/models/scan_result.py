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

from dataclasses import (
    dataclass,
    field,
)
from enum import Enum
from pathlib import Path
from typing import Any


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
        """
        Indica se o item foi encontrado e validado corretamente.

        Returns:
            ``True`` somente para ``VALID``.
        """

        return self is ScanStatus.VALID

    @property
    def is_missing(self) -> bool:
        """
        Indica se o item não foi encontrado.

        Returns:
            ``True`` para ``MISSING``.
        """

        return self is ScanStatus.MISSING

    @property
    def is_error(self) -> bool:
        """
        Indica se ocorreu erro durante a verificação.

        Returns:
            ``True`` para ``ERROR``.
        """

        return self is ScanStatus.ERROR

    @property
    def is_problem(self) -> bool:
        """
        Indica se o item não está em estado válido.

        Returns:
            ``True`` para qualquer estado diferente de ``VALID``.
        """

        return self is not ScanStatus.VALID


class ScanItemType(str, Enum):
    """
    Tipo de arquivo referenciado pelo LISTXML.
    """

    ROM = "rom"

    DISK = "disk"


# ============================================================================
# RESULTADO DE ROM / CHD
# ============================================================================


@dataclass(slots=True)
class RomScanResult:
    """
    Resultado da verificação de uma ROM ou CHD individual.

    O objeto representa uma única entrada do LISTXML.

    Attributes:
        machine_name:
            Nome da máquina à qual o item pertence.

        rom_name:
            Nome da ROM/CHD conforme definido no XML.

        status:
            Resultado da validação.

        expected_size:
            Tamanho esperado em bytes.

        actual_size:
            Tamanho encontrado em bytes.

        expected_crc:
            CRC esperado.

        actual_crc:
            CRC encontrado.

        expected_sha1:
            SHA1 esperado.

        actual_sha1:
            SHA1 encontrado.

        path:
            Caminho do arquivo encontrado.

        archive_path:
            Caminho do ZIP que contém a ROM, quando aplicável.

        archive_member:
            Nome do arquivo dentro do ZIP.

        item_type:
            Tipo do item: ROM ou disk.

        merge:
            Valor do atributo ``merge`` do LISTXML.

        optional:
            Indica se a ROM foi marcada como opcional.

        message:
            Mensagem adicional do scanner.

        error:
            Mensagem de erro, quando existente.
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
        """
        Indica se o item foi encontrado.

        Um item é considerado encontrado quando está em qualquer estado
        que represente uma verificação efetivamente realizada.

        Returns:
            ``True`` se o arquivo foi localizado.
        """

        return self.status not in (
            ScanStatus.MISSING,
            ScanStatus.UNKNOWN,
        )

    @property
    def valid(self) -> bool:
        """
        Indica se o item está correto.

        Returns:
            ``True`` quando o status é ``VALID``.
        """

        return self.status is ScanStatus.VALID

    @property
    def invalid(self) -> bool:
        """
        Indica se o item foi encontrado, mas não corresponde ao esperado.

        Returns:
            ``True`` quando o status é ``INVALID``.
        """

        return self.status is ScanStatus.INVALID

    @property
    def missing(self) -> bool:
        """
        Indica se o item não foi encontrado.

        Returns:
            ``True`` quando o status é ``MISSING``.
        """

        return self.status is ScanStatus.MISSING

    @property
    def has_error(self) -> bool:
        """
        Indica se houve erro durante o processamento.

        Returns:
            ``True`` quando o status é ``ERROR`` ou existe mensagem
            explícita de erro.
        """

        return (
            self.status is ScanStatus.ERROR
            or bool(self.error)
        )

    @property
    def filename(self) -> str:
        """
        Retorna o nome do arquivo encontrado.

        Returns:
            Nome do arquivo ou string vazia.
        """

        if self.path is not None:
            return self.path.name

        if self.archive_member:
            return Path(
                self.archive_member
            ).name

        return self.rom_name

    @property
    def location(self) -> Path | None:
        """
        Retorna a localização física mais relevante do item.

        Para ROMs dentro de ZIP, retorna o ZIP.

        Returns:
            Caminho físico ou ``None``.
        """

        if self.archive_path is not None:
            return self.archive_path

        return self.path

    @property
    def expected_hash(self) -> str:
        """
        Retorna o hash esperado prioritário.

        CRC é priorizado porque é o identificador principal das ROMs
        no fluxo do MAME.

        Returns:
            CRC, SHA1 ou string vazia.
        """

        if self.expected_crc:
            return self.expected_crc

        return self.expected_sha1

    @property
    def actual_hash(self) -> str:
        """
        Retorna o hash encontrado prioritário.

        Returns:
            CRC, SHA1 ou string vazia.
        """

        if self.actual_crc:
            return self.actual_crc

        return self.actual_sha1

    @property
    def size_matches(self) -> bool:
        """
        Verifica se o tamanho encontrado corresponde ao esperado.

        Returns:
            ``True`` quando os tamanhos são iguais.

        Observação:
            Quando o tamanho esperado é zero, a comparação é considerada
            inconclusiva e retorna ``False``.
        """

        if self.expected_size <= 0:
            return False

        return (
            self.expected_size
            == self.actual_size
        )

    @property
    def crc_matches(self) -> bool:
        """
        Verifica correspondência de CRC.

        Returns:
            ``True`` quando ambos existem e são iguais.
        """

        if not self.expected_crc:
            return False

        if not self.actual_crc:
            return False

        return (
            self.expected_crc.lower()
            == self.actual_crc.lower()
        )

    @property
    def sha1_matches(self) -> bool:
        """
        Verifica correspondência de SHA1.

        Returns:
            ``True`` quando ambos existem e são iguais.
        """

        if not self.expected_sha1:
            return False

        if not self.actual_sha1:
            return False

        return (
            self.expected_sha1.lower()
            == self.actual_sha1.lower()
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Converte o resultado para dicionário.

        Returns:
            Dicionário serializável.
        """

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
            "path": (
                str(self.path)
                if self.path
                else None
            ),
            "archive_path": (
                str(self.archive_path)
                if self.archive_path
                else None
            ),
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
        machine_name:
            Nome da máquina conforme o LISTXML.

        description:
            Descrição amigável da máquina.

        cloneof:
            Nome da máquina pai, quando for clone.

        roms:
            Resultados individuais das ROMs/CHDs.

        started:
            Indica se a máquina chegou a ser processada.

        error:
            Erro geral da máquina, caso exista.
    """

    machine_name: str

    description: str = ""

    cloneof: str | None = None

    roms: list[RomScanResult] = field(
        default_factory=list
    )

    started: bool = False

    error: str | None = None

    # ------------------------------------------------------------------------
    # CONTADORES
    # ------------------------------------------------------------------------

    @property
    def total(self) -> int:
        """
        Retorna a quantidade total de itens.

        Returns:
            Número de ROMs/CHDs.
        """

        return len(
            self.roms
        )

    @property
    def found(self) -> int:
        """
        Retorna a quantidade de itens encontrados.

        Returns:
            Quantidade encontrada.
        """

        return sum(
            1
            for result in self.roms
            if result.found
        )

    @property
    def valid(self) -> int:
        """
        Retorna a quantidade de itens válidos.

        Returns:
            Quantidade válida.
        """

        return sum(
            1
            for result in self.roms
            if result.valid
        )

    @property
    def missing(self) -> int:
        """
        Retorna a quantidade de itens ausentes.

        Returns:
            Quantidade ausente.
        """

        return sum(
            1
            for result in self.roms
            if result.missing
        )

    @property
    def bad(self) -> int:
        """
        Retorna a quantidade de itens inválidos.

        ``bad`` é mantido como alias semântico para ``invalid``,
        porque essa nomenclatura é usada pela GUI e pelos relatórios
        de auditoria.

        Returns:
            Quantidade inválida.
        """

        return self.invalid

    @property
    def invalid(self) -> int:
        """
        Retorna a quantidade de itens inválidos.

        Returns:
            Quantidade inválida.
        """

        return sum(
            1
            for result in self.roms
            if result.invalid
        )

    @property
    def error_count(self) -> int:
        """
        Retorna a quantidade de itens com erro.

        Returns:
            Quantidade de erros.
        """

        return sum(
            1
            for result in self.roms
            if result.has_error
        )

    @property
    def error(self) -> int:
        """
        Alias numérico utilizado pela GUI.

        Returns:
            Quantidade de itens com erro.
        """

        return self.error_count

    @property
    def cancelled(self) -> int:
        """
        Retorna a quantidade de itens cancelados.

        Returns:
            Quantidade de itens cancelados.
        """

        return sum(
            1
            for result in self.roms
            if result.status
            is ScanStatus.CANCELLED
        )

    # ------------------------------------------------------------------------
    # STATUS AGREGADO
    # ------------------------------------------------------------------------

    @property
    def is_complete(self) -> bool:
        """
        Indica se todos os itens foram processados.

        Returns:
            ``True`` quando não existem itens desconhecidos.
        """

        return all(
            result.status
            is not ScanStatus.UNKNOWN
            for result in self.roms
        )

    @property
    def is_valid(self) -> bool:
        """
        Indica se todos os itens da máquina são válidos.

        Uma máquina sem ROMs não é considerada válida.

        Returns:
            ``True`` quando todos os itens são válidos.
        """

        return (
            self.total > 0
            and self.valid == self.total
        )

    @property
    def status(self) -> ScanStatus:
        """
        Calcula o status agregado da máquina.

        A prioridade é:

            ERROR
            INVALID
            MISSING
            CANCELLED
            VALID
            UNKNOWN

        Returns:
            Status agregado.
        """

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

    # ------------------------------------------------------------------------
    # TAMANHOS
    # ------------------------------------------------------------------------

    @property
    def expected_size(self) -> int:
        """
        Retorna o tamanho total esperado.

        Returns:
            Bytes esperados.
        """

        return sum(
            max(
                0,
                result.expected_size,
            )
            for result in self.roms
        )

    @property
    def actual_size(self) -> int:
        """
        Retorna o tamanho total encontrado.

        Returns:
            Bytes encontrados.
        """

        return sum(
            max(
                0,
                result.actual_size,
            )
            for result in self.roms
        )

    # ------------------------------------------------------------------------
    # MÉTODOS
    # ------------------------------------------------------------------------

    def add_result(
        self,
        result: RomScanResult,
    ) -> None:
        """
        Adiciona um resultado individual à máquina.

        Args:
            result:
                Resultado da ROM/CHD.
        """

        self.roms.append(
            result
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Converte a máquina para dicionário.

        Returns:
            Dicionário com a máquina e seus resultados.
        """

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
            "roms": [
                result.to_dict()
                for result in self.roms
            ],
            "error_message": self.error,
        }


# ============================================================================
# RESULTADO GERAL DO SCAN
# ============================================================================


@dataclass(slots=True)
class ScanResult:
    """
    Resultado completo de uma execução do RomScanner.

    Este é o objeto de nível superior para representar uma execução.

    Attributes:
        machines:
            Resultados agregados das máquinas.

        xml_path:
            LISTXML utilizado como fonte.

        started_at:
            Momento de início.

        finished_at:
            Momento de término.

        cancelled:
            Indica se o processo foi cancelado.

        error:
            Erro geral da execução.
    """

    machines: list[MachineScanResult] = field(
        default_factory=list
    )

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
        """
        Retorna a quantidade de máquinas.

        Returns:
            Número de máquinas.
        """

        return len(
            self.machines
        )

    @property
    def total(self) -> int:
        """
        Retorna a quantidade total de itens.

        Returns:
            Total de ROMs/CHDs.
        """

        return sum(
            machine.total
            for machine in self.machines
        )

    @property
    def found(self) -> int:
        """
        Retorna a quantidade de itens encontrados.

        Returns:
            Quantidade encontrada.
        """

        return sum(
            machine.found
            for machine in self.machines
        )

    @property
    def valid(self) -> int:
        """
        Retorna a quantidade de itens válidos.

        Returns:
            Quantidade válida.
        """

        return sum(
            machine.valid
            for machine in self.machines
        )

    @property
    def missing(self) -> int:
        """
        Retorna a quantidade de itens ausentes.

        Returns:
            Quantidade ausente.
        """

        return sum(
            machine.missing
            for machine in self.machines
        )

    @property
    def bad(self) -> int:
        """
        Retorna a quantidade de itens inválidos.

        Returns:
            Quantidade inválida.
        """

        return sum(
            machine.bad
            for machine in self.machines
        )

    @property
    def error_count(self) -> int:
        """
        Retorna a quantidade de erros.

        Returns:
            Quantidade de erros.
        """

        return sum(
            machine.error
            for machine in self.machines
        )

    @property
    def error_count_total(self) -> int:
        """
        Alias explícito para ``error_count``.

        Returns:
            Quantidade total de erros.
        """

        return self.error_count

    @property
    def is_complete(self) -> bool:
        """
        Indica se o scan terminou sem cancelamento/erro.

        Returns:
            ``True`` quando o resultado está completo.
        """

        return (
            not self.cancelled
            and self.error is None
            and self.finished_at is not None
        )

    @property
    def is_valid(self) -> bool:
        """
        Indica se todos os itens encontrados estão válidos.

        Returns:
            ``True`` quando não há ausentes, inválidos ou erros.
        """

        return (
            self.total > 0
            and self.valid == self.total
        )

    # ------------------------------------------------------------------------
    # TAMANHOS
    # ------------------------------------------------------------------------

    @property
    def expected_size(self) -> int:
        """
        Retorna o tamanho esperado total.

        Returns:
            Bytes esperados.
        """

        return sum(
            machine.expected_size
            for machine in self.machines
        )

    @property
    def actual_size(self) -> int:
        """
        Retorna o tamanho encontrado total.

        Returns:
            Bytes encontrados.
        """

        return sum(
            machine.actual_size
            for machine in self.machines
        )

    # ------------------------------------------------------------------------
    # MÉTODOS
    # ------------------------------------------------------------------------

    def add_machine(
        self,
        machine: MachineScanResult,
    ) -> None:
        """
        Adiciona o resultado de uma máquina.

        Args:
            machine:
                Resultado da máquina.
        """

        self.machines.append(
            machine
        )

    def get_machine(
        self,
        machine_name: str,
    ) -> MachineScanResult | None:
        """
        Procura uma máquina pelo nome.

        Args:
            machine_name:
                Nome da máquina.

        Returns:
            MachineScanResult ou ``None``.
        """

        for machine in self.machines:

            if (
                machine.machine_name
                == machine_name
            ):
                return machine

        return None

    def to_dict(self) -> dict[str, Any]:
        """
        Converte o resultado completo para dicionário.

        Returns:
            Dicionário serializável.
        """

        return {
            "xml_path": (
                str(self.xml_path)
                if self.xml_path
                else None
            ),
            "started_at": (
                self.started_at.isoformat()
                if hasattr(
                    self.started_at,
                    "isoformat",
                )
                else self.started_at
            ),
            "finished_at": (
                self.finished_at.isoformat()
                if hasattr(
                    self.finished_at,
                    "isoformat",
                )
                else self.finished_at
            ),
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
            "machines": [
                machine.to_dict()
                for machine in self.machines
            ],
        }


# ============================================================================
# ALIASES DE COMPATIBILIDADE
# ============================================================================

# Alguns componentes antigos do projeto utilizavam nomes diferentes.
# Estes aliases permitem que a migração aconteça gradualmente sem criar
# uma segunda implementação do modelo.

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