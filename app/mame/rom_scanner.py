"""
MAME Set Builder - ROM Scanner
==============================

Responsável por verificar as ROMs presentes no XML filtrado contra os
arquivos físicos existentes nas pastas configuradas para o MAME.

Princípios deste scanner:

1. Somente ROMs presentes no XML fornecido são analisadas.
2. Nenhuma varredura global de todos os arquivos é realizada antes do scan.
3. ZIPs são abertos somente quando necessários.
4. Cada ROM analisada gera um evento de progresso.
5. Cada ROM analisada gera log.
6. O processo pode ser cancelado pelo usuário.
7. Um erro em uma ROM não interrompe o restante do scan.

O XML filtrado deve ser a fonte de verdade para determinar quais ROMs
precisam ser verificadas.
"""

from __future__ import annotations

import logging
import threading
import zipfile

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)

logger = logging.getLogger(__name__)


# ============================================================================
# RESULTADOS
# ============================================================================


@dataclass
class RomScanResult:
    """
    Resultado da verificação de uma ROM.

    Attributes:
        machine_name:
            Nome da máquina no XML.

        rom_name:
            Nome esperado da ROM.

        expected_size:
            Tamanho informado pelo XML.

        expected_crc:
            CRC informado pelo XML.

        found:
            Indica se a ROM foi encontrada.

        valid:
            Indica se a ROM encontrada é válida.

        status:
            Estado final da ROM.

        path:
            Arquivo físico onde a ROM foi encontrada.

        actual_size:
            Tamanho real encontrado.

        actual_crc:
            CRC real encontrado.

        source:
            Arquivo ZIP ou diretório onde a ROM foi localizada.

        message:
            Informação adicional sobre o resultado.
    """

    machine_name: str
    rom_name: str

    expected_size: int = 0
    expected_crc: str = ""

    found: bool = False
    valid: bool = False

    status: str = "missing"

    path: Path | None = None

    actual_size: int = 0
    actual_crc: str = ""

    source: Path | None = None

    message: str = ""


@dataclass
class MachineScanResult:
    """
    Resultado do scan de uma máquina.

    Attributes:
        machine_name:
            Nome da máquina.

        roms:
            Resultados das ROMs da máquina.

        total:
            Total de ROMs verificadas.

        found:
            Quantidade de ROMs encontradas.

        valid:
            Quantidade de ROMs válidas.

        missing:
            Quantidade de ROMs ausentes.

        bad:
            Quantidade de ROMs encontradas porém inválidas.

        error:
            Quantidade de ROMs que apresentaram erro durante a análise.
    """

    machine_name: str

    roms: list[RomScanResult] = field(default_factory=list)

    total: int = 0
    found: int = 0
    valid: int = 0
    missing: int = 0
    bad: int = 0
    error: int = 0

    @property
    def complete(self) -> bool:
        """
        Retorna True quando todas as ROMs da máquina são válidas.
        """
        return (
            self.total > 0
            and self.valid == self.total
        )


# ============================================================================
# CALLBACKS
# ============================================================================


ProgressCallback = Callable[
    [int, int, RomScanResult],
    None,
]

LogCallback = Callable[
    [str],
    None,
]


# ============================================================================
# SCANNER
# ============================================================================


class RomScanner:
    """
    Scanner de ROMs do MAME.

    O scanner recebe exclusivamente as máquinas provenientes do XML
    filtrado. Dessa maneira, máquinas e ROMs que não fazem parte do
    conjunto selecionado não são analisadas.

    Args:
        rom_paths:
            Diretórios onde as ROMs do MAME estão armazenadas.

        max_workers:
            Número máximo de threads utilizadas para o scan.

        progress_callback:
            Callback chamado após cada ROM analisada.

        log_callback:
            Callback opcional para exibição das mensagens na interface.

        enable_alternate_search:
            Mantido por compatibilidade com versões anteriores.

            Quando False, o scanner procura somente nos locais diretamente
            relacionados à máquina.

            O valor padrão é False para evitar uma varredura global de
            arquivos que não pertencem ao XML filtrado.
    """

    def __init__(
        self,
        rom_paths: Iterable[str | Path],
        max_workers: int = 4,
        progress_callback: ProgressCallback | None = None,
        log_callback: LogCallback | None = None,
        enable_alternate_search: bool = False,
    ):
        self.rom_paths = [
            Path(path)
            for path in rom_paths
        ]

        self.max_workers = max(
            1,
            int(max_workers),
        )

        self.progress_callback = progress_callback
        self.log_callback = log_callback

        self.enable_alternate_search = (
            enable_alternate_search
        )

        self._cancel_event = threading.Event()

        logger.info(
            "RomScanner inicializado: %d diretório(s), "
            "%d worker(s), alternate_search=%s",
            len(self.rom_paths),
            self.max_workers,
            self.enable_alternate_search,
        )

    # =========================================================================
    # CONTROLE
    # =========================================================================

    def cancel(self) -> None:
        """
        Solicita o cancelamento do scan.

        O cancelamento é cooperativo. A ROM atualmente em processamento
        pode terminar normalmente, mas novas ROMs não serão iniciadas.
        """
        logger.info(
            "Solicitação de cancelamento recebida."
        )

        self._cancel_event.set()

    def reset_cancel(self) -> None:
        """
        Limpa o estado de cancelamento.

        Deve ser chamado antes de iniciar um novo scan utilizando a mesma
        instância.
        """
        self._cancel_event.clear()

    @property
    def cancelled(self) -> bool:
        """
        Retorna True quando o scan foi cancelado.
        """
        return self._cancel_event.is_set()

    # =========================================================================
    # LOG
    # =========================================================================

    def _log(
        self,
        message: str,
        *args,
        level: int = logging.INFO,
    ) -> None:
        """
        Registra uma mensagem no logger e, opcionalmente, envia a mensagem
        para a interface gráfica.
        """
        logger.log(
            level,
            message,
            *args,
        )

        if self.log_callback is not None:
            try:
                formatted = message % args if args else message

                self.log_callback(
                    formatted
                )

            except Exception:
                logger.exception(
                    "Erro no log_callback."
                )

    # =========================================================================
    # NORMALIZAÇÃO
    # =========================================================================

    @staticmethod
    def _normalize_crc(
        crc: str | None,
    ) -> str:
        """
        Normaliza um CRC para comparação.

        Remove espaços e converte para letras minúsculas.
        """
        if not crc:
            return ""

        return str(crc).strip().lower()

    @staticmethod
    def _normalize_name(
        name: str | None,
    ) -> str:
        """
        Normaliza o nome de uma ROM para comparação.
        """
        if not name:
            return ""

        return str(name).replace(
            "\\",
            "/",
        ).strip()

    # =========================================================================
    # CAMINHOS
    # =========================================================================

    def _machine_candidates(
        self,
        machine_name: str,
    ) -> list[Path]:
        """
        Retorna os possíveis arquivos físicos da máquina.

        Para uma máquina 'sf2', por exemplo, serão considerados:

            sf2.zip
            sf2/

        Não é feita uma busca recursiva por todos os ZIPs existentes.

        Isso é fundamental para manter o scanner rápido em fullsets grandes.
        """
        candidates: list[Path] = []

        for base in self.rom_paths:
            if not base.exists():
                continue

            candidates.append(
                base / f"{machine_name}.zip"
            )

            candidates.append(
                base / machine_name
            )

        return candidates

    # =========================================================================
    # LEITURA DE ZIP
    # =========================================================================

    def _scan_zip(
        self,
        zip_path: Path,
        machine_name: str,
        rom_name: str,
        expected_size: int,
        expected_crc: str,
    ) -> RomScanResult | None:
        """
        Procura uma ROM dentro de um arquivo ZIP específico.

        Retorna None quando o ZIP não contém uma entrada com o nome
        solicitado.
        """
        try:
            with zipfile.ZipFile(
                zip_path,
                "r",
            ) as archive:

                normalized_target = self._normalize_name(
                    rom_name
                )

                for info in archive.infolist():

                    if info.is_dir():
                        continue

                    entry_name = self._normalize_name(
                        info.filename
                    )

                    if entry_name != normalized_target:
                        continue

                    actual_size = info.file_size

                    actual_crc = (
                        f"{info.CRC:08x}"
                    )

                    normalized_expected_crc = (
                        self._normalize_crc(
                            expected_crc
                        )
                    )

                    size_ok = (
                        expected_size <= 0
                        or actual_size == expected_size
                    )

                    crc_ok = (
                        not normalized_expected_crc
                        or actual_crc
                        == normalized_expected_crc
                    )

                    valid = (
                        size_ok
                        and crc_ok
                    )

                    if valid:
                        status = "good"

                    else:
                        status = "bad"

                    return RomScanResult(
                        machine_name=machine_name,
                        rom_name=rom_name,
                        expected_size=expected_size,
                        expected_crc=expected_crc,
                        found=True,
                        valid=valid,
                        status=status,
                        path=zip_path,
                        actual_size=actual_size,
                        actual_crc=actual_crc,
                        source=zip_path,
                        message=(
                            "ROM encontrada no ZIP."
                            if valid
                            else (
                                "ROM encontrada, mas "
                                "tamanho ou CRC inválido."
                            )
                        ),
                    )

        except zipfile.BadZipFile:
            self._log(
                "ZIP inválido: %s",
                zip_path,
                level=logging.WARNING,
            )

        except OSError as exc:
            self._log(
                "Erro lendo ZIP %s: %s",
                zip_path,
                exc,
                level=logging.WARNING,
            )

        except Exception:
            logger.exception(
                "Erro inesperado lendo ZIP: %s",
                zip_path,
            )

        return None

    # =========================================================================
    # ROM DESCOMPACTADA
    # =========================================================================

    def _scan_raw_file(
        self,
        file_path: Path,
        machine_name: str,
        rom_name: str,
        expected_size: int,
        expected_crc: str,
    ) -> RomScanResult:
        """
        Verifica uma ROM armazenada como arquivo descompactado.

        O CRC é calculado apenas quando necessário. Para evitar carregar
        arquivos enormes inteiramente em memória, o cálculo é realizado
        em blocos.
        """
        import binascii

        try:
            actual_size = file_path.stat().st_size

            crc_value = 0

            with file_path.open(
                "rb"
            ) as file:

                while True:
                    chunk = file.read(
                        1024 * 1024
                    )

                    if not chunk:
                        break

                    crc_value = binascii.crc32(
                        chunk,
                        crc_value,
                    )

            actual_crc = (
                f"{crc_value & 0xffffffff:08x}"
            )

            normalized_expected_crc = (
                self._normalize_crc(
                    expected_crc
                )
            )

            size_ok = (
                expected_size <= 0
                or actual_size == expected_size
            )

            crc_ok = (
                not normalized_expected_crc
                or actual_crc
                == normalized_expected_crc
            )

            valid = (
                size_ok
                and crc_ok
            )

            return RomScanResult(
                machine_name=machine_name,
                rom_name=rom_name,
                expected_size=expected_size,
                expected_crc=expected_crc,
                found=True,
                valid=valid,
                status=(
                    "good"
                    if valid
                    else "bad"
                ),
                path=file_path,
                actual_size=actual_size,
                actual_crc=actual_crc,
                source=file_path.parent,
                message=(
                    "ROM encontrada."
                    if valid
                    else (
                        "ROM encontrada, mas "
                        "tamanho ou CRC inválido."
                    )
                ),
            )

        except OSError as exc:
            return RomScanResult(
                machine_name=machine_name,
                rom_name=rom_name,
                expected_size=expected_size,
                expected_crc=expected_crc,
                found=False,
                valid=False,
                status="error",
                path=file_path,
                source=file_path.parent,
                message=str(exc),
            )

    # =========================================================================
    # ROM INDIVIDUAL
    # =========================================================================

    def scan_rom(
        self,
        machine_name: str,
        rom: dict,
    ) -> RomScanResult:
        """
        Analisa uma única ROM.

        A busca segue somente os caminhos associados à máquina:

            1. <rom_path>/<machine>.zip
            2. <rom_path>/<machine>/<rom>

        Não existe busca global pelos demais ZIPs.
        """
        rom_name = self._normalize_name(
            rom.get("name")
        )

        expected_size = int(
            rom.get("size") or 0
        )

        expected_crc = self._normalize_crc(
            rom.get("crc")
        )

        if not rom_name:
            return RomScanResult(
                machine_name=machine_name,
                rom_name="",
                expected_size=expected_size,
                expected_crc=expected_crc,
                status="error",
                message="ROM sem nome no XML.",
            )

        self._log(
            "Analisando ROM: máquina=%s | rom=%s | "
            "size=%d | crc=%s",
            machine_name,
            rom_name,
            expected_size,
            expected_crc or "-",
        )

        # ---------------------------------------------------------------------
        # 1. ZIP DA MÁQUINA
        # ---------------------------------------------------------------------

        zip_candidates = [
            path
            for path in self._machine_candidates(
                machine_name
            )
            if path.is_file()
            and path.suffix.lower() == ".zip"
        ]

        for zip_path in zip_candidates:

            if self.cancelled:
                return RomScanResult(
                    machine_name=machine_name,
                    rom_name=rom_name,
                    expected_size=expected_size,
                    expected_crc=expected_crc,
                    status="cancelled",
                    message="Scan cancelado.",
                )

            result = self._scan_zip(
                zip_path=zip_path,
                machine_name=machine_name,
                rom_name=rom_name,
                expected_size=expected_size,
                expected_crc=expected_crc,
            )

            if result is not None:
                self._log_rom_result(
                    result
                )

                return result

        # ---------------------------------------------------------------------
        # 2. DIRETÓRIO DA MÁQUINA
        # ---------------------------------------------------------------------

        for base in self.rom_paths:

            machine_dir = (
                base / machine_name
            )

            if not machine_dir.is_dir():
                continue

            file_path = (
                machine_dir
                / rom_name
            )

            if not file_path.is_file():
                continue

            result = self._scan_raw_file(
                file_path=file_path,
                machine_name=machine_name,
                rom_name=rom_name,
                expected_size=expected_size,
                expected_crc=expected_crc,
            )

            self._log_rom_result(
                result
            )

            return result

        # ---------------------------------------------------------------------
        # 3. AUSENTE
        # ---------------------------------------------------------------------

        result = RomScanResult(
            machine_name=machine_name,
            rom_name=rom_name,
            expected_size=expected_size,
            expected_crc=expected_crc,
            found=False,
            valid=False,
            status="missing",
            message="ROM não encontrada.",
        )

        self._log_rom_result(
            result
        )

        return result

    # =========================================================================
    # LOG DO RESULTADO
    # =========================================================================

    def _log_rom_result(
        self,
        result: RomScanResult,
    ) -> None:
        """
        Registra o resultado de uma ROM.

        Todas as ROMs passam por este método, inclusive as válidas.
        """
        status_map = {
            "good": "OK",
            "bad": "RUIM",
            "missing": "AUSENTE",
            "error": "ERRO",
            "cancelled": "CANCELADA",
        }

        status_text = status_map.get(
            result.status,
            result.status.upper(),
        )

        if result.found:
            self._log(
                "[ROM] %-10s | máquina=%s | rom=%s | "
                "esperado=%d bytes/%s | encontrado=%d bytes/%s",
                status_text,
                result.machine_name,
                result.rom_name,
                result.expected_size,
                result.expected_crc or "-",
                result.actual_size,
                result.actual_crc or "-",
            )

        else:
            self._log(
                "[ROM] %-10s | máquina=%s | rom=%s | "
                "esperado=%d bytes/%s | %s",
                status_text,
                result.machine_name,
                result.rom_name,
                result.expected_size,
                result.expected_crc or "-",
                result.message,
            )

    # =========================================================================
    # MÁQUINA
    # =========================================================================

    def scan_machine(
        self,
        machine: dict,
    ) -> MachineScanResult:
        """
        Analisa todas as ROMs de uma máquina.

        O objeto machine deve representar uma máquina já filtrada pelo
        XML anterior.
        """
        machine_name = str(
            machine.get("name") or ""
        )

        roms = machine.get(
            "roms",
            [],
        )

        result = MachineScanResult(
            machine_name=machine_name
        )

        if not machine_name:
            return result

        if not isinstance(
            roms,
            (list, tuple),
        ):
            roms = list(roms)

        self._log(
            "Iniciando máquina: %s | %d ROM(s)",
            machine_name,
            len(roms),
        )

        for rom in roms:

            if self.cancelled:
                break

            rom_result = self.scan_rom(
                machine_name=machine_name,
                rom=rom,
            )

            result.roms.append(
                rom_result
            )

            result.total += 1

            if rom_result.status == "good":
                result.found += 1
                result.valid += 1

            elif rom_result.status == "bad":
                result.found += 1
                result.bad += 1

            elif rom_result.status == "missing":
                result.missing += 1

            elif rom_result.status == "error":
                result.error += 1

        self._log(
            "Máquina concluída: %s | total=%d | "
            "válidas=%d | ausentes=%d | ruins=%d | erros=%d",
            machine_name,
            result.total,
            result.valid,
            result.missing,
            result.bad,
            result.error,
        )

        return result

    # =========================================================================
    # SCAN COMPLETO
    # =========================================================================

    def scan(
        self,
        machines: Iterable[dict],
    ) -> list[MachineScanResult]:
        """
        Executa o scan completo das máquinas do XML filtrado.

        O número total de ROMs é calculado antes do processamento para que
        a interface possa apresentar uma barra de progresso determinística.

        Args:
            machines:
                Iterable contendo somente máquinas provenientes do XML
                filtrado.

        Returns:
            Lista de MachineScanResult.
        """
        self.reset_cancel()

        machines = list(
            machines
        )

        total_roms = sum(
            len(
                machine.get(
                    "roms",
                    [],
                )
            )
            for machine in machines
        )

        self._log(
            "============================================================"
        )

        self._log(
            "Iniciando scan de ROMs."
        )

        self._log(
            "Máquinas selecionadas: %d",
            len(machines),
        )

        self._log(
            "ROMs a verificar: %d",
            total_roms,
        )

        self._log(
            "Diretórios de ROM: %s",
            ", ".join(
                str(path)
                for path in self.rom_paths
            ),
        )

        self._log(
            "============================================================"
        )

        if total_roms == 0:
            self._log(
                "Nenhuma ROM encontrada no XML filtrado.",
                level=logging.WARNING,
            )

            return []

        completed_roms = 0

        results_by_index: dict[
            int,
            MachineScanResult,
        ] = {}

        # ---------------------------------------------------------------------
        # PROCESSAMENTO
        # ---------------------------------------------------------------------
        #
        # Cada máquina é uma unidade de trabalho.
        #
        # A atualização de progresso ocorre por ROM através de
        # _emit_progress().
        #
        # Como cada máquina contém várias ROMs, o callback é disparado
        # individualmente após cada ROM.
        #
        # ---------------------------------------------------------------------

        if self.max_workers == 1:

            for index, machine in enumerate(
                machines
            ):

                if self.cancelled:
                    break

                result = self.scan_machine_with_progress(
                    machine,
                    completed_roms,
                    total_roms,
                )

                results_by_index[
                    index
                ] = result

                completed_roms += result.total

        else:

            # Em execução paralela, cada máquina possui seu próprio worker.
            #
            # O callback pode ser chamado por threads diferentes. A GUI deve
            # tratar o callback adequadamente, preferencialmente através de
            # sinais Qt ou mecanismo equivalente.

            with ThreadPoolExecutor(
                max_workers=self.max_workers
            ) as executor:

                futures = {
                    executor.submit(
                        self.scan_machine,
                        machine,
                    ): index
                    for index, machine
                    in enumerate(machines)
                    if not self.cancelled
                }

                for future in as_completed(
                    futures
                ):

                    if self.cancelled:
                        break

                    index = futures[
                        future
                    ]

                    try:
                        result = future.result()

                    except Exception as exc:

                        machine_name = str(
                            machines[index].get(
                                "name",
                                "",
                            )
                        )

                        logger.exception(
                            "Erro escaneando máquina %s",
                            machine_name,
                        )

                        result = MachineScanResult(
                            machine_name=machine_name
                        )

                    results_by_index[
                        index
                    ] = result

                    completed_roms += result.total

                    # scan_machine não envia callbacks individuais no
                    # processamento paralelo porque isso poderia provocar
                    # atualizações concorrentes na GUI.
                    #
                    # Emitimos o progresso da máquina concluída aqui.

                    if self.progress_callback:
                        for rom_result in result.roms:

                            try:
                                self.progress_callback(
                                    min(
                                        completed_roms
                                        - result.total
                                        + result.roms.index(
                                            rom_result
                                        )
                                        + 1,
                                        total_roms,
                                    ),
                                    total_roms,
                                    rom_result,
                                )

                            except Exception:
                                logger.exception(
                                    "Erro no progress_callback."
                                )

        # ---------------------------------------------------------------------
        # PRESERVAR ORDEM DO XML
        # ---------------------------------------------------------------------

        ordered_results = [
            results_by_index[index]
            for index in sorted(
                results_by_index
            )
        ]

        # ---------------------------------------------------------------------
        # RESUMO
        # ---------------------------------------------------------------------

        total_checked = sum(
            result.total
            for result in ordered_results
        )

        total_valid = sum(
            result.valid
            for result in ordered_results
        )

        total_missing = sum(
            result.missing
            for result in ordered_results
        )

        total_bad = sum(
            result.bad
            for result in ordered_results
        )

        total_errors = sum(
            result.error
            for result in ordered_results
        )

        self._log(
            "============================================================"
        )

        self._log(
            "Scan finalizado%s.",
            " por cancelamento"
            if self.cancelled
            else "",
        )

        self._log(
            "ROMs processadas: %d/%d",
            total_checked,
            total_roms,
        )

        self._log(
            "Válidas: %d | Ausentes: %d | "
            "Ruins: %d | Erros: %d",
            total_valid,
            total_missing,
            total_bad,
            total_errors,
        )

        self._log(
            "============================================================"
        )

        return ordered_results

    # =========================================================================
    # SCAN COM PROGRESSO
    # =========================================================================

    def scan_machine_with_progress(
        self,
        machine: dict,
        completed_before: int,
        total_roms: int,
    ) -> MachineScanResult:
        """
        Analisa uma máquina e envia o progresso após cada ROM.

        Esta versão é utilizada quando max_workers=1, pois nesse cenário
        o callback pode ser atualizado diretamente sem risco de concorrência.
        """
        machine_name = str(
            machine.get("name") or ""
        )

        roms = machine.get(
            "roms",
            [],
        )

        if not isinstance(
            roms,
            (list, tuple),
        ):
            roms = list(roms)

        result = MachineScanResult(
            machine_name=machine_name
        )

        for rom in roms:

            if self.cancelled:
                break

            rom_result = self.scan_rom(
                machine_name=machine_name,
                rom=rom,
            )

            result.roms.append(
                rom_result
            )

            result.total += 1

            if rom_result.status == "good":
                result.found += 1
                result.valid += 1

            elif rom_result.status == "bad":
                result.found += 1
                result.bad += 1

            elif rom_result.status == "missing":
                result.missing += 1

            elif rom_result.status == "error":
                result.error += 1

            current = (
                completed_before
                + result.total
            )

            self._emit_progress(
                current=current,
                total=total_roms,
                result=rom_result,
            )

        return result

    # =========================================================================
    # CALLBACK DE PROGRESSO
    # =========================================================================

    def _emit_progress(
        self,
        current: int,
        total: int,
        result: RomScanResult,
    ) -> None:
        """
        Envia uma atualização de progresso para a interface.

        Args:
            current:
                Número da ROM atualmente concluída.

            total:
                Número total de ROMs do XML filtrado.

            result:
                Resultado da ROM recém-processada.
        """
        if self.progress_callback is None:
            return

        try:
            self.progress_callback(
                current,
                total,
                result,
            )

        except Exception:
            logger.exception(
                "Erro executando progress_callback."
            )


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================


def create_rom_scanner(
    rom_paths: Iterable[str | Path],
    *,
    max_workers: int = 4,
    progress_callback: ProgressCallback | None = None,
    log_callback: LogCallback | None = None,
) -> RomScanner:
    """
    Cria uma instância configurada do RomScanner.

    A busca alternativa é explicitamente desativada para garantir que
    somente os arquivos relacionados às máquinas do XML filtrado sejam
    considerados.

    Args:
        rom_paths:
            Diretórios de ROMs.

        max_workers:
            Quantidade máxima de workers.

        progress_callback:
            Callback de progresso.

        log_callback:
            Callback de log.

    Returns:
        Instância configurada de RomScanner.
    """
    return RomScanner(
        rom_paths=rom_paths,
        max_workers=max_workers,
        progress_callback=progress_callback,
        log_callback=log_callback,
        enable_alternate_search=False,
    )