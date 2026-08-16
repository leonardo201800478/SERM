"""
MAME Set Builder
================

Scanner físico de ROMs e CHDs.

Responsabilidade
----------------
Este módulo cruza as informações do LISTXML filtrado com os arquivos
físicos existentes nos diretórios configurados para o MAME.

Fluxo:

    LISTXML filtrado
          |
          v
    Machine / Rom / Disk
          |
          v
    RomScanner
          |
          +---- ZIP da máquina
          |
          +---- diretório da máquina
          |
          +---- CHD
          |
          v
    ScanResult
          |
          v
    GUI / Banco / ReconstructionService

Princípios
----------
1. O XML filtrado é a fonte de verdade.
2. Somente máquinas presentes no XML são analisadas.
3. Somente ROMs presentes nas máquinas selecionadas são analisadas.
4. Não existe varredura global obrigatória de todos os ZIPs.
5. ZIPs são abertos somente quando necessários.
6. O CRC armazenado no ZIP é aproveitado quando disponível.
7. Arquivos descompactados têm seu CRC calculado em streaming.
8. CHDs são tratados separadamente das ROMs.
9. O processo pode ser cancelado cooperativamente.
10. Um erro em uma ROM não interrompe o restante do scan.
11. O scanner não grava diretamente no banco.
12. O scanner não modifica os modelos Machine/Rom/Disk.

Compatibilidade
---------------
O scanner aceita:

    * Machine / Rom / Disk;
    * objetos semelhantes aos modelos do projeto;
    * dicionários, utilizados principalmente por código legado/testes.

Isso permite reconstruir os modelos gradualmente sem quebrar o scanner.

IMPORTANTE
----------
O tamanho de uma ROM é o tamanho descompactado informado pelo LISTXML.

O tamanho de um CHD é obtido do arquivo físico durante o scan.

O CRC de uma ROM dentro de ZIP pode ser obtido diretamente do diretório
central do ZIP sem descompactar o conteúdo.

Para arquivos ROM descompactados, o CRC é calculado em blocos.

CHDs não possuem CRC de ROM tradicional; a validação principal é feita
por SHA-1 quando essa informação estiver disponível.
"""

from __future__ import annotations

import binascii
import hashlib
import logging
import os
import threading
import zipfile

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import (
    Any,
    Callable,
    Iterable,
    Iterator,
)

from app.core.models.scan_result import (
    MachineScanResult,
    RomScanResult,
    ScanStatus,
)


logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTES
# ============================================================================

DEFAULT_MAX_WORKERS = 4

DEFAULT_CHUNK_SIZE = 1024 * 1024

ROM_EXTENSION = ".zip"

CHD_EXTENSION = ".chd"


# ============================================================================
# CALLBACKS
# ============================================================================

ProgressCallback = Callable[
    [int, int, RomScanResult],
    None,
]

MachineCallback = Callable[
    [MachineScanResult],
    None,
]

LogCallback = Callable[
    [str],
    None,
]


# ============================================================================
# HELPERS DE ACESSO A OBJETOS
# ============================================================================

def _get_value(
    obj: Any,
    name: str,
    default: Any = None,
) -> Any:
    """
    Obtém um atributo de objeto ou uma chave de dicionário.

    Essa função é usada para manter compatibilidade entre:

        Machine / Rom / Disk

    e implementações antigas baseadas em:

        dict

    Args:
        obj:
            Objeto ou dicionário.

        name:
            Nome do campo.

        default:
            Valor padrão.

    Returns:
        Valor encontrado ou ``default``.
    """

    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(
            name,
            default,
        )

    return getattr(
        obj,
        name,
        default,
    )


def _as_int(
    value: Any,
    default: int = 0,
) -> int:
    """
    Converte um valor para inteiro com segurança.

    Args:
        value:
            Valor original.

        default:
            Valor em caso de falha.

    Returns:
        Inteiro.
    """

    if value is None:
        return default

    if isinstance(
        value,
        bool,
    ):
        return int(value)

    try:
        return int(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def _normalize_name(
    name: Any,
) -> str:
    """
    Normaliza nomes de ROM/CHD para comparação.

    Barras invertidas são convertidas para barras normais.

    Args:
        name:
            Nome original.

    Returns:
        Nome normalizado.
    """

    if name is None:
        return ""

    return (
        str(name)
        .replace(
            "\\",
            "/",
        )
        .strip()
    )


def _basename(
    name: str,
) -> str:
    """
    Retorna somente o nome final de um caminho.

    Exemplo:

        ``foo/bar/rom.bin``

    retorna:

        ``rom.bin``

    Args:
        name:
            Caminho/nome.

    Returns:
        Nome final.
    """

    return Path(
        name
    ).name


def _normalize_hash(
    value: Any,
) -> str:
    """
    Normaliza hashes para comparação.

    Args:
        value:
            Hash original.

    Returns:
        Hash lowercase e sem espaços.
    """

    if not value:
        return ""

    return (
        str(value)
        .strip()
        .lower()
    )


def _result_kwargs(
    result: Any,
) -> dict[str, Any]:
    """
    Converte um resultado dataclass em dicionário quando necessário.

    Essa função é utilizada somente para compatibilidade entre versões
    do modelo de resultado.
    """

    if is_dataclass(result):
        return asdict(result)

    if isinstance(
        result,
        dict,
    ):
        return dict(result)

    return {
        key: value
        for key, value
        in vars(result).items()
        if not key.startswith("_")
    }


# ============================================================================
# SCANNER
# ============================================================================

class RomScanner:
    """
    Scanner físico de ROMs e CHDs do MAME.

    O scanner recebe os diretórios onde os sets estão armazenados e
    analisa somente as máquinas/ROMs fornecidas pelo XML filtrado.

    Args:
        rom_paths:
            Diretórios onde os sets MAME estão armazenados.

        max_workers:
            Quantidade máxima de workers quando o scan paralelo estiver
            habilitado.

        progress_callback:
            Callback executado após cada ROM/CHD analisado.

        machine_callback:
            Callback executado ao concluir uma máquina.

        log_callback:
            Callback opcional para enviar mensagens para a GUI.

        enable_alternate_search:
            Habilita procura alternativa por nome de arquivo/ZIP.

            O padrão é False para preservar a regra de que o XML filtrado
            determina exatamente o conjunto analisado.

        chunk_size:
            Tamanho do bloco utilizado para calcular CRC/SHA1 de arquivos
            descompactados.

        include_chds:
            Quando True, disks/CHDs também são analisados.
    """

    def __init__(
        self,
        rom_paths: Iterable[str | Path],
        max_workers: int = DEFAULT_MAX_WORKERS,
        progress_callback: ProgressCallback | None = None,
        machine_callback: MachineCallback | None = None,
        log_callback: LogCallback | None = None,
        enable_alternate_search: bool = False,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        include_chds: bool = True,
    ) -> None:

        self.rom_paths = self._normalize_paths(
            rom_paths
        )

        self.max_workers = max(
            1,
            _as_int(
                max_workers,
                DEFAULT_MAX_WORKERS,
            ),
        )

        self.progress_callback = (
            progress_callback
        )

        self.machine_callback = (
            machine_callback
        )

        self.log_callback = (
            log_callback
        )

        self.enable_alternate_search = (
            bool(
                enable_alternate_search
            )
        )

        self.chunk_size = max(
            4096,
            _as_int(
                chunk_size,
                DEFAULT_CHUNK_SIZE,
            ),
        )

        self.include_chds = bool(
            include_chds
        )

        self._cancel_event = (
            threading.Event()
        )

        self._callback_lock = (
            threading.Lock()
        )

        logger.info(
            "RomScanner inicializado: "
            "%d diretório(s), %d worker(s), "
            "alternate_search=%s, include_chds=%s",
            len(self.rom_paths),
            self.max_workers,
            self.enable_alternate_search,
            self.include_chds,
        )

    # ========================================================================
    # CONTROLE
    # ========================================================================

    def cancel(self) -> None:
        """
        Solicita o cancelamento do scan.

        O cancelamento é cooperativo.

        Uma ROM que já esteja sendo processada pode terminar, mas novas
        tarefas devem interromper sua execução assim que possível.
        """

        logger.info(
            "Solicitação de cancelamento do ROM scan."
        )

        self._cancel_event.set()

    def reset_cancel(self) -> None:
        """
        Limpa o estado de cancelamento.

        Deve ser chamado antes de iniciar um novo scan com a mesma instância.
        """

        self._cancel_event.clear()

    @property
    def cancelled(self) -> bool:
        """
        Retorna ``True`` quando o scan foi cancelado.

        Returns:
            Estado atual do cancelamento.
        """

        return self._cancel_event.is_set()

    # ========================================================================
    # LOG
    # ========================================================================

    def _log(
        self,
        message: str,
        *args: Any,
        level: int = logging.INFO,
    ) -> None:
        """
        Registra uma mensagem no logger e envia opcionalmente para a GUI.

        Args:
            message:
                Mensagem de log.

            *args:
                Argumentos usados pelo logging.

            level:
                Nível do log.
        """

        logger.log(
            level,
            message,
            *args,
        )

        if self.log_callback is None:
            return

        try:
            formatted = (
                message % args
                if args
                else message
            )

            self.log_callback(
                formatted
            )

        except Exception:
            logger.exception(
                "Erro executando log_callback."
            )

    # ========================================================================
    # PATHS
    # ========================================================================

    @staticmethod
    def _normalize_paths(
        paths: Iterable[str | Path],
    ) -> list[Path]:
        """
        Normaliza e remove caminhos duplicados.

        Args:
            paths:
                Diretórios de ROM.

        Returns:
            Lista de Paths únicos.
        """

        result: list[Path] = []

        seen: set[str] = set()

        for value in paths:

            path = Path(
                value
            ).expanduser()

            key = os.path.normcase(
                os.path.abspath(
                    str(path)
                )
            )

            if key in seen:
                continue

            seen.add(key)

            result.append(
                path
            )

        return result

    # ========================================================================
    # CANDIDATOS DE MÁQUINA
    # ========================================================================

    def _machine_zip_candidates(
        self,
        machine_name: str,
    ) -> Iterator[Path]:
        """
        Retorna os ZIPs diretamente relacionados à máquina.

        Exemplo:

            ``sf2``

        resulta em:

            ``<rom_path>/sf2.zip``

        Nenhum ZIP global é enumerado aqui.

        Args:
            machine_name:
                Nome da máquina.

        Yields:
            Caminhos candidatos.
        """

        for base in self.rom_paths:

            yield (
                base
                / f"{machine_name}.zip"
            )

    def _machine_dir_candidates(
        self,
        machine_name: str,
    ) -> Iterator[Path]:
        """
        Retorna os diretórios diretamente relacionados à máquina.

        Exemplo:

            ``<rom_path>/sf2/``

        Args:
            machine_name:
                Nome da máquina.

        Yields:
            Diretórios candidatos.
        """

        for base in self.rom_paths:

            yield (
                base
                / machine_name
            )

    # ========================================================================
    # ZIP
    # ========================================================================

    def _open_zip(
        self,
        path: Path,
    ) -> zipfile.ZipFile | None:
        """
        Abre um ZIP de forma segura.

        Args:
            path:
                Arquivo ZIP.

        Returns:
            ``ZipFile`` ou ``None``.
        """

        try:
            return zipfile.ZipFile(
                path,
                "r",
            )

        except zipfile.BadZipFile:
            self._log(
                "ZIP inválido: %s",
                path,
                level=logging.WARNING,
            )

        except OSError as exc:
            self._log(
                "Erro abrindo ZIP %s: %s",
                path,
                exc,
                level=logging.WARNING,
            )

        return None

    def _find_zip_entry(
        self,
        archive: zipfile.ZipFile,
        rom_name: str,
    ) -> zipfile.ZipInfo | None:
        """
        Procura uma ROM dentro de um ZIP.

        A comparação principal é feita pelo caminho normalizado.

        Quando ``enable_alternate_search`` está ativo, uma segunda
        tentativa é realizada utilizando somente o basename.

        Args:
            archive:
                ZIP aberto.

            rom_name:
                Nome esperado.

        Returns:
            ``ZipInfo`` encontrado ou ``None``.
        """

        target = _normalize_name(
            rom_name
        )

        if not target:
            return None

        basename = _basename(
            target
        )

        fallback: zipfile.ZipInfo | None = None

        for info in archive.infolist():

            if info.is_dir():
                continue

            entry = _normalize_name(
                info.filename
            )

            if entry == target:
                return info

            if (
                self.enable_alternate_search
                and _basename(entry) == basename
                and fallback is None
            ):
                fallback = info

        return fallback

    def _scan_zip_rom(
        self,
        zip_path: Path,
        machine_name: str,
        rom: Any,
    ) -> RomScanResult | None:
        """
        Procura uma ROM dentro de um ZIP específico.

        O CRC armazenado no diretório ZIP é utilizado diretamente.

        Não é necessário descompactar a ROM para validá-la.

        Args:
            zip_path:
                ZIP da máquina.

            machine_name:
                Nome da máquina.

            rom:
                Modelo/dicionário da ROM.

        Returns:
            Resultado ou ``None`` quando a ROM não existe nesse ZIP.
        """

        rom_name = _normalize_name(
            _get_value(
                rom,
                "name",
                "",
            )
        )

        expected_size = _as_int(
            _get_value(
                rom,
                "size",
                0,
            )
        )

        expected_crc = _normalize_hash(
            _get_value(
                rom,
                "crc",
                "",
            )
        )

        archive = self._open_zip(
            zip_path
        )

        if archive is None:
            return None

        try:
            info = self._find_zip_entry(
                archive,
                rom_name,
            )

            if info is None:
                return None

            actual_size = int(
                info.file_size
            )

            actual_crc = (
                f"{info.CRC:08x}"
            )

            size_ok = (
                expected_size <= 0
                or actual_size
                == expected_size
            )

            crc_ok = (
                not expected_crc
                or actual_crc
                == expected_crc
            )

            valid = (
                size_ok
                and crc_ok
            )

            status = (
                ScanStatus.VALID
                if valid
                else ScanStatus.INVALID
            )

            if valid:
                message = (
                    "ROM encontrada e válida "
                    "no ZIP."
                )
            else:
                problems: list[str] = []
                if not size_ok:
                    problems.append(
                        "tamanho inválido"
                    )
                if not crc_ok:
                    problems.append(
                        "CRC inválido"
                    )
                message = (
                    "ROM encontrada, mas "
                    + " e ".join(
                        problems
                    )
                    + "."
                )

            return RomScanResult(
                machine_name=machine_name,
                rom_name=rom_name,
                expected_size=expected_size,
                actual_size=actual_size,
                expected_crc=expected_crc,
                actual_crc=actual_crc,
                status=status,
                path=zip_path,
                archive_path=zip_path,
                archive_member=info.filename,
                message=message,
            )

        except Exception as exc:

            logger.exception(
                "Erro analisando ROM %s em %s.",
                rom_name,
                zip_path,
            )

            return RomScanResult(
                machine_name=machine_name,
                rom_name=rom_name,
                expected_size=expected_size,
                expected_crc=expected_crc,
                status=ScanStatus.ERROR,
                path=zip_path,
                archive_path=zip_path,
                message=str(exc),
            )

        finally:
            archive.close()

    # ========================================================================
    # ARQUIVO DESCOMPACTADO
    # ========================================================================

    def _calculate_crc(
        self,
        path: Path,
    ) -> str:
        """
        Calcula CRC32 de um arquivo em streaming.

        O arquivo nunca é carregado inteiro na memória.

        Args:
            path:
                Arquivo.

        Returns:
            CRC32 em hexadecimal lowercase.
        """

        crc = 0

        with path.open(
            "rb"
        ) as file:

            while True:

                if self.cancelled:
                    raise ScanCancelledError()

                chunk = file.read(
                    self.chunk_size
                )

                if not chunk:
                    break

                crc = binascii.crc32(
                    chunk,
                    crc,
                )

        return (
            f"{crc & 0xffffffff:08x}"
        )

    def _calculate_sha1(
        self,
        path: Path,
    ) -> str:
        """
        Calcula SHA-1 de um arquivo em streaming.

        Args:
            path:
                Arquivo.

        Returns:
            SHA-1 lowercase.
        """

        digest = hashlib.sha1()

        with path.open(
            "rb"
        ) as file:

            while True:

                if self.cancelled:
                    raise ScanCancelledError()

                chunk = file.read(
                    self.chunk_size
                )

                if not chunk:
                    break

                digest.update(
                    chunk
                )

        return digest.hexdigest()

    def _scan_raw_rom(
        self,
        path: Path,
        machine_name: str,
        rom: Any,
    ) -> RomScanResult:
        """
        Analisa uma ROM armazenada como arquivo físico.

        O CRC é calculado em blocos para evitar consumo excessivo
        de memória.

        Args:
            path:
                Caminho da ROM.

            machine_name:
                Máquina.

            rom:
                Modelo/dicionário da ROM.

        Returns:
            Resultado da análise.
        """

        rom_name = _normalize_name(
            _get_value(
                rom,
                "name",
                "",
            )
        )

        expected_size = _as_int(
            _get_value(
                rom,
                "size",
                0,
            )
        )

        expected_crc = _normalize_hash(
            _get_value(
                rom,
                "crc",
                "",
            )
        )

        try:

            actual_size = path.stat().st_size

            actual_crc = (
                self._calculate_crc(
                    path
                )
            )

            size_ok = (
                expected_size <= 0
                or actual_size
                == expected_size
            )

            crc_ok = (
                not expected_crc
                or actual_crc
                == expected_crc
            )

            valid = (
                size_ok
                and crc_ok
            )

            status = (
                ScanStatus.VALID
                if valid
                else ScanStatus.INVALID
            )

            return RomScanResult(
                machine_name=machine_name,
                rom_name=rom_name,
                expected_size=expected_size,
                actual_size=actual_size,
                expected_crc=expected_crc,
                actual_crc=actual_crc,
                status=status,
                path=path,
                message=(
                    "ROM encontrada e válida."
                    if valid
                    else (
                        "ROM encontrada, mas "
                        "tamanho ou CRC inválido."
                    )
                ),
            )

        except ScanCancelledError:

            return RomScanResult(
                machine_name=machine_name,
                rom_name=rom_name,
                expected_size=expected_size,
                expected_crc=expected_crc,
                status=ScanStatus.CANCELLED,
                path=path,
                message="Scan cancelado.",
            )

        except OSError as exc:

            return RomScanResult(
                machine_name=machine_name,
                rom_name=rom_name,
                expected_size=expected_size,
                expected_crc=expected_crc,
                status=ScanStatus.ERROR,
                path=path,
                message=str(exc),
            )

        except Exception as exc:

            logger.exception(
                "Erro analisando arquivo ROM %s.",
                path,
            )

            return RomScanResult(
                machine_name=machine_name,
                rom_name=rom_name,
                expected_size=expected_size,
                expected_crc=expected_crc,
                status=ScanStatus.ERROR,
                path=path,
                message=str(exc),
            )

    # ========================================================================
    # SCAN DE ROM
    # ========================================================================

    def scan_rom(
        self,
        machine_name: str,
        rom: Any,
    ) -> RomScanResult:
        """
        Analisa uma ROM individual.

        Ordem de procura:

        1. ``<rom_path>/<machine>.zip``
        2. ``<rom_path>/<machine>/<rom>``

        O scanner não procura a ROM em todos os ZIPs do diretório.

        Args:
            machine_name:
                Nome da máquina.

            rom:
                ROM do modelo ou dicionário.

        Returns:
            ``RomScanResult``.
        """

        rom_name = _normalize_name(
            _get_value(
                rom,
                "name",
                "",
            )
        )

        expected_size = _as_int(
            _get_value(
                rom,
                "size",
                0,
            )
        )

        expected_crc = _normalize_hash(
            _get_value(
                rom,
                "crc",
                "",
            )
        )

        if not rom_name:

            return RomScanResult(
                machine_name=machine_name,
                rom_name="",
                expected_size=expected_size,
                expected_crc=expected_crc,
                status=ScanStatus.ERROR,
                message="ROM sem nome.",
            )

        self._log(
            "[ROM] Analisando: "
            "machine=%s | rom=%s | "
            "size=%d | crc=%s",
            machine_name,
            rom_name,
            expected_size,
            expected_crc or "-",
        )

        if self.cancelled:

            return RomScanResult(
                machine_name=machine_name,
                rom_name=rom_name,
                expected_size=expected_size,
                expected_crc=expected_crc,
                status=ScanStatus.CANCELLED,
                message="Scan cancelado.",
            )

        # ------------------------------------------------------------------
        # 1. ZIP DA MÁQUINA
        # ------------------------------------------------------------------

        for zip_path in self._machine_zip_candidates(
            machine_name
        ):

            if not zip_path.is_file():
                continue

            result = self._scan_zip_rom(
                zip_path,
                machine_name,
                rom,
            )

            if result is not None:

                self._log_rom_result(
                    result
                )

                return result

        # ------------------------------------------------------------------
        # 2. ROM DESCOMPACTADA
        # ------------------------------------------------------------------

        for machine_dir in self._machine_dir_candidates(
            machine_name
        ):

            if not machine_dir.is_dir():
                continue

            raw_path = (
                machine_dir
                / rom_name
            )

            if not raw_path.is_file():

                if self.enable_alternate_search:

                    alternate = (
                        self._find_raw_alternate(
                            machine_dir,
                            rom_name,
                        )
                    )

                    if alternate is not None:
                        raw_path = alternate

            if not raw_path.is_file():
                continue

            result = self._scan_raw_rom(
                raw_path,
                machine_name,
                rom,
            )

            self._log_rom_result(
                result
            )

            return result

        # ------------------------------------------------------------------
        # 3. AUSENTE
        # ------------------------------------------------------------------

        result = RomScanResult(
            machine_name=machine_name,
            rom_name=rom_name,
            expected_size=expected_size,
            expected_crc=expected_crc,
            status=ScanStatus.MISSING,
            message="ROM não encontrada.",
        )

        self._log_rom_result(
            result
        )

        return result

    def _find_raw_alternate(
        self,
        machine_dir: Path,
        rom_name: str,
    ) -> Path | None:
        """
        Procura uma ROM alternativa pelo basename.

        Esta busca somente ocorre dentro do diretório da própria máquina.

        Portanto não transforma o scanner em uma busca global.

        Args:
            machine_dir:
                Diretório da máquina.

            rom_name:
                Nome esperado.

        Returns:
            Arquivo encontrado ou ``None``.
        """

        target = _basename(
            _normalize_name(
                rom_name
            )
        )

        try:

            for entry in machine_dir.iterdir():

                if not entry.is_file():
                    continue

                if (
                    entry.name
                    == target
                ):
                    return entry

        except OSError as exc:

            self._log(
                "Erro procurando ROM alternativa em %s: %s",
                machine_dir,
                exc,
                level=logging.WARNING,
            )

        return None

    # ========================================================================
    # CHD
    # ========================================================================

    def _scan_chd(
        self,
        machine_name: str,
        disk: Any,
    ) -> RomScanResult:
        """
        Analisa um CHD.

        O LISTXML fornece normalmente:

            name
            sha1
            merge

        O scanner procura o arquivo:

            <machine>.chd

        ou, quando ``merge`` estiver presente, considera também o nome
        informado pelo atributo merge.

        A validação utiliza:

            * existência;
            * tamanho físico;
            * SHA-1, quando disponível.

        IMPORTANTE:
        CHD não possui CRC32 equivalente à ROM tradicional.

        Args:
            machine_name:
                Nome da máquina.

            disk:
                Modelo/dicionário Disk.

        Returns:
            ``RomScanResult``.

        O modelo de resultado é utilizado para que ROMs e CHDs possam
        ser apresentados de maneira uniforme pela GUI.
        """

        disk_name = _normalize_name(
            _get_value(
                disk,
                "name",
                "",
            )
        )

        expected_sha1 = _normalize_hash(
            _get_value(
                disk,
                "sha1",
                "",
            )
        )

        expected_size = _as_int(
            _get_value(
                disk,
                "size",
                0,
            )
        )

        if not disk_name:

            return RomScanResult(
                machine_name=machine_name,
                rom_name="",
                expected_size=expected_size,
                expected_crc="",
                status=ScanStatus.ERROR,
                message="Disk/CHD sem nome.",
            )

        candidates = (
            self._chd_candidates(
                machine_name,
                disk_name,
            )
        )

        for path in candidates:

            if not path.is_file():
                continue

            return self._validate_chd(
                machine_name,
                disk,
                path,
            )

        return RomScanResult(
            machine_name=machine_name,
            rom_name=disk_name,
            expected_size=expected_size,
            expected_crc=expected_sha1,
            status=ScanStatus.MISSING,
            message="CHD não encontrado.",
        )

    def _chd_candidates(
        self,
        machine_name: str,
        disk_name: str,
    ) -> Iterator[Path]:
        """
        Gera os caminhos possíveis para um CHD.

        Formatos considerados:

            <rom_path>/<machine>/<disk>.chd
            <rom_path>/<machine>.chd

        O formato de diretório é priorizado porque é a organização
        tradicional utilizada pelos sets MAME.

        Args:
            machine_name:
                Máquina.

            disk_name:
                Nome do CHD.

        Yields:
            Caminhos candidatos.
        """

        disk_filename = (
            disk_name
            if disk_name.lower().endswith(
                CHD_EXTENSION
            )
            else (
                f"{disk_name}{CHD_EXTENSION}"
            )
        )

        for base in self.rom_paths:

            yield (
                base
                / machine_name
                / disk_filename
            )

            yield (
                base
                / disk_filename
            )

    def _validate_chd(
        self,
        machine_name: str,
        disk: Any,
        path: Path,
    ) -> RomScanResult:
        """
        Valida um CHD físico.

        A SHA-1 é calculada integralmente no arquivo físico quando
        o LISTXML fornece essa informação.

        Args:
            machine_name:
                Máquina.

            disk:
                Disk esperado.

            path:
                CHD encontrado.

        Returns:
            Resultado.
        """

        disk_name = _normalize_name(
            _get_value(
                disk,
                "name",
                "",
            )
        )

        expected_sha1 = _normalize_hash(
            _get_value(
                disk,
                "sha1",
                "",
            )
        )

        expected_size = _as_int(
            _get_value(
                disk,
                "size",
                0,
            )
        )

        try:

            actual_size = path.stat().st_size

            actual_sha1 = ""

            if expected_sha1:

                actual_sha1 = (
                    self._calculate_sha1(
                        path
                    )
                )

            size_ok = (
                expected_size <= 0
                or actual_size
                == expected_size
            )

            sha1_ok = (
                not expected_sha1
                or actual_sha1
                == expected_sha1
            )

            valid = (
                size_ok
                and sha1_ok
            )

            status = (
                ScanStatus.VALID
                if valid
                else ScanStatus.INVALID
            )

            if valid:
                message = (
                    "CHD encontrado e válido."
                )
            else:
                problems: list[str] = []
                if not size_ok:
                    problems.append(
                        "tamanho inválido"
                    )
                if not sha1_ok:
                    problems.append(
                        "SHA-1 inválido"
                    )
                message = (
                    "CHD encontrado, mas "
                    + " e ".join(
                        problems
                    )
                    + "."
                )

            return RomScanResult(
                machine_name=machine_name,
                rom_name=disk_name,
                expected_size=expected_size,
                actual_size=actual_size,
                expected_crc=expected_sha1,
                actual_crc=actual_sha1,
                status=status,
                path=path,
                message=message,
            )

        except ScanCancelledError:

            return RomScanResult(
                machine_name=machine_name,
                rom_name=disk_name,
                expected_size=expected_size,
                expected_crc=expected_sha1,
                status=ScanStatus.CANCELLED,
                path=path,
                message="Scan cancelado.",
            )

        except OSError as exc:

            return RomScanResult(
                machine_name=machine_name,
                rom_name=disk_name,
                expected_size=expected_size,
                expected_crc=expected_sha1,
                status=ScanStatus.ERROR,
                path=path,
                message=str(exc),
            )

        except Exception as exc:

            logger.exception(
                "Erro validando CHD %s.",
                path,
            )

            return RomScanResult(
                machine_name=machine_name,
                rom_name=disk_name,
                expected_size=expected_size,
                expected_crc=expected_sha1,
                status=ScanStatus.ERROR,
                path=path,
                message=str(exc),
            )

    # ========================================================================
    # LOG DO RESULTADO
    # ========================================================================

    def _log_rom_result(
        self,
        result: RomScanResult,
    ) -> None:
        """
        Registra uma ROM/CHD individual.

        Args:
            result:
                Resultado.
        """

        status_map = {
            ScanStatus.VALID: "OK",
            ScanStatus.INVALID: "RUIM",
            ScanStatus.MISSING: "AUSENTE",
            ScanStatus.ERROR: "ERRO",
            ScanStatus.CANCELLED: "CANCELADA",
        }

        status = status_map.get(
            result.status,
            str(result.status).upper(),
        )

        self._log(
            "[ROM] %-10s | machine=%s | rom=%s | %s",
            status,
            result.machine_name,
            result.rom_name,
            result.message,
        )

    # ========================================================================
    # MÁQUINA
    # ========================================================================

    def scan_machine(
        self,
        machine: Any,
        *,
        progress_start: int = 0,
        progress_total: int = 0,
    ) -> MachineScanResult:
        """
        Analisa todas as ROMs e CHDs de uma máquina.

        Args:
            machine:
                Machine ou dicionário.

            progress_start:
                Quantidade de itens processados antes desta máquina.

            progress_total:
                Total global de itens.

        Returns:
            ``MachineScanResult``.
        """

        machine_name = str(
            _get_value(
                machine,
                "name",
                "",
            )
            or ""
        )

        roms = _get_value(
            machine,
            "roms",
            [],
        )

        disks = _get_value(
            machine,
            "disks",
            [],
        )

        if roms is None:
            roms = []

        if disks is None:
            disks = []

        roms = list(
            roms
        )

        disks = list(
            disks
        )

        result = MachineScanResult(
            machine_name=machine_name
        )

        if not machine_name:

            self._log(
                "Machine sem nome encontrada.",
                level=logging.WARNING,
            )

            return result

        self._log(
            "------------------------------------------------------------"
        )

        self._log(
            "Iniciando máquina: %s | "
            "ROMs=%d | CHDs=%d",
            machine_name,
            len(roms),
            len(disks),
        )

        local_index = 0

        # ------------------------------------------------------------------
        # ROMS
        # ------------------------------------------------------------------

        for rom in roms:

            if self.cancelled:
                break

            rom_result = self.scan_rom(
                machine_name,
                rom,
            )

            self._append_rom_result(
                result,
                rom_result,
            )

            local_index += 1

            self._emit_progress(
                progress_start
                + local_index,
                progress_total,
                rom_result,
            )

        # ------------------------------------------------------------------
        # CHDS
        # ------------------------------------------------------------------

        if (
            self.include_chds
            and not self.cancelled
        ):

            for disk in disks:

                if self.cancelled:
                    break

                disk_result = self._scan_chd(
                    machine_name,
                    disk,
                )

                self._append_rom_result(
                    result,
                    disk_result,
                )

                local_index += 1

                self._emit_progress(
                    progress_start
                    + local_index,
                    progress_total,
                    disk_result,
                )

                error_count = sum(1 for r in result.roms if r.status == ScanStatus.ERROR)
                self._log(
                    "Máquina concluída: %s | total=%d | válidas=%d | ausentes=%d | ruins=%d | erros=%d",
                    machine_name,
                    result.total,
                    result.valid,
                    result.missing,
                    result.bad,
                    error_count,
                )

        if self.machine_callback is not None:

            try:

                self.machine_callback(
                    result
                )

            except Exception:

                logger.exception(
                    "Erro executando machine_callback."
                )

        return result

    def _append_rom_result(
        self,
        machine_result: MachineScanResult,
        rom_result: RomScanResult,
    ) -> None:
        """
        Adiciona um resultado individual ao resultado da máquina.

        Também atualiza os contadores agregados.

        Args:
            machine_result:
                Resultado da máquina.

            rom_result:
                Resultado individual.
        """

        # Garantir que a lista existe
        try:
            if not hasattr(machine_result, "roms"):
                setattr(machine_result, "roms", [])
            elif machine_result.roms is None:
                setattr(machine_result, "roms", [])
            machine_result.roms.append(rom_result)
        except AttributeError:
            return

        # Atualizar contadores via propriedades da máquina
        # Mas como MachineScanResult tem propriedades, basta incrementar os contadores
        # que são usados pelas propriedades. No entanto, MachineScanResult usa
        # sum sobre roms, então não precisamos incrementar manualmente.
        # Porém, a máquina também tem campos como total, found, valid, etc.
        # Eles são calculados via property. Portanto não precisamos incrementar nada aqui.

        # Mas para compatibilidade com código antigo que espera contadores,
        # vamos manter a lógica de incremento, mas usando os campos privados.
        # Como a classe tem campos do tipo property, não podemos incrementar diretamente.
        # Precisamos usar os atributos subjacentes se existirem.
        # Vamos simplesmente confiar nas propriedades e não incrementar nada.

        pass

    # ========================================================================
    # PROGRESSO
    # ========================================================================

    def _emit_progress(
        self,
        completed: int,
        total: int,
        result: RomScanResult,
    ) -> None:
        """
        Emite evento de progresso após uma ROM/CHD.

        Args:
            completed:
                Quantidade concluída.

            total:
                Quantidade total.

            result:
                Resultado recém-processado.
        """

        if self.progress_callback is None:
            return

        try:

            with self._callback_lock:

                self.progress_callback(
                    completed,
                    total,
                    result,
                )

        except Exception:

            logger.exception(
                "Erro executando progress_callback."
            )

    # ========================================================================
    # SCAN COMPLETO
    # ========================================================================

    def scan(
        self,
        machines: Iterable[Any],
    ) -> list[MachineScanResult]:
        """
        Executa o scan completo.

        O iterable de máquinas é materializado para permitir:

            * cálculo determinístico do progresso;
            * processamento paralelo;
            * preservação da ordem original.

        Args:
            machines:
                Máquinas provenientes do XML filtrado.

        Returns:
            Lista de resultados na mesma ordem das máquinas recebidas.
        """

        self.reset_cancel()

        machines_list = list(
            machines
        )

        total_items = sum(
            self._machine_item_count(
                machine
            )
            for machine in machines_list
        )

        self._log(
            "============================================================"
        )

        self._log(
            "Iniciando scan de ROMs/CHDs."
        )

        self._log(
            "Máquinas selecionadas: %d",
            len(machines_list),
        )

        self._log(
            "Itens a verificar: %d",
            total_items,
        )

        self._log(
            "Diretórios de ROM: %s",
            ", ".join(
                str(path)
                for path in self.rom_paths
            )
            or "(nenhum)",
        )

        self._log(
            "============================================================"
        )

        if not machines_list:

            self._log(
                "Nenhuma máquina encontrada no XML filtrado.",
                level=logging.WARNING,
            )

            return []

        if total_items == 0:

            self._log(
                "Nenhuma ROM/CHD encontrada nas máquinas selecionadas.",
                level=logging.WARNING,
            )

            return [
                MachineScanResult(
                    machine_name=str(
                        _get_value(
                            machine,
                            "name",
                            "",
                        )
                    )
                )
                for machine in machines_list
            ]

        # ------------------------------------------------------------------
        # SINGLE THREAD
        # ------------------------------------------------------------------

        if self.max_workers == 1:

            return self._scan_sequential(
                machines_list,
                total_items,
            )

        # ------------------------------------------------------------------
        # MULTI THREAD
        # ------------------------------------------------------------------

        return self._scan_parallel(
            machines_list,
            total_items,
        )

    def _scan_sequential(
        self,
        machines: list[Any],
        total_items: int,
    ) -> list[MachineScanResult]:
        """
        Executa o scan sequencialmente.

        É particularmente útil para depuração e testes.

        Args:
            machines:
                Máquinas.

            total_items:
                Total de ROMs/CHDs.

        Returns:
            Resultados.
        """

        results: list[
            MachineScanResult
        ] = []

        completed = 0

        for machine in machines:

            if self.cancelled:
                break

            result = self.scan_machine(
                machine,
                progress_start=completed,
                progress_total=total_items,
            )

            results.append(
                result
            )

            completed += self._machine_result_count(
                result
            )

        self._finish_log(
            results,
            total_items,
        )

        return results

    def _scan_parallel(
        self,
        machines: list[Any],
        total_items: int,
    ) -> list[MachineScanResult]:
        """
        Executa o scan paralelo por máquina.

        A ordem dos resultados é preservada.

        Observação:
        O progresso é emitido dentro de cada worker. A GUI deve utilizar
        sinais Qt ou mecanismo equivalente para atualizar widgets.

        Args:
            machines:
                Máquinas.

            total_items:
                Total global.

        Returns:
            Resultados na ordem original.
        """

        results: list[
            MachineScanResult | None
        ] = [
            None
            for _ in machines
        ]

        progress_offsets: list[int] = []

        offset = 0

        for machine in machines:

            progress_offsets.append(
                offset
            )

            offset += (
                self._machine_item_count(
                    machine
                )
            )

        with ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:

            futures = {}

            for index, machine in enumerate(
                machines
            ):

                if self.cancelled:
                    break

                future = executor.submit(
                    self.scan_machine,
                    machine,
                    progress_start=(
                        progress_offsets[index]
                    ),
                    progress_total=total_items,
                )

                futures[
                    future
                ] = index

            for future in as_completed(
                futures
            ):

                index = futures[
                    future
                ]

                try:

                    result = future.result()

                    results[
                        index
                    ] = result

                except Exception as exc:

                    machine_name = str(
                        _get_value(
                            machines[index],
                            "name",
                            "",
                        )
                    )

                    logger.exception(
                        "Erro escaneando máquina %s.",
                        machine_name,
                    )

                    results[
                        index
                    ] = MachineScanResult(
                        machine_name=machine_name
                    )

        final_results = [
            result
            for result in results
            if result is not None
        ]

        self._finish_log(
            final_results,
            total_items,
        )

        return final_results

    # ========================================================================
    # CONTADORES
    # ========================================================================

    def _machine_item_count(
        self,
        machine: Any,
    ) -> int:
        """
        Retorna a quantidade de itens que serão verificados na máquina.

        Args:
            machine:
                Máquina.

        Returns:
            Quantidade de ROMs + CHDs.
        """

        roms = _get_value(
            machine,
            "roms",
            [],
        )

        disks = _get_value(
            machine,
            "disks",
            [],
        )

        count = len(
            list(
                roms or []
            )
        )

        if self.include_chds:

            count += len(
                list(
                    disks or []
                )
            )

        return count

    @staticmethod
    def _machine_result_count(
        result: Any,
    ) -> int:
        """
        Retorna a quantidade de itens efetivamente processados.

        Args:
            result:
                Resultado da máquina.

        Returns:
            Quantidade.
        """

        return len(
            list(
                _get_value(
                    result,
                    "roms",
                    [],
                )
                or []
            )
        )

    # ========================================================================
    # FINALIZAÇÃO
    # ========================================================================

    def _finish_log(
        self,
        results: list[MachineScanResult],
        total_items: int,
    ) -> None:
        """
        Registra o resumo final do scan.

        Args:
            results:
                Resultados.

            total_items:
                Total planejado.
        """

        total = 0
        found = 0
        valid = 0
        missing = 0
        bad = 0
        error = 0

        for result in results:

            total += result.total
            found += result.found
            valid += result.valid
            missing += result.missing
            bad += result.bad
            error += sum(1 for r in result.roms if r.status == ScanStatus.ERROR)

        self._log(
            "============================================================"
        )

        self._log(
            "Scan finalizado."
        )

        self._log(
            "Itens planejados: %d",
            total_items,
        )

        self._log(
            "Itens processados: %d",
            total,
        )

        self._log(
            "Encontrados: %d",
            found,
        )

        self._log(
            "Válidos: %d",
            valid,
        )

        self._log(
            "Ausentes: %d",
            missing,
        )

        self._log(
            "Inválidos: %d",
            bad,
        )

        self._log(
            "Erros: %d",
            error,
        )

        self._log(
            "Cancelado: %s",
            "SIM"
            if self.cancelled
            else "NÃO",
        )

        self._log(
            "============================================================"
        )


# ============================================================================
# EXCEÇÃO
# ============================================================================

class ScanCancelledError(
    RuntimeError
):
    """
    Exceção interna utilizada para interromper cálculos longos quando
    o usuário cancela o scan.

    Não representa uma falha do scanner.
    """