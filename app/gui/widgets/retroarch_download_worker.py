"""Worker Qt para download do RetroArch e dos cores libretro."""
from __future__ import annotations

import traceback
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.config.app_config import AppConfig
from app.core.services.retroarch_download_service import RetroArchDownloadService


class RetroArchDownloadWorker(QObject):
    """Executa downloads do Buildbot fora da thread da GUI."""

    progress = Signal(int, int)
    status = Signal(str)
    log_message = Signal(str)
    finished = Signal(str, str, str)
    failed = Signal(str)

    def __init__(self, operation: str, destination: Path, mode: str = "nightly", stable_version: str | None = None, core_filename: str | None = None, core_filenames: list[str] | None = None) -> None:
        """Configura uma operação de instalação/atualização."""
        super().__init__()
        self.operation = operation
        self.destination = Path(destination)
        self.mode = mode
        self.stable_version = stable_version
        self.core_filename = core_filename
        self.core_filenames = list(core_filenames or [])

    def _log(self, message: str) -> None:
        """Publica uma mensagem operacional."""
        self.log_message.emit(str(message))

    @Slot()
    def run(self) -> None:
        """Executa a operação selecionada e atualiza AppConfig."""
        try:
            service = RetroArchDownloadService(log_callback=self._log)
            self.status.emit("Consultando Buildbot oficial…")
            channel = service.channel(self.mode, self.stable_version)
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

            if self.operation in {"core", "cores_installed"}:
                self.status.emit("Consultando lista de cores…")
                cores = service.list_cores(channel)
                by_filename = {item.filename: item for item in cores}
                by_name = {item.core_name.casefold(): item for item in cores}
                app_config = AppConfig()
                app_config.load()
                cores_dir = app_config.get_emulator_path("retroarch", "cores") or (self.destination / "cores")
                cores_dir = Path(cores_dir).expanduser().resolve()
                self._log(f"DIRETÓRIO CORES | {cores_dir}")

                if self.operation == "core":
                    requested = self.core_filenames or ([self.core_filename] if self.core_filename else [])
                    selected_cores = [by_filename[name] for name in requested if name in by_filename]
                    if not selected_cores:
                        raise ValueError("Nenhum dos cores selecionados foi encontrado no índice oficial.")
                else:
                    installed = sorted(cores_dir.glob("*_libretro.dll")) if cores_dir.is_dir() else []
                    selected_cores = []
                    for dll in installed:
                        logical = dll.stem.removesuffix("_libretro").casefold()
                        if logical in by_name:
                            selected_cores.append(by_name[logical])
                    if not selected_cores:
                        raise ValueError("Nenhum core instalado corresponde ao índice oficial deste canal. Verifique o diretório Cores importado do retroarch.cfg.")
                    self._log(f"CORES INSTALADOS | candidatos={len(selected_cores)}")

                for index, selected in enumerate(selected_cores, start=1):
                    self.status.emit(f"Baixando core {index}/{len(selected_cores)}: {selected.core_name}…")
                    self._log(f"CORE {index}/{len(selected_cores)} | {selected.core_name} | CRC={selected.crc32}")
                    service.download_core(
                        channel,
                        selected,
                        cores_dir,
                        progress=lambda received, total, offset=index - 1, count=len(selected_cores): self.progress.emit(int(((offset + (received / total if total else 0)) / count) * 100), 100),
                    )
                self.finished.emit("cores", str(len(selected_cores)), str(cores_dir))
                return

            raise ValueError(f"Operação RetroArch desconhecida: {self.operation}")
        except Exception as exc:
            self._log(f"ERRO | {type(exc).__name__}: {exc}")
            self.failed.emit("\n".join((f"{type(exc).__name__}: {exc}", traceback.format_exc())))
