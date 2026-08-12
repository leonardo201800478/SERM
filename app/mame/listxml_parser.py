"""
Parser streaming (unificado) do MAME -listxml.

Este módulo substitui as duas implementações anteriores que existiam no
projeto (``app/mame/listxml.py`` e o método privado
``DatabaseService._parse_listxml``), que eram redundantes, divergiam em
pequenos detalhes (ex.: tratamento de ``offset`` hexadecimal, extração de
``isbios``) e carregavam o XML inteiro em memória via
``ET.fromstring``.

Um ``-listxml`` de uma build atual do MAME tem mais de 45 mil elementos
``<machine>`` e facilmente ultrapassa 100 MB. Carregar isso como uma árvore
DOM completa (``ET.fromstring``) consome memória muito acima do necessário
e é mais lento do que processar em streaming.

Este módulo usa ``xml.etree.ElementTree.iterparse`` para processar o XML
incrementalmente: cada ``<machine>`` é convertido em um objeto ``Machine``
assim que seu fechamento (``</machine>``) é encontrado, e o elemento é
descartado (`clear()`) em seguida — a árvore nunca cresce além de uma
máquina por vez.

Uso típico (uma máquina de cada vez, sem acumular tudo em uma lista):

    from app.mame.listxml_parser import iter_machines

    for machine in iter_machines(caminho_ou_stream):
        ...  # inserir no banco, filtrar, etc.

``iter_machines`` aceita:
- um caminho de arquivo (``str`` ou ``Path``) contendo o XML;
- um objeto file-like já aberto (ex.: ``subprocess.Popen(...).stdout``,
  o que permite consumir a saída do MAME em tempo real, sem nunca
  materializar o XML completo como string em memória);
- uma ``str`` já contendo o XML completo (mantido apenas para
  compatibilidade/testes — nesse caso o streaming de I/O não ajuda, pois a
  string já está inteira em memória, mas o parsing continua incremental).
"""

from __future__ import annotations

import io
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import IO, Iterator, Union

from app.core.models.disk import Disk
from app.core.models.machine import Machine
from app.core.models.rom import Rom

logger = logging.getLogger(__name__)

# Quantas máquinas processar entre cada "flush" do root do parser.
# Isso evita que a lista interna de filhos do elemento raiz cresça
# indefinidamente (mesmo já com clear() em cada <machine>, o root mantém
# referências vazias). Ver _iterparse_machines.
_ROOT_FLUSH_INTERVAL = 200

SourceType = Union[str, Path, IO[str], IO[bytes]]


def iter_machines(source: SourceType) -> Iterator[Machine]:
    """Gera objetos ``Machine`` a partir de um -listxml do MAME, em streaming.

    Args:
        source: caminho para um arquivo XML, um objeto file-like (ex.:
            stdout de um subprocesso rodando ``mame -listxml``), ou uma
            string já contendo o XML completo.

    Yields:
        Machine: uma máquina por vez, já com ``roms`` e ``disks``
        preenchidos. Nenhuma lista com todas as máquinas é mantida em
        memória por este módulo — quem chama decide se quer acumular ou
        processar incrementalmente (ex.: inserir em lotes no banco).
    """
    fh, close_after = _resolve_source(source)
    try:
        yield from _iterparse_machines(fh)
    except ET.ParseError as e:
        logger.error(f"Erro ao parsear listxml: {e}")
        raise
    finally:
        if close_after:
            fh.close()


def _resolve_source(source: SourceType):
    """Normaliza a origem para um objeto file-like, retornando (fh, deve_fechar)."""
    if isinstance(source, (str, Path)):
        text = str(source)
        # Heurística simples: se "parece" XML (começa com '<' depois de
        # tirar espaços), trata como conteúdo; senão, como caminho de arquivo.
        if text.lstrip().startswith("<"):
            return io.StringIO(text), True
        return open(source, "r", encoding="utf-8", errors="ignore"), True
    # Já é um objeto file-like (texto ou bytes) — ex.: Popen.stdout
    return source, False


def _iterparse_machines(fh) -> Iterator[Machine]:
    context = iter(ET.iterparse(fh, events=("start", "end")))
    _, root = next(context)  # captura o elemento raiz (<mame> ou <mess>)

    count = 0
    for event, elem in context:
        if event != "end" or elem.tag != "machine":
            continue

        yield _build_machine(elem)

        # Libera a memória do elemento processado. O root ainda mantém uma
        # referência "vazia" ao elemento; periodicamente limpamos o root
        # também para não deixar essa lista crescer sem limite em datasets
        # muito grandes.
        elem.clear()
        count += 1
        if count % _ROOT_FLUSH_INTERVAL == 0:
            root.clear()


def _build_machine(elem: ET.Element) -> Machine:
    machine = Machine()
    machine.name = elem.get("name", "")
    machine.sourcefile = elem.get("sourcefile", "")
    machine.cloneof = elem.get("cloneof", "")
    machine.romof = elem.get("romof", "")
    machine.sampleof = elem.get("sampleof", "")
    machine.is_bios = elem.get("isbios", "no") == "yes"
    machine.is_device = elem.get("isdevice", "no") == "yes"
    machine.is_mechanical = elem.get("ismechanical", "no") == "yes"
    machine.runnable = elem.get("runnable", "yes") == "yes"

    desc_elem = elem.find("description")
    machine.description = (desc_elem.text or "") if desc_elem is not None else ""

    year_elem = elem.find("year")
    machine.year = (year_elem.text or "") if year_elem is not None else ""

    manuf_elem = elem.find("manufacturer")
    machine.manufacturer = (manuf_elem.text or "") if manuf_elem is not None else ""

    _apply_driver_info(machine, elem.find("driver"))

    machine.roms = [_build_rom(rom_elem) for rom_elem in elem.findall("rom")]
    machine.disks = [_build_disk(disk_elem) for disk_elem in elem.findall("disk")]

    return machine


def _apply_driver_info(machine: Machine, driver_elem: ET.Element | None) -> None:
    if driver_elem is None:
        machine.emulation_status = "unknown"
        machine.driver_status = ""
        return

    status = driver_elem.get("status", "")
    machine.driver_status = status
    if status == "good":
        machine.emulation_status = "working"
    elif status == "imperfect":
        machine.emulation_status = "imperfect"
    else:
        machine.emulation_status = "not_working"

    machine.savestate = driver_elem.get("savestate", "unsupported") == "supported"
    machine.requires_artwork = driver_elem.get("requiresartwork", "no") == "yes"
    machine.unofficial = driver_elem.get("unofficial", "no") == "yes"
    machine.nosoundhardware = driver_elem.get("nosoundhardware", "no") == "yes"
    machine.incomplete = driver_elem.get("incomplete", "no") == "yes"


def _build_rom(rom_elem: ET.Element) -> Rom:
    rom = Rom()
    rom.name = rom_elem.get("name", "")
    rom.size = _safe_int(rom_elem.get("size", "0"))
    rom.crc = rom_elem.get("crc", "")
    rom.sha1 = rom_elem.get("sha1", "")
    rom.merge = rom_elem.get("merge", "")
    rom.region = rom_elem.get("region", "")
    rom.offset = _safe_int(rom_elem.get("offset", "0"), allow_hex=True)
    rom.status = rom_elem.get("status", "good")
    rom.optional = rom_elem.get("optional", "no") == "yes"
    rom.bios = rom_elem.get("bios", "")
    return rom


def _build_disk(disk_elem: ET.Element) -> Disk:
    disk = Disk()
    disk.name = disk_elem.get("name", "")
    disk.sha1 = disk_elem.get("sha1", "")
    disk.merge = disk_elem.get("merge", "")
    disk.region = disk_elem.get("region", "")
    disk.index = _safe_int(disk_elem.get("index", "0"))
    disk.writable = disk_elem.get("writable", "no") == "yes"
    disk.status = disk_elem.get("status", "good")
    disk.optional = disk_elem.get("optional", "no") == "yes"
    return disk


def _safe_int(value: str, *, allow_hex: bool = False) -> int:
    """Converte para int aceitando decimal e, opcionalmente, hexadecimal.

    O atributo ``offset`` do MAME listxml costuma vir em hexadecimal sem o
    prefixo ``0x``. Tentamos decimal primeiro (caso comum de ``size`` e
    ``index``) e caímos para base 16 apenas quando ``allow_hex`` é True e o
    valor não é um decimal válido.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    if allow_hex:
        try:
            return int(value, 16)
        except (TypeError, ValueError):
            pass
    logger.warning(f"Valor numérico inválido '{value}', usando 0.")
    return 0
