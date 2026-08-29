"""Worker Qt para download do RetroArch e dos cores libretro."""
from __future__ import annotations

import traceback
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.config.app_config import AppConfig
from app.core.services.retroarch_download_service import RetroArchDownloadService


class RetroArchDownloadWorker(QObject):
    """Executa downloads do Buildbot fora da thread da GUI."""

    CORE_ATTEMPTS = 3

    progress = Signal(int, int)
    status = Signal(str)
    log_message = Signal(str)
    # Alias mantido para consumidores que usam a nomenclatura curta.
    log = log_message
    finished = Signal(str, str, str)
    failed = Signal(str)

    def __init__(
        self,
        operation: str,
        destination: Path,
        mode: str = "nightly",
        stable_version: str | None = None,
        core_filename: str | None = None,
        core_filenames: list[str] | None = None,
        *,
        service: RetroArchDownloadService | None = None,
        channel=None,
        selected_cores: list[str] | None = None,
    ) -> None:
        """Configura uma operação de instalação/atualização.

        ``service``, ``channel`` e ``selected_cores`` são aliases de integração
        usados pela Home. Os parâmetros originais continuam compatíveis.
        """
        super().__init__()
        self.operation = operation
        self.destination = Path(destination)
        self.mode = mode
        self.stable_version = stable_version
        self.core_filename = core_filename
        self.core_filenames = list(core_filenames or selected_cores or [])
        self._service = service
        self._channel_override = channel

    def _log(self, message: str) -> None:
        """Publica uma mensagem operacional."""
        self.log_message.emit(str(message))

    @Slot()
    def run(self) -> None:
        """Executa a operação selecionada e atualiza AppConfig."""
        try:
            service = self._service or RetroArchDownloadService(log_callback=self._log)
            self.status.emit("Consultando Buildbot oficial…")
            channel = self._channel_override or service.channel(self.mode, self.stable_version)
            self._log(f"CANAL | {channel.name} | base={channel.base_url}")

            if self.operation in {"install", "update"}:
                self.status.emit("Baixando RetroArch…")
                archive = service.download_retroarch(channel, self.destination, progress=lambda received, total: self.progress.emit(received, total))
                preserve = self.operation == "update"
                self.status.emit("Extraindo RetroArch…")
                executable = service.install_retroarch(archive, self.destination, preserve_config=preserve)
                config = AppConfig()
                config.retroarch_path = executable
                config.retroarch_dir = self.destination
                detected = service.detect_installed_version(executable)
                config.retroarch_version = detected or channel.version or "nightly"
                self._log(f"VERSÃO | detectada={detected or 'não detectada'} | canal={channel.name}")
                try:
                    config.set_retroarch_executable(executable)
                except (FileNotFoundError, OSError, ValueError) as exc:
                    self._log(f"AVISO | retroarch.cfg não pôde ser importado após instalação: {exc}")
                config.save()
                self.finished.emit("retroarch", config.retroarch_version or "nightly", str(executable))
                return

            if self.operation in {"core", "cores_installed", "cores"}:
                self.status.emit("Consultando lista de cores…")
                cores = service.list_cores(channel)
                by_filename = {item.filename: item for item in cores}
                app_config = AppConfig()
                app_config.load()
                cores_dir = app_config.get_emulator_path("retroarch", "cores") or (self.destination / "cores")
                cores_dir = Path(cores_dir).expanduser().resolve()
                self._log(f"DIRETÓRIO CORES | {cores_dir}")

                if self.operation in {"core", "cores"}:
                    requested = self.core_filenames or ([self.core_filename] if self.core_filename else [])
                    selected_cores = [by_filename[name] for name in requested if name in by_filename]
                    if not selected_cores:
                        raise ValueError("Nenhum dos cores selecionados foi encontrado no índice oficial.")
                else:
                    comparisons = service.compare_installed_cores(cores, cores_dir)
                    selected_cores = []
                    for comparison in comparisons:
                        if comparison.remote_crc32 is None:
                            self._log(f"CORE IGNORADO | {comparison.core_name} | não encontrado no índice oficial")
                            continue
                        remote = next((item for item in cores if item.filename.casefold() == f"{comparison.path.name}.zip".casefold()), None)
                        if remote is None:
                            continue
                        if comparison.is_current:
                            self._log(f"CORE ATUALIZADO | {comparison.core_name} | CRC={comparison.local_crc32}")
                        elif comparison.needs_update:
                            selected_cores.append(remote)
                            self._log(f"ATUALIZAÇÃO DISPONÍVEL | {comparison.core_name} | local={comparison.local_crc32} | remoto={comparison.remote_crc32}")
                    self._log(f"COMPARAÇÃO CRC | instalados={len(comparisons)} | atualizações={len(selected_cores)}")
                    if not selected_cores:
                        self.status.emit("Todos os cores instalados já estão atualizados.")
                        self.finished.emit("cores", "0", str(cores_dir))
                        return

                successful = 0
                failed_cores: list[str] = []
                for index, selected in enumerate(selected_cores, start=1):
                    completed = False
                    last_error: Exception | None = None
                    for attempt in range(1, self.CORE_ATTEMPTS + 1):
                        self.status.emit(f"Baixando core {index}/{len(selected_cores)}: {selected.core_name} (tentativa {attempt}/{self.CORE_ATTEMPTS})…")
                        self._log(f"CORE {index}/{len(selected_cores)} | {selected.core_name} | CRC={selected.crc32} | tentativa={attempt}/{self.CORE_ATTEMPTS}")
                        try:
                            service.download_core(
                                channel,
                                selected,
                                cores_dir,
                                progress=lambda received, total, offset=index - 1, count=len(selected_cores): self.progress.emit(int(((offset + (received / total if total else 0)) / count) * 100), 100),
                            )
                            completed = True
                            successful += 1
                            break
                        except Exception as exc:
                            last_error = exc
                            self._log(f"FALHA CORE | {selected.core_name} | tentativa={attempt}/{self.CORE_ATTEMPTS} | {type(exc).__name__}: {exc}")
                    if not completed:
                        failed_cores.append(selected.core_name)
                        self._log(f"CORE PULADO | {selected.core_name} | falha após {self.CORE_ATTEMPTS} tentativas | erro={last_error}")

                if failed_cores:
                    self._log(f"ATUALIZAÇÃO CONCLUÍDA COM FALHAS | sucesso={successful} | falhas={len(failed_cores)} | cores_com_falha={', '.join(failed_cores)}")
                else:
                    self._log(f"ATUALIZAÇÃO CONCLUÍDA | sucesso={successful} | falhas=0")
                self.finished.emit("cores", str(successful), str(cores_dir))
                return

            raise ValueError(f"Operação RetroArch desconhecida: {self.operation}")
        except Exception as exc:
            self._log(f"ERRO | {type(exc).__name__}: {exc}")
            self.failed.emit("\n".join((f"{type(exc).__name__}: {exc}", traceback.format_exc())))
