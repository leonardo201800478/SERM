"""Correções de compatibilidade para a Home do RetroArch.

O Buildbot informa no ``.index-extended`` o CRC do pacote ZIP do core.
O índice pode ficar temporariamente divergente do artefato publicado; por isso
validamos a integridade real do ZIP antes da instalação e tratamos o CRC do
índice como aviso quando houver divergência.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

from .emulator_manager import DownloadResult, EmulatorManager, RetroArchManager


def _install_core(
    self: RetroArchManager,
    filename: str,
    destination: Path,
    *,
    channel: str = "nightly",
    stable_version: str | None = None,
    progress=None,
    log=None,
) -> Path:
    """Baixa e instala um core Nightly com validação estrutural do ZIP."""
    if channel.casefold() != "nightly":
        raise RuntimeError(
            "O Buildbot Stable não publica cores individuais. "
            "O pacote Stable de cores é RetroArch_cores.7z; cores individuais usam Nightly."
        )

    filename = Path(filename).name
    if not filename.casefold().endswith("_libretro.dll.zip"):
        raise ValueError(f"Nome de core inválido para download: {filename!r}")

    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="serm-core-"))
    archive = temp_dir / filename

    try:
        url = f"{self.NIGHTLY_ROOT}{filename}"
        if log:
            log(f"DOWNLOAD | core={filename} | temporário={archive}")
        self._download_file(url, archive, progress, log)

        remote = next(
            (
                core
                for core in self.list_cores("nightly", stable_version)
                if core.filename.casefold() == filename.casefold()
            ),
            None,
        )
        actual_crc = self._crc32(archive)
        if remote is None:
            raise RuntimeError(f"Core não encontrado no índice Nightly: {filename}")
        if remote.crc32 and remote.crc32 != actual_crc:
            if log:
                log(
                    f"AVISO | CRC32 do índice divergente para {filename}: "
                    f"recebido={actual_crc}, índice={remote.crc32}; "
                    "prosseguindo com validação estrutural do ZIP"
                )

        with zipfile.ZipFile(archive) as package:
            bad = package.testzip()
            if bad:
                raise RuntimeError(f"ZIP corrompido do core: {bad}")
            dll_names = [
                name
                for name in package.namelist()
                if name.casefold().endswith("_libretro.dll")
            ]
            if not dll_names:
                raise RuntimeError(f"ZIP sem DLL libretro: {filename}")
            dll_name = Path(dll_names[0]).name
            data = package.read(dll_names[0])

        target = (destination / dll_name).resolve()
        if destination not in target.parents:
            raise RuntimeError("Caminho inseguro no core.")
        temp_dll = target.with_suffix(target.suffix + ".tmp")
        temp_dll.write_bytes(data)
        try:
            temp_dll.replace(target)
        finally:
            temp_dll.unlink(missing_ok=True)

        if log:
            log(f"CORE INSTALADO | {target} | CRC32 pacote={actual_crc}")
        return target
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _install_frontend(
    self: RetroArchManager,
    destination: Path,
    *,
    channel: str = "stable",
    progress=None,
    log=None,
) -> DownloadResult:
    """Baixa, testa, descompacta e instala o frontend RetroArch x64."""
    channel = channel.casefold().strip()
    if channel not in {"stable", "nightly"}:
        raise ValueError(f"Canal RetroArch inválido: {channel!r}")

    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)

    if channel == "stable":
        version = self.latest_stable_version()
        root, _ = self.buildroot("stable", version)
        archive_name = self.RETROARCH_ARCHIVE
        url = f"{root}{archive_name}"
        version_label = version
    else:
        archive_name, url = self.discover_nightly_archive()
        version_label = f"nightly-{archive_name[:10]}"

    temp_dir = Path(tempfile.mkdtemp(prefix="serm-retroarch-"))
    archive = temp_dir / archive_name
    extracted = temp_dir / "extracted"
    extracted.mkdir()

    try:
        if log:
            log(
                f"RETROARCH | canal={channel} | versão={version_label} | "
                f"arquivo={archive_name}"
            )
            log(f"DOWNLOAD | {url}")
        self._download_file(url, archive, progress, log)

        EmulatorManager._extract(archive, extracted, log)
        if not any(path.is_file() for path in extracted.rglob("retroarch.exe")):
            raise RuntimeError(
                "O pacote RetroArch foi baixado, mas a descompactação não produziu retroarch.exe."
            )
        EmulatorManager._merge(extracted, destination)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    executable = next(
        (path.resolve() for path in destination.rglob("retroarch.exe") if path.is_file()),
        None,
    )
    if executable is None:
        raise RuntimeError(
            f"Download/descompactação concluídos, mas retroarch.exe não foi encontrado em {destination}."
        )
    return DownloadResult("retroarch", version_label, executable, archive_name)


def _patch_gui() -> None:
    """Oculta o seletor visual de canal sem destruir os widgets Qt."""
    from PySide6.QtWidgets import QGroupBox

    from ..gui.emulator_home import EmulatorHomePage

    original_tab = EmulatorHomePage._retroarch_tab
    if getattr(original_tab, "_serm_distribution_channel_removed", False):
        return

    def retroarch_tab_without_channel(self):
        page = original_tab(self)
        for child in page.findChildren(QGroupBox):
            if child.title() == "Canal de distribuição":
                child.setVisible(False)
                child.setEnabled(False)
        return page

    retroarch_tab_without_channel._serm_distribution_channel_removed = True
    EmulatorHomePage._retroarch_tab = retroarch_tab_without_channel

    original_load = EmulatorHomePage._load_paths

    def load_paths_without_distribution_channel(self):
        paths = original_load(self)
        paths.pop("retroarch_channel", None)
        return paths

    EmulatorHomePage._load_paths = load_paths_without_distribution_channel


RetroArchManager.install_core = _install_core
RetroArchManager.install_frontend = _install_frontend
_patch_gui()
