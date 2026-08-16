"""
MAME Set Builder
================

Parser streaming do arquivo ``mame -listxml``.

Este módulo transforma o LISTXML do MAME em objetos de domínio.

Características
---------------
* Parsing incremental com ``xml.etree.ElementTree.iterparse``;
* Não carrega o XML inteiro em memória;
* Compatível com arquivos grandes de LISTXML;
* Aceita Path, str, bytes e file-like objects;
* Extrai os dados principais de ``machine``;
* Extrai ROMs;
* Extrai disks/CHDs;
* Extrai BIOS;
* Extrai devices;
* Extrai chips;
* Extrai displays;
* Extrai input/control;
* Extrai features;
* Extrai software lists;
* Extrai slots e slot options;
* Extrai informações do driver;
* Preserva atributos do XML para utilização posterior;
* Tratamento seguro de números decimais e hexadecimais.

Fluxo
-----

    listxml.xml
        |
        v
    iter_machines()
        |
        v
    Machine
        |
        +-- Rom
        +-- Disk
        +-- BIOS
        +-- Device
        +-- Chip
        +-- Display
        +-- Input
        +-- Control
        +-- Feature
        +-- SoftwareList
        +-- Slot
        +-- SlotOption

IMPORTANTE
----------
Os modelos especializados serão mantidos compatíveis com este parser.
Durante a reconstrução dos modelos ``machine.py``, ``rom.py`` e
``disk.py``, os campos utilizados aqui deverão permanecer com os mesmos
nomes.

O parser não grava diretamente no banco de dados.

Essa separação é intencional:

    Parser -> Modelos -> Serviços -> Database

Assim o mesmo parser pode ser utilizado por:

* importação inicial do LISTXML;
* filtros;
* geração de XML;
* Scan ROMs;
* testes automatizados;
* reconstrução de sets.
"""

from __future__ import annotations

import io
import logging
import xml.etree.ElementTree as ET

from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Iterator, Union

from app.core.models.disk import Disk
from app.core.models.machine import Machine
from app.core.models.rom import Rom


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CONFIGURAÇÃO
# ---------------------------------------------------------------------------

ROOT_FLUSH_INTERVAL = 200

SourceType = Union[
    str,
    Path,
    bytes,
    bytearray,
    IO[str],
    IO[bytes],
]


# ---------------------------------------------------------------------------
# MODELOS AUXILIARES
# ---------------------------------------------------------------------------

@dataclass
class BiosInfo:
    """
    Representa uma entrada de BIOS encontrada no LISTXML.

    O elemento ``rom`` pode possuir o atributo ``bios``. Entretanto,
    também existe informação de BIOS associada à máquina em algumas
    versões/estruturas do LISTXML.

    Este objeto mantém essa informação separada para posterior persistência.
    """

    name: str = ""
    description: str = ""
    is_default: bool = False


@dataclass
class DeviceInfo:
    """
    Representa um device de uma máquina MAME.
    """

    tag: str = ""
    name: str = ""


@dataclass
class ChipInfo:
    """
    Representa um chip físico/lógico descrito pelo LISTXML.
    """

    chip_type: str = ""
    tag: str = ""
    name: str = ""
    clock: int = 0


@dataclass
class DisplayInfo:
    """
    Representa um display da máquina.
    """

    tag: str = ""
    display_type: str = ""
    rotate: int = 0
    flipx: bool = False
    width: int = 0
    height: int = 0
    refresh: float = 0.0


@dataclass
class ControlInfo:
    """
    Representa um controle associado a uma entrada.
    """

    control_type: str = ""
    player: int = 0
    buttons: int = 0
    minimum: int = 0
    maximum: int = 0
    sensitivity: int = 0
    keydelta: int = 0
    reverse: bool = False
    ways: int = 0


@dataclass
class InputInfo:
    """
    Representa as informações gerais de entrada da máquina.

    ``controls`` contém os controles individuais encontrados dentro
    do elemento ``input``.
    """

    players: int = 1
    coins: int = 0
    service: int = 0
    tilt: bool = False

    controls: list[ControlInfo] = field(
        default_factory=list
    )


@dataclass
class FeatureInfo:
    """
    Representa uma feature do driver MAME.
    """

    feature_type: str = ""
    status: str = ""
    overall: str = ""


@dataclass
class SoftwareListInfo:
    """
    Representa uma software list associada à máquina.
    """

    tag: str = ""
    name: str = ""
    status: str = ""
    filter: str = ""


@dataclass
class SlotOptionInfo:
    """
    Representa uma opção de slot.
    """

    name: str = ""
    devname: str = ""
    is_default: bool = False


@dataclass
class SlotInfo:
    """
    Representa um slot da máquina.
    """

    name: str = ""

    options: list[SlotOptionInfo] = field(
        default_factory=list
    )


@dataclass
class ChdDependencyInfo:
    """
    Representa uma dependência de CHD.

    Nem todas as versões do LISTXML utilizam um elemento explícito
    ``chd_dependency``. Quando disponível, ele será convertido para
    este objeto.
    """

    name: str = ""
    sha1: str = ""
    region: str = ""
    required: bool = True


# ---------------------------------------------------------------------------
# API PÚBLICA
# ---------------------------------------------------------------------------

def iter_machines(
    source: SourceType,
) -> Iterator[Machine]:
    """
    Itera sobre as máquinas de um LISTXML.

    O XML é processado em streaming. Apenas uma máquina permanece
    materializada durante cada iteração.

    Args:
        source:
            Pode ser:

            * caminho ``str``;
            * ``Path``;
            * conteúdo XML em ``str``;
            * conteúdo XML em ``bytes``;
            * objeto file-like;
            * ``stdout`` de um subprocesso executando MAME.

    Yields:
        ``Machine``:

            Uma máquina por vez, contendo as ROMs, disks e demais
            informações disponíveis.

    Raises:
        FileNotFoundError:
            Quando o caminho informado não existe.

        ET.ParseError:
            Quando o XML é inválido.

        OSError:
            Quando ocorre erro durante a leitura do arquivo.
    """

    file_handle, close_after = _resolve_source(source)

    try:
        yield from _iterparse_machines(file_handle)

    except ET.ParseError as exc:
        logger.error(
            "Erro ao interpretar LISTXML: %s",
            exc,
        )
        raise

    finally:
        if close_after:
            file_handle.close()


def parse(
    source: SourceType,
) -> list[Machine]:
    """
    Faz o parsing completo do LISTXML e retorna uma lista de máquinas.

    Atenção:
        Diferentemente de ``iter_machines()``, este método acumula todas
        as máquinas em memória.

    Deve ser utilizado apenas quando o chamador realmente precisar de
    uma coleção completa.

    Para importações grandes, prefira:

    ::

        for machine in iter_machines(path):
            ...

    Args:
        source:
            Origem do LISTXML.

    Returns:
        Lista de ``Machine``.
    """

    return list(
        iter_machines(source)
    )


def parse_file(
    path: str | Path,
) -> list[Machine]:
    """
    Atalho para realizar parsing de um arquivo LISTXML.

    Args:
        path:
            Caminho do arquivo XML.

    Returns:
        Lista de máquinas.
    """

    return parse(path)


# ---------------------------------------------------------------------------
# RESOLUÇÃO DA ORIGEM
# ---------------------------------------------------------------------------

def _resolve_source(
    source: SourceType,
) -> tuple[IO[str] | IO[bytes], bool]:
    """
    Normaliza a origem para um objeto file-like.

    Args:
        source:
            Origem do XML.

    Returns:
        Tupla:

            ``(file_handle, close_after)``

        ``close_after`` informa se o parser é responsável por fechar
        o objeto.

    Raises:
        TypeError:
            Quando o tipo da origem não é suportado.

        FileNotFoundError:
            Quando um caminho informado não existe.
    """

    # ------------------------------------------------------------------
    # PATH
    # ------------------------------------------------------------------

    if isinstance(source, Path):
        return (
            source.open(
                "rb"
            ),
            True,
        )

    # ------------------------------------------------------------------
    # STRING
    # ------------------------------------------------------------------

    if isinstance(source, str):

        stripped = source.lstrip()

        # Conteúdo XML
        if stripped.startswith("<"):
            return (
                io.StringIO(source),
                True,
            )

        # Caminho
        return (
            open(
                source,
                "rb",
            ),
            True,
        )

    # ------------------------------------------------------------------
    # BYTES
    # ------------------------------------------------------------------

    if isinstance(
        source,
        (bytes, bytearray),
    ):
        return (
            io.BytesIO(bytes(source)),
            True,
        )

    # ------------------------------------------------------------------
    # FILE-LIKE
    # ------------------------------------------------------------------

    if hasattr(
        source,
        "read",
    ):
        return (
            source,
            False,
        )

    raise TypeError(
        "Origem do LISTXML não suportada: "
        f"{type(source)!r}"
    )


# ---------------------------------------------------------------------------
# PARSING STREAMING
# ---------------------------------------------------------------------------

def _iterparse_machines(
    file_handle: IO[str] | IO[bytes],
) -> Iterator[Machine]:
    """
    Processa o XML incrementalmente.

    Apenas elementos ``machine`` são entregues ao chamador.

    A limpeza periódica da raiz evita que referências aos elementos
    já processados permaneçam acumuladas na árvore.
    """

    context = ET.iterparse(
        file_handle,
        events=(
            "start",
            "end",
        ),
    )

    try:
        _, root = next(context)

    except StopIteration:
        return

    count = 0

    for event, element in context:

        if (
            event != "end"
            or _strip_namespace(element.tag) != "machine"
        ):
            continue

        machine = _build_machine(
            element
        )

        yield machine

        # Libera a máquina processada.
        element.clear()

        count += 1

        if (
            count % ROOT_FLUSH_INTERVAL
            == 0
        ):
            root.clear()

        if count % 1000 == 0:
            logger.debug(
                "LISTXML: %d máquinas processadas.",
                count,
            )


# ---------------------------------------------------------------------------
# MACHINE
# ---------------------------------------------------------------------------

def _build_machine(
    element: ET.Element,
) -> Machine:
    """
    Constrói um objeto ``Machine`` a partir de ``<machine>``.

    Args:
        element:
            Elemento XML ``machine``.

    Returns:
        Máquina preenchida.
    """

    machine = Machine()

    # ------------------------------------------------------------------
    # ATRIBUTOS BÁSICOS
    # ------------------------------------------------------------------

    machine.name = _get_attr(
        element,
        "name",
    )

    machine.sourcefile = _get_attr(
        element,
        "sourcefile",
    )

    machine.cloneof = _get_attr(
        element,
        "cloneof",
    )

    machine.romof = _get_attr(
        element,
        "romof",
    )

    machine.sampleof = _get_attr(
        element,
        "sampleof",
    )

    machine.is_bios = _get_bool_attr(
        element,
        "isbios",
    )

    machine.is_device = _get_bool_attr(
        element,
        "isdevice",
    )

    machine.is_mechanical = _get_bool_attr(
        element,
        "ismechanical",
    )

    machine.runnable = _get_bool_attr(
        element,
        "runnable",
        default=True,
    )

    # ------------------------------------------------------------------
    # TEXTOS
    # ------------------------------------------------------------------

    machine.description = _find_text(
        element,
        "description",
    )

    machine.year = _find_text(
        element,
        "year",
    )

    machine.manufacturer = _find_text(
        element,
        "manufacturer",
    )

    # ------------------------------------------------------------------
    # DRIVER
    # ------------------------------------------------------------------

    _apply_driver_info(
        machine,
        element.find("driver"),
    )

    # ------------------------------------------------------------------
    # ROMS
    # ------------------------------------------------------------------

    machine.roms = [
        _build_rom(rom_element)
        for rom_element
        in _find_children(
            element,
            "rom",
        )
    ]

    # ------------------------------------------------------------------
    # DISKS
    # ------------------------------------------------------------------

    machine.disks = [
        _build_disk(disk_element)
        for disk_element
        in _find_children(
            element,
            "disk",
        )
    ]

    # ------------------------------------------------------------------
    # DADOS AUXILIARES
    # ------------------------------------------------------------------

    bios = [
        _build_bios(rom)
        for rom in machine.roms
        if getattr(
            rom,
            "bios",
            "",
        )
    ]

    devices = [
        _build_device(device)
        for device
        in _find_children(
            element,
            "device",
        )
    ]

    chips = [
        _build_chip(chip)
        for chip
        in _find_children(
            element,
            "chip",
        )
    ]

    displays = [
        _build_display(display)
        for display
        in _find_children(
            element,
            "display",
        )
    ]

    input_info = _build_input(
        element.find("input")
    )

    features = [
        _build_feature(feature)
        for feature
        in _find_children(
            element,
            "feature",
        )
    ]

    software_lists = [
        _build_software_list(item)
        for item
        in _find_children(
            element,
            "softwarelist",
        )
    ]

    slots = [
        _build_slot(slot)
        for slot
        in _find_children(
            element,
            "slot",
        )
    ]

    chd_dependencies = [
        _build_chd_dependency(item)
        for item
        in _find_children(
            element,
            "chd_dependency",
        )
    ]

    # ------------------------------------------------------------------
    # ATRIBUTOS AUXILIARES
    # ------------------------------------------------------------------
    #
    # Os modelos serão ampliados no próximo passo da reconstrução.
    #
    # Enquanto isso, manter os dados como atributos opcionais torna
    # este parser compatível com a evolução dos modelos sem descartar
    # informação do LISTXML.
    #
    # ------------------------------------------------------------------

    _set_optional_attribute(
        machine,
        "bios",
        bios,
    )

    _set_optional_attribute(
        machine,
        "devices",
        devices,
    )

    _set_optional_attribute(
        machine,
        "chips",
        chips,
    )

    _set_optional_attribute(
        machine,
        "displays",
        displays,
    )

    _set_optional_attribute(
        machine,
        "input",
        input_info,
    )

    _set_optional_attribute(
        machine,
        "features",
        features,
    )

    _set_optional_attribute(
        machine,
        "software_lists",
        software_lists,
    )

    _set_optional_attribute(
        machine,
        "slots",
        slots,
    )

    _set_optional_attribute(
        machine,
        "chd_dependencies",
        chd_dependencies,
    )

    return machine


# ---------------------------------------------------------------------------
# DRIVER
# ---------------------------------------------------------------------------

def _apply_driver_info(
    machine: Machine,
    driver_element: ET.Element | None,
) -> None:
    """
    Extrai as informações do elemento ``driver``.

    O MAME fornece um status do driver que normalmente pode ser:

    * ``good``
    * ``imperfect``
    * ``preliminary``

    O projeto utiliza ``emulation_status`` para uma representação
    simplificada desse estado.

    Args:
        machine:
            Máquina que receberá os dados.

        driver_element:
            Elemento ``driver``.
    """

    if driver_element is None:

        machine.driver_status = ""

        machine.emulation_status = (
            "unknown"
        )

        return

    status = _get_attr(
        driver_element,
        "status",
    )

    machine.driver_status = status

    status_lower = status.lower()

    if status_lower == "good":
        machine.emulation_status = "working"

    elif status_lower == "imperfect":
        machine.emulation_status = "imperfect"

    elif status_lower in (
        "preliminary",
        "bad",
    ):
        machine.emulation_status = (
            "not_working"
        )

    else:
        machine.emulation_status = (
            status_lower
            or "unknown"
        )

    machine.savestate = (
        _get_attr(
            driver_element,
            "savestate",
        ).lower()
        == "supported"
    )

    machine.requires_artwork = _get_bool_attr(
        driver_element,
        "requiresartwork",
    )

    machine.unofficial = _get_bool_attr(
        driver_element,
        "unofficial",
    )

    machine.nosoundhardware = _get_bool_attr(
        driver_element,
        "nosoundhardware",
    )

    machine.incomplete = _get_bool_attr(
        driver_element,
        "incomplete",
    )


# ---------------------------------------------------------------------------
# ROM
# ---------------------------------------------------------------------------

def _build_rom(
    element: ET.Element,
) -> Rom:
    """
    Constrói um objeto ``Rom``.

    Campos extraídos:

    * name
    * size
    * crc
    * sha1
    * merge
    * region
    * offset
    * status
    * optional
    * bios

    Args:
        element:
            Elemento XML ``rom``.

    Returns:
        Objeto ``Rom``.
    """

    rom = Rom()

    rom.name = _get_attr(
        element,
        "name",
    )

    rom.size = _safe_int(
        _get_attr(
            element,
            "size",
            default="0",
        )
    )

    rom.crc = _normalize_hash(
        _get_attr(
            element,
            "crc",
        )
    )

    rom.sha1 = _normalize_hash(
        _get_attr(
            element,
            "sha1",
        )
    )

    rom.merge = _get_attr(
        element,
        "merge",
    )

    rom.region = _get_attr(
        element,
        "region",
    )

    rom.offset = _safe_int(
        _get_attr(
            element,
            "offset",
            default="0",
        ),
        allow_hex=True,
    )

    rom.status = _get_attr(
        element,
        "status",
        default="good",
    )

    rom.optional = _get_bool_attr(
        element,
        "optional",
    )

    rom.bios = _get_attr(
        element,
        "bios",
    )

    return rom


# ---------------------------------------------------------------------------
# DISK
# ---------------------------------------------------------------------------

def _build_disk(
    element: ET.Element,
) -> Disk:
    """
    Constrói um objeto ``Disk``.

    IMPORTANTE
    ----------
    O schema atual utiliza ``disk_index``.

    Portanto este parser não utiliza mais ``disk.index``.

    Campos:

    * name
    * sha1
    * merge
    * region
    * disk_index
    * writable
    * status
    * optional

    O campo ``size`` não vem do LISTXML e será preenchido posteriormente
    pelo ``rom_scanner`` quando o CHD físico for encontrado.

    Args:
        element:
            Elemento XML ``disk``.

    Returns:
        Objeto ``Disk``.
    """

    disk = Disk()

    disk.name = _get_attr(
        element,
        "name",
    )

    disk.sha1 = _normalize_hash(
        _get_attr(
            element,
            "sha1",
        )
    )

    disk.merge = _get_attr(
        element,
        "merge",
    )

    disk.region = _get_attr(
        element,
        "region",
    )

    disk_index = _safe_int(
        _get_attr(
            element,
            "index",
            default="0",
        )
    )

    # Novo modelo:
    #     disk.disk_index
    #
    # Compatibilidade temporária:
    # se o modelo antigo ainda estiver instalado, o atributo index
    # também será atualizado.

    _set_optional_attribute(
        disk,
        "disk_index",
        disk_index,
    )

    _set_optional_attribute(
        disk,
        "index",
        disk_index,
    )

    disk.writable = _get_bool_attr(
        element,
        "writable",
    )

    disk.status = _get_attr(
        element,
        "status",
        default="good",
    )

    disk.optional = _get_bool_attr(
        element,
        "optional",
    )

    # O LISTXML não fornece o tamanho físico do CHD.
    # O scanner preencherá esse campo.
    _set_optional_attribute(
        disk,
        "size",
        0,
    )

    return disk


# ---------------------------------------------------------------------------
# BIOS
# ---------------------------------------------------------------------------

def _build_bios(
    rom: Rom,
) -> BiosInfo:
    """
    Constrói informação de BIOS a partir de uma ROM que possui
    o atributo ``bios``.

    Args:
        rom:
            ROM contendo a referência BIOS.

    Returns:
        ``BiosInfo``.
    """

    return BiosInfo(
        name=rom.name,
        description=rom.name,
        is_default=False,
    )


# ---------------------------------------------------------------------------
# DEVICE
# ---------------------------------------------------------------------------

def _build_device(
    element: ET.Element,
) -> DeviceInfo:
    """
    Constrói um device.

    O LISTXML pode utilizar diferentes atributos dependendo da versão
    do MAME. O parser preserva ``tag`` e ``name`` quando disponíveis.
    """

    return DeviceInfo(
        tag=_get_attr(
            element,
            "tag",
        ),
        name=_get_attr(
            element,
            "name",
        ),
    )


# ---------------------------------------------------------------------------
# CHIP
# ---------------------------------------------------------------------------

def _build_chip(
    element: ET.Element,
) -> ChipInfo:
    """
    Constrói informação de chip.

    ``clock`` é convertido para inteiro.

    Args:
        element:
            Elemento ``chip``.

    Returns:
        ``ChipInfo``.
    """

    return ChipInfo(
        chip_type=_get_attr(
            element,
            "type",
        ),
        tag=_get_attr(
            element,
            "tag",
        ),
        name=_get_attr(
            element,
            "name",
        ),
        clock=_safe_int(
            _get_attr(
                element,
                "clock",
                default="0",
            )
        ),
    )


# ---------------------------------------------------------------------------
# DISPLAY
# ---------------------------------------------------------------------------

def _build_display(
    element: ET.Element,
) -> DisplayInfo:
    """
    Constrói informação de display.

    Args:
        element:
            Elemento ``display``.

    Returns:
        ``DisplayInfo``.
    """

    return DisplayInfo(
        tag=_get_attr(
            element,
            "tag",
        ),
        display_type=_get_attr(
            element,
            "type",
        ),
        rotate=_safe_int(
            _get_attr(
                element,
                "rotate",
                default="0",
            )
        ),
        flipx=_get_bool_attr(
            element,
            "flipx",
        ),
        width=_safe_int(
            _get_attr(
                element,
                "width",
                default="0",
            )
        ),
        height=_safe_int(
            _get_attr(
                element,
                "height",
                default="0",
            )
        ),
        refresh=_safe_float(
            _get_attr(
                element,
                "refresh",
                default="0",
            )
        ),
    )


# ---------------------------------------------------------------------------
# INPUT
# ---------------------------------------------------------------------------

def _build_input(
    element: ET.Element | None,
) -> InputInfo | None:
    """
    Constrói as informações de input.

    O elemento ``input`` possui atributos gerais e elementos filhos
    ``control``.

    Args:
        element:
            Elemento ``input``.

    Returns:
        ``InputInfo`` ou ``None``.
    """

    if element is None:
        return None

    input_info = InputInfo(
        players=_safe_int(
            _get_attr(
                element,
                "players",
                default="1",
            )
        ),
        coins=_safe_int(
            _get_attr(
                element,
                "coins",
                default="0",
            )
        ),
        service=_safe_int(
            _get_attr(
                element,
                "service",
                default="0",
            )
        ),
        tilt=_get_bool_attr(
            element,
            "tilt",
        ),
    )

    input_info.controls = [
        _build_control(control)
        for control
        in _find_children(
            element,
            "control",
        )
    ]

    return input_info


# ---------------------------------------------------------------------------
# CONTROL
# ---------------------------------------------------------------------------

def _build_control(
    element: ET.Element,
) -> ControlInfo:
    """
    Constrói um controle de input.

    Args:
        element:
            Elemento XML ``control``.

    Returns:
        ``ControlInfo``.
    """

    return ControlInfo(
        control_type=_get_attr(
            element,
            "type",
        ),
        player=_safe_int(
            _get_attr(
                element,
                "player",
                default="0",
            )
        ),
        buttons=_safe_int(
            _get_attr(
                element,
                "buttons",
                default="0",
            )
        ),
        minimum=_safe_int(
            _get_attr(
                element,
                "minimum",
                default="0",
            )
        ),
        maximum=_safe_int(
            _get_attr(
                element,
                "maximum",
                default="0",
            )
        ),
        sensitivity=_safe_int(
            _get_attr(
                element,
                "sensitivity",
                default="0",
            )
        ),
        keydelta=_safe_int(
            _get_attr(
                element,
                "keydelta",
                default="0",
            )
        ),
        reverse=_get_bool_attr(
            element,
            "reverse",
        ),
        ways=_safe_int(
            _get_attr(
                element,
                "ways",
                default="0",
            )
        ),
    )


# ---------------------------------------------------------------------------
# FEATURE
# ---------------------------------------------------------------------------

def _build_feature(
    element: ET.Element,
) -> FeatureInfo:
    """
    Constrói uma feature.

    Args:
        element:
            Elemento ``feature``.

    Returns:
        ``FeatureInfo``.
    """

    return FeatureInfo(
        feature_type=_get_attr(
            element,
            "type",
        ),
        status=_get_attr(
            element,
            "status",
        ),
        overall=_get_attr(
            element,
            "overall",
        ),
    )


# ---------------------------------------------------------------------------
# SOFTWARE LIST
# ---------------------------------------------------------------------------

def _build_software_list(
    element: ET.Element,
) -> SoftwareListInfo:
    """
    Constrói uma software list.

    Args:
        element:
            Elemento ``softwarelist``.

    Returns:
        ``SoftwareListInfo``.
    """

    return SoftwareListInfo(
        tag=_get_attr(
            element,
            "tag",
        ),
        name=_get_attr(
            element,
            "name",
        ),
        status=_get_attr(
            element,
            "status",
        ),
        filter=_get_attr(
            element,
            "filter",
        ),
    )


# ---------------------------------------------------------------------------
# SLOT
# ---------------------------------------------------------------------------

def _build_slot(
    element: ET.Element,
) -> SlotInfo:
    """
    Constrói um slot e suas opções.

    Args:
        element:
            Elemento ``slot``.

    Returns:
        ``SlotInfo``.
    """

    slot = SlotInfo(
        name=_get_attr(
            element,
            "name",
        )
    )

    slot.options = [
        _build_slot_option(option)
        for option
        in _find_children(
            element,
            "slotoption",
        )
    ]

    return slot


# ---------------------------------------------------------------------------
# SLOT OPTION
# ---------------------------------------------------------------------------

def _build_slot_option(
    element: ET.Element,
) -> SlotOptionInfo:
    """
    Constrói uma opção de slot.

    Args:
        element:
            Elemento ``slotoption``.

    Returns:
        ``SlotOptionInfo``.
    """

    return SlotOptionInfo(
        name=_get_attr(
            element,
            "name",
        ),
        devname=_get_attr(
            element,
            "devname",
        ),
        is_default=_get_bool_attr(
            element,
            "default",
        ),
    )


# ---------------------------------------------------------------------------
# CHD DEPENDENCY
# ---------------------------------------------------------------------------

def _build_chd_dependency(
    element: ET.Element,
) -> ChdDependencyInfo:
    """
    Constrói uma dependência de CHD.

    Args:
        element:
            Elemento ``chd_dependency``.

    Returns:
        ``ChdDependencyInfo``.
    """

    return ChdDependencyInfo(
        name=_get_attr(
            element,
            "name",
        ),
        sha1=_normalize_hash(
            _get_attr(
                element,
                "sha1",
            )
        ),
        region=_get_attr(
            element,
            "region",
        ),
        required=not _get_bool_attr(
            element,
            "optional",
        ),
    )


# ---------------------------------------------------------------------------
# XML HELPERS
# ---------------------------------------------------------------------------

def _strip_namespace(
    tag: str,
) -> str:
    """
    Remove namespace XML de uma tag.

    Exemplo:

        ``{namespace}machine``

    torna-se:

        ``machine``

    Args:
        tag:
            Nome da tag.

    Returns:
        Tag sem namespace.
    """

    if "}" in tag:
        return tag.rsplit(
            "}",
            1,
        )[1]

    return tag


def _find_children(
    element: ET.Element,
    tag: str,
) -> list[ET.Element]:
    """
    Retorna filhos diretos com determinado nome.

    A função é tolerante a namespaces XML.

    Args:
        element:
            Elemento pai.

        tag:
            Nome procurado.

    Returns:
        Lista de elementos.
    """

    return [
        child
        for child in list(element)
        if _strip_namespace(
            child.tag
        ) == tag
    ]


def _find_first(
    element: ET.Element,
    tag: str,
) -> ET.Element | None:
    """
    Retorna o primeiro filho direto com determinada tag.

    Args:
        element:
            Elemento pai.

        tag:
            Nome procurado.

    Returns:
        Elemento ou ``None``.
    """

    for child in list(element):

        if _strip_namespace(
            child.tag
        ) == tag:
            return child

    return None


def _find_text(
    element: ET.Element,
    tag: str,
    default: str = "",
) -> str:
    """
    Obtém o texto de um filho XML.

    Args:
        element:
            Elemento pai.

        tag:
            Tag procurada.

        default:
            Valor padrão.

    Returns:
        Texto limpo.
    """

    child = _find_first(
        element,
        tag,
    )

    if child is None:
        return default

    return (
        child.text or default
    ).strip()


def _get_attr(
    element: ET.Element,
    name: str,
    default: str = "",
) -> str:
    """
    Obtém um atributo XML com valor padrão.

    Args:
        element:
            Elemento XML.

        name:
            Nome do atributo.

        default:
            Valor padrão.

    Returns:
        Valor do atributo.
    """

    value = element.get(
        name
    )

    if value is None:
        return default

    return value.strip()


# ---------------------------------------------------------------------------
# CONVERSÕES
# ---------------------------------------------------------------------------

def _get_bool_attr(
    element: ET.Element,
    name: str,
    default: bool = False,
) -> bool:
    """
    Converte atributo XML para bool.

    Valores reconhecidos como verdadeiro:

        yes
        true
        1
        on
        supported

    Valores reconhecidos como falso:

        no
        false
        0
        off
        unsupported

    Args:
        element:
            Elemento XML.

        name:
            Nome do atributo.

        default:
            Valor padrão.

    Returns:
        Booleano.
    """

    value = element.get(
        name
    )

    if value is None:
        return default

    normalized = (
        value.strip()
        .lower()
    )

    if normalized in {
        "yes",
        "true",
        "1",
        "on",
        "supported",
    }:
        return True

    if normalized in {
        "no",
        "false",
        "0",
        "off",
        "unsupported",
    }:
        return False

    return default


def _safe_int(
    value: str | int | None,
    *,
    allow_hex: bool = False,
    default: int = 0,
) -> int:
    """
    Converte um valor para inteiro de forma segura.

    O LISTXML utiliza principalmente números decimais, porém ``offset``
    pode aparecer em hexadecimal sem prefixo ``0x``.

    Estratégia:

    1. decimal;
    2. hexadecimal, quando ``allow_hex=True``;
    3. default.

    Args:
        value:
            Valor a converter.

        allow_hex:
            Permite fallback hexadecimal.

        default:
            Valor usado quando a conversão falhar.

    Returns:
        Inteiro.
    """

    if value is None:
        return default

    if isinstance(
        value,
        int,
    ):
        return value

    text = str(value).strip()

    if not text:
        return default

    # Decimal
    try:
        return int(
            text,
            10,
        )

    except ValueError:
        pass

    # Hexadecimal explícito
    if text.lower().startswith(
        "0x"
    ):
        try:
            return int(
                text,
                16,
            )

        except ValueError:
            pass

    # Hexadecimal sem prefixo
    if allow_hex:

        try:
            return int(
                text,
                16,
            )

        except ValueError:
            pass

    logger.debug(
        "Valor inteiro inválido '%s'. Usando %s.",
        value,
        default,
    )

    return default


def _safe_float(
    value: str | float | int | None,
    default: float = 0.0,
) -> float:
    """
    Converte um valor para float de forma segura.

    Args:
        value:
            Valor original.

        default:
            Valor utilizado em caso de erro.

    Returns:
        Float.
    """

    if value is None:
        return default

    if isinstance(
        value,
        (float, int),
    ):
        return float(value)

    text = str(value).strip()

    if not text:
        return default

    try:
        return float(text)

    except ValueError:

        logger.debug(
            "Valor float inválido '%s'. Usando %s.",
            value,
            default,
        )

        return default


def _normalize_hash(
    value: str,
) -> str:
    """
    Normaliza hashes provenientes do LISTXML.

    CRC e SHA1 são armazenados em lowercase para facilitar:

    * comparação;
    * indexação;
    * scanner;
    * reconstrução.

    Args:
        value:
            Hash original.

    Returns:
        Hash normalizado.
    """

    return (
        value.strip()
        .lower()
    )


# ---------------------------------------------------------------------------
# ATRIBUTOS OPCIONAIS
# ---------------------------------------------------------------------------

def _set_optional_attribute(
    obj: object,
    name: str,
    value: object,
) -> None:
    """
    Define um atributo no objeto.

    A função existe para permitir a transição entre os modelos antigos
    e os modelos completos que serão utilizados pelo projeto.

    Quando o modelo futuro já possuir o atributo, simplesmente será
    atribuído normalmente.

    Quando o modelo atual ainda não possuir o atributo, Python permite
    sua inclusão dinâmica enquanto a classe não utilizar ``slots``.

    Args:
        obj:
            Objeto destino.

        name:
            Nome do atributo.

        value:
            Valor.
    """

    try:
        setattr(
            obj,
            name,
            value,
        )

    except AttributeError:
        logger.debug(
            "Modelo %s não aceita atributo opcional '%s'.",
            type(obj).__name__,
            name,
        )


# ---------------------------------------------------------------------------
# VALIDAÇÃO
# ---------------------------------------------------------------------------

def validate_machine(
    machine: Machine,
) -> bool:
    """
    Valida os campos mínimos de uma máquina.

    Esta função não substitui validações de banco de dados.

    Regras:

    * ``name`` deve existir;
    * ``description`` pode estar vazia;
    * ``roms`` deve ser uma lista;
    * ``disks`` deve ser uma lista.

    Args:
        machine:
            Máquina a validar.

    Returns:
        ``True`` quando a estrutura mínima é válida.
    """

    if not machine.name:
        return False

    if not isinstance(
        machine.roms,
        list,
    ):
        return False

    if not isinstance(
        machine.disks,
        list,
    ):
        return False

    return True


# ---------------------------------------------------------------------------
# ESTATÍSTICAS
# ---------------------------------------------------------------------------

def count_machines(
    source: SourceType,
) -> int:
    """
    Conta máquinas sem acumular o LISTXML inteiro.

    Args:
        source:
            Origem do XML.

    Returns:
        Quantidade de máquinas.
    """

    count = 0

    for _ in iter_machines(source):
        count += 1

    return count


def iter_machine_names(
    source: SourceType,
) -> Iterator[str]:
    """
    Itera somente pelos nomes das máquinas.

    Útil para consultas rápidas sem necessidade de manter todos
    os objetos.

    Args:
        source:
            Origem do XML.

    Yields:
        Nome de cada máquina.
    """

    for machine in iter_machines(
        source
    ):
        yield machine.name