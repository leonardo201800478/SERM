"""
Persistência do diagnóstico de escaneamento do MAME.

Este módulo é responsável exclusivamente pela persistência do resultado
de uma execução de scan.

Formato:
    JSON Lines (JSONL)

Cada linha representa um registro independente:

    header
    machine
    rom
    machine_summary
    scan_summary
    footer

A escolha por JSONL permite:

    - escrita incremental;
    - recuperação após interrupção;
    - arquivos muito grandes sem carregar tudo em memória;
    - processamento posterior por streaming;
    - reconstrução baseada na origem física de cada arquivo.

Estrutura física:

    data/
        database/
            scan/
                scan_YYYYMMDD_HHMMSS_<id>.jsonl
                scan_YYYYMMDD_HHMMSS_<id>.log
                current_scan.jsonl

O arquivo current_scan.jsonl é uma cópia lógica do último manifesto
concluído ou em andamento.

IMPORTANTE
----------
Este módulo não conhece Qt, não acessa SQLite e não executa o scan.

Ele apenas persiste o diagnóstico produzido pelo scanner.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import threading
import uuid

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTES
# ============================================================================

DEFAULT_SCAN_DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "database"
    / "scan"
)

CURRENT_SCAN_FILENAME = "current_scan.jsonl"


# ============================================================================
# HELPERS
# ============================================================================

def _utc_now() -> str:
    """
    Retorna a data/hora atual em UTC no formato ISO-8601.

    Returns
    -------
    str
        Timestamp UTC com indicação explícita do fuso horário.
    """
    return datetime.now(timezone.utc).isoformat()


def _json_default(value: Any) -> Any:
    """
    Converte objetos não suportados diretamente pelo json.dumps().

    São tratados principalmente objetos Path, Enum e dataclasses.

    Parameters
    ----------
    value:
        Objeto que precisa ser convertido.

    Returns
    -------
    Any
        Representação serializável do objeto.

    Raises
    ------
    TypeError
        Caso o objeto não possua uma representação conhecida.
    """
    if isinstance(value, Path):
        return str(value)

    if hasattr(value, "value"):
        return value.value

    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)

    raise TypeError(
        f"Objeto do tipo {type(value).__name__} não é serializável."
    )


def _serialize(value: Any) -> Any:
    """
    Normaliza recursivamente valores para armazenamento no JSONL.

    Parameters
    ----------
    value:
        Valor arbitrário.

    Returns
    -------
    Any
        Valor compatível com JSON.
    """
    if isinstance(value, Path):
        return str(value)

    if hasattr(value, "value"):
        return value.value

    if hasattr(value, "__dataclass_fields__"):
        return {
            key: _serialize(item)
            for key, item in asdict(value).items()
        }

    if isinstance(value, Mapping):
        return {
            str(key): _serialize(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_serialize(item) for item in value]

    return value


# ============================================================================
# MODELOS DE PERSISTÊNCIA
# ============================================================================

@dataclass(slots=True)
class ScanSource:
    """
    Representa a localização física onde uma ROM foi encontrada.

    Uma ROM pode estar:

        - em arquivo solto;
        - dentro de ZIP;
        - dentro de 7Z;
        - em outro arquivo pertencente a outro jogo.

    Attributes
    ----------
    kind:
        Tipo da origem: file, zip, 7z etc.

    archive:
        Caminho físico do arquivo de origem.

    member:
        Nome do membro dentro do arquivo compactado.

    machine:
        Machine à qual o arquivo de origem pertence, quando conhecida.

    """

    kind: str | None = None
    archive: str | None = None
    member: str | None = None
    machine: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Converte a origem para um dicionário serializável."""
        return _serialize(asdict(self))


@dataclass(slots=True)
class ScanRomRecord:
    """
    Registro persistente de uma ROM requisitada por uma machine.

    Este registro é a peça fundamental para a futura reconstrução.

    A diferença entre:

        machine
        ROM requisitada
        origem física

    é mantida explicitamente.

    Assim:

        game_a -> rom.bin -> game_b.zip!rom.bin

    pode ser reconstruído sem assumir que a ROM pertence ao ZIP
    cujo nome corresponde à machine.
    """

    machine: str
    machine_description: str
    rom_name: str

    expected_size: int
    expected_crc: str
    expected_sha1: str | None

    merge: str | None = None
    region: str | None = None

    status: str = "not_scanned"

    actual_size: int | None = None
    actual_crc: str | None = None
    actual_sha1: str | None = None

    source: ScanSource | None = None

    required: bool = True
    optional: bool = False

    error: str | None = None

    scanned_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """
        Converte o registro para o formato persistido.

        Returns
        -------
        dict
            Registro serializável.
        """
        return _serialize(asdict(self))


@dataclass(slots=True)
class ScanMachineRecord:
    """
    Registro persistente de uma machine.

    O registro contém apenas os dados estruturais necessários para
    identificar a machine e os seus relacionamentos.
    """

    name: str
    description: str = ""
    cloneof: str | None = None

    rom_count: int = 0
    status: str = "not_scanned"

    started_at: str | None = None
    completed_at: str | None = None

    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Converte o registro para um dicionário serializável."""
        return _serialize(asdict(self))


# ============================================================================
# WRITER
# ============================================================================

class ScanManifestWriter:
    """
    Escritor streaming do diagnóstico do scan.

    O writer mantém apenas o arquivo aberto e alguns contadores simples.
    Os resultados individuais são gravados imediatamente.

    Exemplo:

        writer = ScanManifestWriter()

        writer.start(
            version="0.289",
            xml_path=xml_path,
            source_paths=rom_paths,
        )

        writer.machine_started(machine)

        writer.write_rom(record)

        writer.machine_finished(machine)

        writer.finish()

    O writer é thread-safe para permitir que o scanner produza resultados
    concorrentes.
    """

    def __init__(
        self,
        directory: Path | str | None = None,
        *,
        copy_to_current: bool = True,
        flush_each_record: bool = True,
    ) -> None:
        """
        Inicializa o writer.

        Parameters
        ----------
        directory:
            Diretório onde os manifests serão armazenados.

        copy_to_current:
            Se True, atualiza current_scan.jsonl após o encerramento.

        flush_each_record:
            Se True, força flush após cada registro para reduzir perda
            de diagnóstico em caso de interrupção.
        """
        self.directory = (
            Path(directory)
            if directory is not None
            else DEFAULT_SCAN_DIRECTORY
        )

        self.copy_to_current = copy_to_current
        self.flush_each_record = flush_each_record

        self.directory.mkdir(parents=True, exist_ok=True)

        self.scan_id: str | None = None
        self.scan_path: Path | None = None
        self.log_path: Path | None = None

        self._file = None
        self._lock = threading.RLock()

        self.started = False
        self.finished = False

        self.machine_count = 0
        self.rom_count = 0

        self.ok_count = 0
        self.fixable_count = 0
        self.missing_count = 0
        self.corrupted_count = 0
        self.unavailable_count = 0
        self.error_count = 0

        self._started_at: str | None = None
        self._finished_at: str | None = None

    # ------------------------------------------------------------------
    # PROPRIEDADES
    # ------------------------------------------------------------------

    @property
    def current_path(self) -> Path:
        """
        Retorna o caminho do manifesto corrente.

        Returns
        -------
        Path
            Caminho de current_scan.jsonl.
        """
        return self.directory / CURRENT_SCAN_FILENAME

    @property
    def is_open(self) -> bool:
        """
        Indica se o manifesto está atualmente aberto para escrita.

        Returns
        -------
        bool
            True quando existe uma execução aberta.
        """
        return self._file is not None

    # ------------------------------------------------------------------
    # ABERTURA
    # ------------------------------------------------------------------

    def start(
        self,
        *,
        version: str = "unknown",
        xml_path: Path | str | None = None,
        source_paths: Iterable[Path | str] = (),
        machine_count: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Path:
        """
        Inicia uma nova execução de scan.

        Parameters
        ----------
        version:
            Versão do MAME usada para gerar o dataset.

        xml_path:
            LISTXML utilizado no scan.

        source_paths:
            Diretórios de origem das ROMs.

        machine_count:
            Quantidade prevista de machines.

        metadata:
            Metadados adicionais.

        Returns
        -------
        Path
            Caminho do arquivo JSONL criado.

        Raises
        ------
        RuntimeError
            Caso já exista uma execução aberta.
        """
        with self._lock:
            if self._file is not None:
                raise RuntimeError(
                    "Já existe uma execução de scan aberta."
                )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = uuid.uuid4().hex[:8]

            self.scan_id = f"{timestamp}_{unique_id}"

            self.scan_path = (
                self.directory
                / f"scan_{self.scan_id}.jsonl"
            )

            self.log_path = (
                self.directory
                / f"scan_{self.scan_id}.log"
            )

            self._file = self.scan_path.open(
                "w",
                encoding="utf-8",
                newline="\n",
            )

            self.started = True
            self.finished = False

            self.machine_count = 0
            self.rom_count = 0

            self.ok_count = 0
            self.fixable_count = 0
            self.missing_count = 0
            self.corrupted_count = 0
            self.unavailable_count = 0
            self.error_count = 0

            self._started_at = _utc_now()
            self._finished_at = None

            header = {
                "record_type": "header",
                "schema_version": 1,
                "scan_id": self.scan_id,
                "started_at": self._started_at,
                "mame_version": version,
                "xml_path": _serialize(xml_path),
                "source_paths": [
                    _serialize(path)
                    for path in source_paths
                ],
                "machine_count_expected": machine_count,
                "metadata": _serialize(metadata or {}),
            }

            self._write_record(header)

            logger.info(
                "Manifest de scan iniciado: %s",
                self.scan_path,
            )

            return self.scan_path

    # ------------------------------------------------------------------
    # REGISTRO GENÉRICO
    # ------------------------------------------------------------------

    def _write_record(self, record: Mapping[str, Any]) -> None:
        """
        Escreve um registro JSON em uma única linha.

        Este método deve ser chamado somente enquanto o writer estiver
        protegido pelo lock.
        """
        if self._file is None:
            raise RuntimeError(
                "Manifesto de scan não está aberto."
            )

        payload = _serialize(dict(record))

        line = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_default,
        )

        self._file.write(line)
        self._file.write("\n")

        if self.flush_each_record:
            self._file.flush()

    # ------------------------------------------------------------------
    # MACHINE
    # ------------------------------------------------------------------

    def machine_started(
        self,
        machine: ScanMachineRecord | Mapping[str, Any],
    ) -> None:
        """
        Registra o início do processamento de uma machine.
        """
        with self._lock:
            if isinstance(machine, ScanMachineRecord):
                data = machine.to_dict()
            else:
                data = _serialize(dict(machine))

            data["started_at"] = data.get(
                "started_at"
            ) or _utc_now()

            self._write_record(
                {
                    "record_type": "machine",
                    "event": "started",
                    "machine": data,
                }
            )

    def machine_finished(
        self,
        machine: ScanMachineRecord | Mapping[str, Any],
    ) -> None:
        """
        Registra a conclusão de uma machine.
        """
        with self._lock:
            if isinstance(machine, ScanMachineRecord):
                data = machine.to_dict()
            else:
                data = _serialize(dict(machine))

            data["completed_at"] = data.get(
                "completed_at"
            ) or _utc_now()

            self.machine_count += 1

            self._write_record(
                {
                    "record_type": "machine",
                    "event": "finished",
                    "machine": data,
                }
            )

    # ------------------------------------------------------------------
    # ROM
    # ------------------------------------------------------------------

    def write_rom(
        self,
        record: ScanRomRecord | Mapping[str, Any],
    ) -> None:
        """
        Persiste imediatamente o resultado de uma ROM.

        A origem física é mantida integralmente para permitir futura
        reconstrução.

        Parameters
        ----------
        record:
            Registro da ROM escaneada.
        """
        with self._lock:
            if isinstance(record, ScanRomRecord):
                data = record.to_dict()
            else:
                data = _serialize(dict(record))

            status = str(
                data.get("status", "not_scanned")
            ).lower()

            self.rom_count += 1

            if status == "ok":
                self.ok_count += 1
            elif status == "fixable":
                self.fixable_count += 1
            elif status == "missing":
                self.missing_count += 1
            elif status == "corrupted":
                self.corrupted_count += 1
            elif status == "unavailable":
                self.unavailable_count += 1
            elif status in {
                "error",
                "failed",
            }:
                self.error_count += 1

            self._write_record(
                {
                    "record_type": "rom",
                    "record": data,
                }
            )

    # ------------------------------------------------------------------
    # EVENTOS
    # ------------------------------------------------------------------

    def write_event(
        self,
        event: str,
        *,
        message: str | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> None:
        """
        Registra um evento arbitrário da execução.

        Útil para:

            - início do índice;
            - erro de ZIP;
            - cancelamento;
            - início da reconstrução;
            - reparo;
            - diagnóstico posterior.

        Parameters
        ----------
        event:
            Nome do evento.

        message:
            Mensagem opcional.

        data:
            Dados adicionais.
        """
        with self._lock:
            self._write_record(
                {
                    "record_type": "event",
                    "event": event,
                    "timestamp": _utc_now(),
                    "message": message,
                    "data": _serialize(data or {}),
                }
            )

    # ------------------------------------------------------------------
    # RESUMO
    # ------------------------------------------------------------------

    def write_summary(
        self,
        *,
        status: str = "running",
        data: Mapping[str, Any] | None = None,
    ) -> None:
        """
        Grava um snapshot das estatísticas atuais.

        O método pode ser utilizado durante o scan sem finalizar
        o manifesto.
        """
        with self._lock:
            summary = {
                "record_type": "scan_summary",
                "status": status,
                "timestamp": _utc_now(),
                "machines": self.machine_count,
                "roms": self.rom_count,
                "ok": self.ok_count,
                "fixable": self.fixable_count,
                "missing": self.missing_count,
                "corrupted": self.corrupted_count,
                "unavailable": self.unavailable_count,
                "errors": self.error_count,
                "data": _serialize(data or {}),
            }

            self._write_record(summary)

    # ------------------------------------------------------------------
    # FINALIZAÇÃO
    # ------------------------------------------------------------------

    def finish(
        self,
        *,
        status: str = "completed",
        error: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Path:
        """
        Finaliza a execução do manifesto.

        O arquivo principal é fechado e, se configurado, copiado
        atomicamente para current_scan.jsonl.

        Parameters
        ----------
        status:
            completed, cancelled ou failed.

        error:
            Erro geral da execução, quando existente.

        metadata:
            Metadados finais adicionais.

        Returns
        -------
        Path
            Caminho do manifesto da execução.
        """
        with self._lock:
            if self._file is None or self.scan_path is None:
                raise RuntimeError(
                    "Nenhuma execução de scan está aberta."
                )

            self._finished_at = _utc_now()

            self._write_record(
                {
                    "record_type": "footer",
                    "status": status,
                    "finished_at": self._finished_at,
                    "error": error,
                    "summary": {
                        "machines": self.machine_count,
                        "roms": self.rom_count,
                        "ok": self.ok_count,
                        "fixable": self.fixable_count,
                        "missing": self.missing_count,
                        "corrupted": self.corrupted_count,
                        "unavailable": self.unavailable_count,
                        "errors": self.error_count,
                    },
                    "metadata": _serialize(metadata or {}),
                }
            )

            self._file.flush()

            try:
                os.fsync(self._file.fileno())
            except OSError:
                logger.debug(
                    "Não foi possível executar fsync no manifesto.",
                    exc_info=True,
                )

            self._file.close()
            self._file = None

            self.finished = True

            if self.copy_to_current:
                self._update_current()

            logger.info(
                "Manifesto de scan finalizado: %s",
                self.scan_path,
            )

            return self.scan_path

    def _update_current(self) -> None:
        """
        Atualiza current_scan.jsonl usando substituição atômica.

        Isso evita deixar um current_scan.jsonl parcialmente escrito
        caso o processo seja interrompido durante a cópia.
        """
        if self.scan_path is None:
            return

        destination = self.current_path

        temp_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".current_scan_",
                suffix=".tmp",
                dir=self.directory,
                delete=False,
            ) as temp:
                temp_path = Path(temp.name)

                with self.scan_path.open(
                    "rb"
                ) as source:
                    shutil.copyfileobj(
                        source,
                        temp,
                        length=1024 * 1024,
                    )

                temp.flush()
                os.fsync(temp.fileno())

            os.replace(temp_path, destination)

            logger.info(
                "current_scan.jsonl atualizado: %s",
                destination,
            )

        except Exception:
            logger.exception(
                "Falha ao atualizar current_scan.jsonl."
            )

            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # CANCELAMENTO / ERRO
    # ------------------------------------------------------------------

    def cancel(self, *, reason: str | None = None) -> Path | None:
        """
        Finaliza o manifesto como cancelado.

        O diagnóstico produzido até o momento permanece disponível.
        """
        if self._file is None:
            return self.scan_path

        return self.finish(
            status="cancelled",
            error=reason,
        )

    def fail(self, error: BaseException | str) -> Path | None:
        """
        Finaliza o manifesto como failed.

        O erro é persistido no footer para diagnóstico posterior.
        """
        if isinstance(error, BaseException):
            message = f"{type(error).__name__}: {error}"
        else:
            message = str(error)

        if self._file is None:
            return self.scan_path

        return self.finish(
            status="failed",
            error=message,
        )

    # ------------------------------------------------------------------
    # CONTEXTO
    # ------------------------------------------------------------------

    def close(self) -> None:
        """
        Fecha o arquivo sem alterar o status.

        Preferir finish(), cancel() ou fail() durante o fluxo normal.
        """
        with self._lock:
            if self._file is not None:
                self._file.flush()
                self._file.close()
                self._file = None

    def __enter__(self) -> "ScanManifestWriter":
        """Permite utilização através de context manager."""
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        """
        Fecha o manifesto ao sair de um context manager.

        Caso uma exceção tenha ocorrido e o manifesto ainda esteja
        aberto, ele é marcado como failed.
        """
        if self._file is None:
            return

        if exc_value is not None:
            self.fail(exc_value)
        else:
            self.close()


# ============================================================================
# READER
# ============================================================================

class ScanManifestReader:
    """
    Leitor streaming de manifestos JSONL.

    Não carrega o arquivo inteiro na memória.

    Pode ser utilizado pela árvore da GUI, pelo resumo e futuramente
    pelo reconstruidor.
    """

    def __init__(self, path: Path | str) -> None:
        """
        Inicializa o leitor.

        Parameters
        ----------
        path:
            Arquivo JSONL a ser lido.
        """
        self.path = Path(path)

    def iter_records(self) -> Iterator[dict[str, Any]]:
        """
        Itera sobre todos os registros válidos do manifesto.

        Registros inválidos são ignorados com warning, permitindo que
        um arquivo parcialmente corrompido ainda seja parcialmente
        recuperado.
        """
        if not self.path.is_file():
            raise FileNotFoundError(
                f"Manifesto não encontrado: {self.path}"
            )

        with self.path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            for line_number, line in enumerate(
                handle,
                start=1,
            ):
                line = line.strip()

                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning(
                        "Registro JSON inválido no manifesto "
                        "%s, linha %d.",
                        self.path,
                        line_number,
                    )
                    continue

                if isinstance(record, dict):
                    yield record

    def iter_roms(self) -> Iterator[dict[str, Any]]:
        """
        Itera somente sobre registros de ROM.
        """
        for record in self.iter_records():
            if record.get("record_type") == "rom":
                value = record.get("record")

                if isinstance(value, dict):
                    yield value

    def iter_machines(self) -> Iterator[dict[str, Any]]:
        """
        Itera sobre eventos de machine.
        """
        for record in self.iter_records():
            if record.get("record_type") != "machine":
                continue

            machine = record.get("machine")

            if isinstance(machine, dict):
                yield machine

    def get_header(self) -> dict[str, Any] | None:
        """
        Retorna o cabeçalho do manifesto.
        """
        for record in self.iter_records():
            if record.get("record_type") == "header":
                return record

        return None

    def get_footer(self) -> dict[str, Any] | None:
        """
        Retorna o footer do manifesto.

        Como o footer é o último registro esperado, o arquivo é
        percorrido até o final.
        """
        footer = None

        for record in self.iter_records():
            if record.get("record_type") == "footer":
                footer = record

        return footer

    def get_summary(self) -> dict[str, Any]:
        """
        Retorna o resumo final ou, caso não exista, o último snapshot
        disponível.

        Returns
        -------
        dict
            Estatísticas do scan.
        """
        summary: dict[str, Any] = {}

        for record in self.iter_records():
            record_type = record.get("record_type")

            if record_type == "scan_summary":
                summary = record

            elif record_type == "footer":
                footer_summary = record.get("summary")

                if isinstance(footer_summary, dict):
                    summary = {
                        **summary,
                        **footer_summary,
                    }

        return summary


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def get_scan_directory(
    base_directory: Path | str | None = None,
) -> Path:
    """
    Retorna o diretório padrão de manifests de scan.

    Parameters
    ----------
    base_directory:
        Diretório raiz opcional do projeto.

    Returns
    -------
    Path
        Diretório data/database/scan.
    """
    if base_directory is None:
        path = DEFAULT_SCAN_DIRECTORY
    else:
        path = Path(base_directory) / "data" / "database" / "scan"

    path.mkdir(parents=True, exist_ok=True)

    return path


def get_current_scan_path(
    base_directory: Path | str | None = None,
) -> Path:
    """
    Retorna o caminho do manifesto corrente.

    Parameters
    ----------
    base_directory:
        Diretório raiz opcional do projeto.

    Returns
    -------
    Path
        Caminho de current_scan.jsonl.
    """
    return (
        get_scan_directory(base_directory)
        / CURRENT_SCAN_FILENAME
    )


def open_current_scan(
    base_directory: Path | str | None = None,
) -> ScanManifestReader | None:
    """
    Abre o manifesto corrente, caso exista.

    Returns
    -------
    ScanManifestReader | None
        Leitor do manifesto ou None se não existir.
    """
    path = get_current_scan_path(base_directory)

    if not path.is_file():
        return None

    return ScanManifestReader(path)