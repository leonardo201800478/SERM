"""Functional emulator installation and RetroArch management for SERM V2."""

from __future__ import annotations

import binascii
import html
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)
USER_AGENT = "SERM/2.0"
VERSION_MARKER = ".serm-version"


@dataclass(frozen=True, slots=True)
class EmulatorStatus:
    """Estado local de um emulador suportado."""
    key: str
    label: str
    executable: Path | None
    root: Path | None
    version: str | None
    state: str


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Resultado de uma instalação/atualização."""
    emulator: str
    version: str
    executable: Path
    archive: str


@dataclass(frozen=True, slots=True)
class CoreInfo:
    """Core libretro publicado pelo Buildbot oficial."""
    filename: str
    core_name: str
    date: str = ""
    crc32: str = ""
    channel: str = "stable"


class EmulatorManager:
    """Descobre, instala e atualiza os emuladores suportados pelo SERM V2."""
    REPOSITORIES = {
        "mame": "mamedev/mame",
        "flycast": "flyinghead/flycast",
        "supermodel": "trzy/supermodel",
        "fbneo": "finalburnneo/FBNeo",
        "ymir": "ymir-emu/Ymir",
        "duckstation": "stenzek/duckstation",
        "pcsx2": "PCSX2/pcsx2",
        "ppsspp": "hrydgard/ppsspp",
        "dolphin": "dolphin-emu/dolphin",
        "xemu": "xemu-project/xemu",
        "azaharplus": "AzaharPlus/AzaharPlus",
        "rpcs3": "RPCS3/rpcs3-binaries-win",
        "xenia_canary": "xenia-canary/xenia-canary",
        "cemu": "cemu-project/Cemu",
        "melonds": "melonDS-emu/melonDS",
        "mgba": "mgba-emu/mgba",
        "shadps4": "shadps4-emu/shadPS4-qtlauncher",
        "ares": "ares-emulator/ares",
        "dosbox_staging": "dosbox-staging/dosbox-staging",
        "scummvm": "scummvm/scummvm",
        "mesence": "nesdev-org/MesenCE",
        "sameboy": "LIJI32/SameBoy",
        "ryujinx_nextendo": "NextendoNetwork/Ryujinx-Nextendo",
        "super_zsnes": "",
        "winuae": "",
        "vice": "",
        "xm6pro68k": "",
        "dosbox_x": "joncampbell123/dosbox-x",
        "stella": "stella-emu/stella",
        "altirra": "",
        "rmg": "Rosalie241/RMG",
        "bigpemu": "",
        "blastem": "",
        "bizhawk": "TASEmulators/BizHawk",
        "dosbox_pure": "schellingb/dosbox-pure-unleashed",
        "yabasanshiro": "",
    }
    LABELS = {
        "mame": "MAME",
        "flycast": "Flycast",
        "supermodel": "Supermodel",
        "fbneo": "FBNeo",
        "ymir": "Ymir · Sega Saturn",
        "duckstation": "DuckStation · PlayStation 1",
        "pcsx2": "PCSX2 · PlayStation 2",
        "ppsspp": "PPSSPP · PSP",
        "dolphin": "Dolphin · GameCube / Wii",
        "xemu": "Xemu · Xbox",
        "azaharplus": "AzaharPlus · Nintendo 3DS",
        "rpcs3": "RPCS3 · PlayStation 3",
        "xenia_canary": "Xenia Canary · Xbox 360",
        "cemu": "Cemu · Wii U",
        "melonds": "melonDS · Nintendo DS",
        "mgba": "mGBA · Game Boy Advance",
        "shadps4": "shadPS4 · PlayStation 4",
        "ares": "ares · Multi-sistema",
        "dosbox_staging": "DOSBox Staging · DOS",
        "scummvm": "ScummVM · Aventuras gráficas",
        "mesence": "MesenCE · Multi-sistema 8/16-bit",
        "sameboy": "SameBoy · Game Boy",
        "ryujinx_nextendo": "Ryujinx-Nextendo · Nintendo Switch",
        "super_zsnes": "SUPER ZSNES · Super Nintendo",
        "winuae": "WinUAE · Amiga",
        "vice": "VICE · Commodore",
        "xm6pro68k": "XM6 Pro-68k · Sharp X68000",
        "dosbox_x": "DOSBox-X · DOS / PC-98",
        "stella": "Stella · Atari 2600",
        "altirra": "Altirra · Atari 8-bit",
        "rmg": "RMG · Nintendo 64",
        "bigpemu": "BigPEmu · Atari Jaguar / Jaguar CD",
        "blastem": "BlastEm · Sega Genesis / Mega Drive + CD / 32X",
        "bizhawk": "BizHawk · Multi-sistema / TAS",
        "dosbox_pure": "DOSBox Pure Unleashed · DOS / Windows 9x",
        "yabasanshiro": "YabaSanshiro 2 · Sega Saturn",
    }
    EXECUTABLES = {
        "mame": "mame.exe",
        "flycast": "flycast.exe",
        "supermodel": "Supermodel.exe",
        "fbneo": "fbneo64.exe",
        "ymir": "ymir-sdl3.exe",
        "duckstation": "duckstation-qt-x64-ReleaseLTCG.exe",
        "pcsx2": "pcsx2-qt.exe",
        "ppsspp": "PPSSPPWindows64.exe",
        "dolphin": "Dolphin.exe",
        "xemu": "xemu.exe",
        "azaharplus": "azahar.exe",
        "rpcs3": "rpcs3.exe",
        "xenia_canary": "xenia_canary.exe",
        "cemu": "Cemu.exe",
        "melonds": "melonDS.exe",
        "mgba": "mGBA.exe",
        "shadps4": "shadPS4QtLauncher.exe",
        "ares": "ares.exe",
        "dosbox_staging": "dosbox.exe",
        "scummvm": "scummvm.exe",
        "mesence": "Mesen.exe",
        "sameboy": "sameboy.exe",
        "ryujinx_nextendo": "Ryujinx.exe",
        "super_zsnes": "SuperZSNES.exe",
        "winuae": "winuae64.exe",
        "vice": "x64sc.exe",
        "xm6pro68k": "XM6.exe",
        "dosbox_x": "dosbox-x.exe",
        "stella": "Stella.exe",
        "altirra": "Altirra64.exe",
        "rmg": "RMG.exe",
        "bigpemu": "BigPEmu.exe",
        "blastem": "blastem.exe",
        "bizhawk": "EmuHawk.exe",
        "dosbox_pure": "DOSBoxPure.exe",
        "yabasanshiro": "yabasanshiro.exe",
    }
    EXECUTABLE_ALIASES = {
        "ymir": ("ymir-sdl3.exe", "ymir.exe"),
        "duckstation": ("duckstation-qt-x64-ReleaseLTCG.exe", "duckstation-qt-x64-Release.exe"),
        "pcsx2": ("pcsx2-qt.exe",),
        "ppsspp": ("PPSSPPWindows64.exe", "PPSSPPWindows.exe"),
        "dolphin": ("Dolphin.exe",),
        "xemu": ("xemu.exe",),
        "azaharplus": ("azahar.exe", "azaharplus.exe"),
        "rpcs3": ("rpcs3.exe",),
        "xenia_canary": ("xenia_canary.exe", "xenia-canary.exe"),
        "cemu": ("Cemu.exe",),
        "melonds": ("melonDS.exe",),
        "mgba": ("mGBA.exe", "mgba.exe"),
        "shadps4": ("shadPS4QtLauncher.exe",),
        "ares": ("ares.exe",),
        "dosbox_staging": ("dosbox.exe", "dosbox-staging.exe"),
        "scummvm": ("scummvm.exe",),
        "mesence": ("Mesen.exe", "MesenCE.exe"),
        "sameboy": ("sameboy.exe", "SameBoy.exe"),
        "ryujinx_nextendo": ("Ryujinx.exe",),
        "super_zsnes": ("SuperZSNES.exe", "SuperZSnes.exe"),
        "winuae": ("winuae64.exe", "winuae.exe"),
        "vice": ("x64sc.exe", "x64.exe", "x128.exe", "xvic.exe", "xplus4.exe", "xpet.exe"),
        "xm6pro68k": ("XM6.exe", "XM6 Pro-68k.exe"),
        "dosbox_x": ("dosbox-x.exe",),
        "stella": ("Stella.exe", "stella.exe"),
        "altirra": ("Altirra64.exe", "Altirra.exe"),
        "rmg": ("RMG.exe",),
        "bigpemu": ("BigPEmu.exe",),
        "blastem": ("blastem.exe",),
        "bizhawk": ("EmuHawk.exe",),
        "dosbox_pure": ("DOSBoxPure.exe",),
        "yabasanshiro": ("yabasanshiro.exe", "YabaSanshiro.exe", "yabause.exe"),
    }
    _FBNEO_VERSION_CACHE: str | None = None
    _FBNEO_VERSION_LOOKED_UP = False

    def __init__(self, roots: dict[str, Path | None] | None = None) -> None:
        """Inicializa com as raízes persistidas."""
        self.roots = {k: Path(v).expanduser() if v else None for k, v in (roots or {}).items()}

    @staticmethod
    def find_7zip() -> Path | None:
        """Localiza 7-Zip no PATH ou em instalações padrão."""
        for name in ("7z.exe", "7zz.exe", "7za.exe"):
            found = shutil.which(name)
            if found:
                return Path(found)
        for path in (Path(r"C:\Program Files\7-Zip\7z.exe"), Path(r"C:\Program Files (x86)\7-Zip\7z.exe"), Path.home() / "AppData/Local/7-Zip/7z.exe"):
            if path.is_file():
                return path
        return None

    def discover(self) -> dict[str, EmulatorStatus]:
        """Detecta executável, raiz e versão dos emuladores."""
        result: dict[str, EmulatorStatus] = {}
        for key, label in self.LABELS.items():
            root = self.roots.get(key)
            executable = self._find_executable(key, root)
            if executable:
                root = executable.parent
            version = self._read_version(key, root, executable)
            state = "ready" if executable else ("configured" if root else "not_found")
            result[key] = EmulatorStatus(key, label, executable, root, version, state)
        return result

    def install(self, key: str, destination: Path, *, progress=None, install_progress=None, log=None) -> DownloadResult:
        """Baixa e instala o pacote Windows x64 oficial."""
        key = key.casefold()
        if key not in self.REPOSITORIES:
            raise ValueError(f"Emulador não suportado: {key}")
        destination = Path(destination).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        if key == "flycast":
            return self._install_latest_flycast_master(destination, progress=progress, install_progress=install_progress, log=log)
        if key in {"ymir", "duckstation", "pcsx2", "ppsspp", "dolphin", "xemu", "azaharplus", "rpcs3", "xenia_canary", "cemu", "melonds", "mgba", "shadps4", "ares", "dosbox_staging", "scummvm", "mesence", "sameboy", "ryujinx_nextendo", "super_zsnes", "winuae", "vice", "xm6pro68k", "dosbox_x", "stella", "altirra", "rmg", "bigpemu", "blastem", "bizhawk", "dosbox_pure", "yabasanshiro"}:
            return self._install_latest_emulator_build(key, destination, progress=progress, install_progress=install_progress, log=log)
        release = self._release(key)
        assets_value = release.get("assets")
        assets: list[object] = assets_value if isinstance(assets_value, list) else []
        asset = self._select_asset(key, assets)
        if not asset:
            raise RuntimeError(f"Nenhum pacote Windows x64 encontrado para {key}.")
        version = str(release.get("tag_name") or release.get("name") or "unknown")
        with tempfile.TemporaryDirectory(prefix="serm-emu-") as temp_name:
            temp = Path(temp_name)
            archive = temp / str(asset["name"])
            self._download(str(asset["browser_download_url"]), archive, int(asset.get("size") or 0), progress, log)
            extracted = temp / "extracted"
            extracted.mkdir()
            self._extract(archive, extracted, log, install_progress=install_progress)
            if key == "fbneo":
                version = (
                    self._read_fbneo_changelog_version(extracted)
                    or self._fetch_fbneo_version()
                    or version
                )
            self._merge(extracted, destination, install_progress=install_progress, start=40)
        executable = self._find_executable(key, destination)
        if executable is None:
            raise RuntimeError(f"Instalação concluída, mas {self.EXECUTABLES[key]} não foi encontrado em {destination}.")
        self._enable_portable_mode(key, executable, log=log)
        return DownloadResult(key, version, executable, str(asset["name"]))

    def _install_latest_emulator_build(self, key: str, destination: Path, *, progress=None, install_progress=None, log=None) -> DownloadResult:
        """Resolve e instala o pacote Windows x64 de desenvolvimento mais recente."""
        if key == "ymir":
            release = self._release_by_tag("ymir-emu/Ymir", "latest-nightly")
            asset = self._named_asset(release, re.compile(r"^ymir-windows-x86_64-AVX2-.*\.zip$", re.I))
            version = asset["name"].removeprefix("ymir-windows-x86_64-AVX2-").removesuffix(".zip")
        elif key == "duckstation":
            release = self._release_by_tag("stenzek/duckstation", "latest")
            asset = self._named_asset(release, re.compile(r"^duckstation-windows-x64-release\.zip$", re.I))
            version = self._release_version(release, "latest rolling")
        elif key == "pcsx2":
            _, asset = self._latest_github_asset(
                "PCSX2/pcsx2",
                re.compile(r"^pcsx2-v(\d+(?:\.\d+)+)-windows-x64-Qt\.7z$", re.I),
            )
            version = asset["name"].removeprefix("pcsx2-").removesuffix("-windows-x64-Qt.7z")
        elif key == "ppsspp":
            try:
                url, archive_name = self._latest_ppsspp_build()
                asset = {"name": archive_name, "browser_download_url": url, "size": 0}
                version = archive_name.removeprefix("ppsspp_win_").removesuffix(".zip")
            except (OSError, URLError, RuntimeError) as exc:
                pattern = re.compile(r"^PPSSPP-v\d+(?:\.\d+)+-Windows-x64\.zip$", re.I)
                _, asset = self._latest_github_asset("hrydgard/ppsspp", pattern)
                version = asset["name"].removeprefix("PPSSPP-v").removesuffix("-Windows-x64.zip")
                if log:
                    log(f"PPSSPP | build de desenvolvimento indisponível; usando release estável {version} ({exc})")
        elif key == "dolphin":
            url, archive_name = self._latest_dolphin_build()
            asset = {"name": archive_name, "browser_download_url": url, "size": 0}
            version = archive_name.removeprefix("dolphin-").removesuffix("-x64.7z")
        elif key == "xemu":
            release = self._release_by_tag("xemu-project/xemu", "pre-release")
            asset = self._named_asset(release, re.compile(r"^xemu-(?!.*-dbg-).+-windows-x86_64\.zip$", re.I))
            version = asset["name"].removeprefix("xemu-").removesuffix("-windows-x86_64.zip")
        elif key == "azaharplus":
            _, asset = self._latest_github_asset(
                "AzaharPlus/AzaharPlus",
                re.compile(r"^azaharplus-.+-windows\.zip$", re.I),
            )
            version = asset["name"].removeprefix("azaharplus-").removesuffix("-windows.zip")
        elif key == "rpcs3":
            # This repository publishes thousands of rolling builds. Use GitHub's
            # designated latest release directly; scanning page one and sorting
            # the candidates by release date can miss newer build tags.
            release = self._json(
                "https://api.github.com/repos/RPCS3/rpcs3-binaries-win/releases/latest"
            )
            asset = self._named_asset(
                release,
                re.compile(r"^rpcs3-v\d+(?:\.\d+)+-\d+-[0-9a-f]+_win64(?:_msvc)?\.7z$", re.I),
            )
            version = (
                asset["name"].removeprefix("rpcs3-")
                .removesuffix("_win64_msvc.7z")
                .removesuffix("_win64.7z")
            )
        elif key == "cemu":
            release = self._release(key)
            asset = self._named_asset(release, re.compile(r"^cemu-.+-windows-x64\.zip$", re.I))
            version = self._release_version(release, "latest")
        elif key == "melonds":
            release = self._release(key)
            asset = self._named_asset(release, re.compile(r"^melonDS-[\d.]+-windows-x86_64\.zip$", re.I))
            version = self._release_version(release, "latest")
        elif key == "mgba":
            release = self._release(key)
            asset = self._named_asset(release, re.compile(r"^mGBA-[\d.]+-win64\.(?:7z|zip)$", re.I))
            version = self._release_version(release, "latest")
        elif key == "shadps4":
            url, archive_name, version = self._latest_shadps4_launcher()
            asset = {"name": archive_name, "browser_download_url": url, "size": 0}
        elif key == "ares":
            release = self._release(key)
            asset = self._named_asset(release, re.compile(r"^ares-windows-x64\.zip$", re.I))
            version = self._release_version(release, "latest")
        elif key == "dosbox_staging":
            release = self._release(key)
            asset = self._named_asset(release, re.compile(r"^dosbox-staging-windows-x64-v[\w.-]+\.zip$", re.I))
            version = self._release_version(release, "latest")
        elif key == "scummvm":
            url, archive_name, version = self._latest_scummvm_build()
            asset = {"name": archive_name, "browser_download_url": url, "size": 0}
        elif key == "mesence":
            release = self._release(key)
            asset = self._named_asset(release, re.compile(r"^Mesen_[\d.]+_Windows\.zip$", re.I))
            version = self._release_version(release, "latest")
        elif key == "sameboy":
            url, archive_name, version = self._latest_sameboy_build()
            asset = {"name": archive_name, "browser_download_url": url, "size": 0}
        elif key == "ryujinx_nextendo":
            release = self._release(key)
            asset = self._named_asset(
                release,
                re.compile(r"^(?:Nextendo|Ryujinx-Nextendo).*\.(?:zip|7z)$", re.I),
            )
            version = self._release_version(release, "latest")
        elif key == "super_zsnes":
            url, archive_name, version = self._latest_super_zsnes_build()
            asset = {"name": archive_name, "browser_download_url": url, "size": 0}
        elif key == "winuae":
            url, archive_name, version = self._latest_winuae_build()
            asset = {"name": archive_name, "browser_download_url": url, "size": 0}
        elif key == "vice":
            url, archive_name, version = self._latest_vice_build()
            asset = {"name": archive_name, "browser_download_url": url, "size": 0}
        elif key == "xm6pro68k":
            url, archive_name, version = self._latest_xm6pro68k_build()
            asset = {"name": archive_name, "browser_download_url": url, "size": 0}
        elif key == "dosbox_x":
            release = self._release(key)
            asset = self._named_asset(
                release,
                re.compile(r"^dosbox-x-vsbuild-win64-\d{4}\.\d{2}\.\d{2}-portable\.zip$", re.I),
            )
            version = self._release_version(release, "latest")
        elif key == "stella":
            url, archive_name, version = self._latest_stella_build()
            asset = {"name": archive_name, "browser_download_url": url, "size": 0}
        elif key == "altirra":
            url, archive_name, version = self._latest_altirra_build()
            asset = {"name": archive_name, "browser_download_url": url, "size": 0}
        elif key == "rmg":
            release = self._release(key)
            asset = self._named_asset(release, re.compile(r"^RMG-Portable-Windows64-v[\d.]+\.zip$", re.I))
            version = self._release_version(release, "latest")
        elif key == "bigpemu":
            url, archive_name, version = self._latest_bigpemu_build()
            asset = {"name": archive_name, "browser_download_url": url, "size": 0}
        elif key == "blastem":
            url, archive_name, version = self._latest_blastem_build()
            asset = {"name": archive_name, "browser_download_url": url, "size": 0}
        elif key == "bizhawk":
            release = self._release(key)
            asset = self._named_asset(release, re.compile(r"^BizHawk-.+-win-x64\.zip$", re.I))
            version = self._release_version(release, "latest")
        elif key == "dosbox_pure":
            release = self._release(key)
            asset = self._named_asset(
                release,
                re.compile(r"^dosbox_pure_unleashed-windows-64bit-[\w.-]+\.zip$", re.I),
            )
            version = self._release_version(release, "latest")
        elif key == "yabasanshiro":
            url, archive_name, version = self._latest_yabasanshiro_build()
            asset = {"name": archive_name, "browser_download_url": url, "size": 0}
        else:
            release, asset = self._latest_github_asset(
                "xenia-canary/xenia-canary",
                re.compile(r"^xenia_canary_windows\.7z$", re.I),
            )
            version = self._release_version(release, "latest Canary")

        archive_name = str(asset["name"])
        url = str(asset["browser_download_url"])
        size = int(asset.get("size") or 0)
        with tempfile.TemporaryDirectory(prefix=f"serm-{key}-") as temp_name:
            temp = Path(temp_name)
            archive = temp / archive_name
            extracted = temp / "extracted"
            extracted.mkdir()
            if log:
                log(f"{key.upper()} | versão={version} | arquivo={archive_name}")
                log(f"DOWNLOAD | {url}")
            self._download(url, archive, size, progress, log)
            self._extract(archive, extracted, log, install_progress=install_progress)
            executable = self._find_executable(key, extracted)
            # The Nextendo package includes a portable data directory alongside
            # the executable; preserve the complete package tree on installation.
            install_root = (
                self._normalize_archive_root(extracted)
                if key == "ryujinx_nextendo"
                else executable.parent if executable else self._normalize_archive_root(extracted)
            )
            self._merge(install_root, destination, install_progress=install_progress, start=40)
        executable = self._find_executable(key, destination)
        if executable is None:
            expected = ", ".join(self.EXECUTABLE_ALIASES.get(key, (self.EXECUTABLES[key],)))
            raise RuntimeError(f"Pacote {key} extraído, mas nenhum executável esperado foi encontrado ({expected}).")
        self._enable_portable_mode(key, executable, log=log)
        return DownloadResult(key, version, executable, archive_name)

    @staticmethod
    def _enable_portable_mode(key: str, executable: Path, *, log=None) -> None:
        """Enable vendor-supported local data storage where a marker is required."""
        install_dir = executable.parent
        marker_name = {
            "duckstation": "portable.txt",
            "pcsx2": "portable.txt",
            "dolphin": "portable.txt",
        }.get(key)
        if marker_name:
            marker = install_dir / marker_name
            if not marker.exists():
                marker.touch()
                if log:
                    log(f"{key.upper()} | modo portátil ativado ({marker_name})")
            return

        if key == "cemu":
            portable_dir = install_dir / "portable"
            if not portable_dir.exists():
                portable_dir.mkdir()
                if log:
                    log("CEMU | modo portátil ativado (pasta portable)")

    @classmethod
    def _latest_bigpemu_build(cls) -> tuple[str, str, str]:
        page_url = "https://www.richwhitehouse.com/jaguar/index.php?content=download"
        page = cls._download_text(page_url)
        links = cls._extract_links(page, page_url)
        for url in links:
            filename = Path(urlparse(url).path).name
            match = re.fullmatch(r"BigPEmu_v(\d+)\.zip", filename, re.I)
            if match:
                version = re.search(r"Current Version:\s*([\d.]+)", html.unescape(page), re.I)
                return url, filename, version.group(1) if version else match.group(1)
        raise RuntimeError("A página oficial do BigPEmu não indicou o ZIP Windows x64.")

    @classmethod
    def _latest_blastem_build(cls) -> tuple[str, str, str]:
        pattern = re.compile(r"blastem-win64-(\d+(?:\.\d+)+)\.zip$", re.I)
        for page_url in (
            "https://www.rhope.retrodev.com/blastem/downloads.html",
            "https://www.retrodev.com/blastem/downloads.html",
        ):
            try:
                page = cls._download_text(page_url)
            except (OSError, URLError):
                continue
            for url in cls._extract_links(page, page_url):
                filename = Path(urlparse(url).path).name
                match = pattern.fullmatch(filename)
                if match:
                    return url, filename, match.group(1)
        raise RuntimeError("A página oficial do BlastEm não indicou o pacote Windows x64 estável.")

    @classmethod
    def _latest_yabasanshiro_build(cls) -> tuple[str, str, str]:
        return cls._latest_emufrance_download(
            query="YabaSanshiro 2",
            post_slug=re.compile(r"/news/\d+-[^\"']*yabasanshiro-2[^\"']*/?", re.I),
            release_version=re.compile(r"YabaSanshiro\s+2\s+v(\d+(?:\.\d+)+)", re.I),
            download_label=re.compile(r"Télécharger\s+YabaSanshiro\s+2\s+v", re.I),
            filename=lambda version: f"YabaSanshiro-2-v{version}.zip",
        )

    @classmethod
    def _latest_xm6pro68k_build(cls) -> tuple[str, str, str]:
        return cls._latest_emufrance_download(
            query="XM6 Pro-68k",
            post_slug=re.compile(r"/news/\d+-[^\"']*xm6-pro-68k-release-[^\"']*/?", re.I),
            release_version=re.compile(r"XM6\s+Pro-68k\s+Release\s*(\d+)\s*\((\d{6})\)", re.I),
            download_label=re.compile(r"Télécharger\s+XM6\s+Pro-68k\s+Release\s*\d+", re.I),
            filename=lambda version: f"XM6-Pro-68k-{version.replace(' ', '-')}.zip",
        )

    @classmethod
    def _latest_emufrance_download(
        cls,
        *,
        query: str,
        post_slug: re.Pattern[str],
        release_version: re.Pattern[str],
        download_label: re.Pattern[str],
        filename: Callable[[str], str],
    ) -> tuple[str, str, str]:
        """Find the newest matching Emu-France news post and its download link."""
        candidates: set[str] = set()
        listing_urls = [
            f"https://www.emu-france.com/?{urlencode({'s': query})}",
            "https://www.emu-france.com/",
        ]
        # Emu-France only exposes a small, recent window on its homepage and
        # its WordPress search can omit older posts. Walk the chronological
        # archive until the first page containing this emulator; those posts
        # are newer than any matching posts on later archive pages.
        archive_page = 2
        archive_match_found = False
        while archive_page <= 12 and not archive_match_found:
            listing_urls.append(f"https://www.emu-france.com/?paged={archive_page}")
            listing_url = listing_urls[-1]
            try:
                listing = cls._download_text(listing_url)
            except (OSError, URLError):
                archive_page += 1
                continue
            page_candidates = {
                url for url in cls._extract_links(listing, listing_url)
                if post_slug.search(urlparse(url).path)
            }
            candidates.update(page_candidates)
            archive_match_found = bool(page_candidates)
            archive_page += 1

        # Search results and the current homepage may contain a newer post
        # than the archive scan. Include them before reading the post pages.
        for listing_url in listing_urls[:2]:
            try:
                listing = cls._download_text(listing_url)
            except (OSError, URLError):
                continue
            candidates.update(
                url for url in cls._extract_links(listing, listing_url)
                if post_slug.search(urlparse(url).path)
            )

        releases: list[tuple[tuple[int, ...], str, str, str]] = []
        for post_url in candidates:
            try:
                post = html.unescape(cls._download_text(post_url))
            except (OSError, URLError):
                continue
            match = release_version.search(post)
            if not match:
                continue
            version = (
                f"Release {match.group(1)} ({match.group(2)})"
                if query == "XM6 Pro-68k"
                else " ".join(match.groups())
            )
            version_key = tuple(int(part) for part in re.findall(r"\d+", version))
            for anchor in re.finditer(r"<a\b([^>]*)>(.*?)</a\s*>", post, re.I | re.S):
                label = re.sub(r"<[^>]+>", " ", anchor.group(2))
                label = re.sub(r"\s+", " ", html.unescape(label)).strip()
                if not download_label.search(label):
                    continue
                href = re.search(r"\bhref\s*=\s*['\"]([^'\"]+)['\"]", anchor.group(1), re.I)
                if not href:
                    continue
                url = urljoin(post_url, href.group(1))
                if "wpfb_dl=" not in urlparse(url).query:
                    continue
                releases.append((version_key, url, filename(version), version))
        if not releases:
            raise RuntimeError(f"Emu-France não informou uma versão e download compatíveis para {query}.")
        _key, url, archive_name, version = max(releases, key=lambda item: item[0])
        return url, archive_name, version

    @classmethod
    def _latest_scummvm_build(cls) -> tuple[str, str, str]:
        page = cls._download_text("https://www.scummvm.org/downloads/")
        for url in cls._extract_links(page, "https://www.scummvm.org/downloads/"):
            filename = Path(urlparse(url).path).name
            match = re.fullmatch(r"scummvm-(\d{4}\.\d+\.\d+)-(?:win64|win32-x86_64)\.zip", filename, re.I)
            if match:
                return url, filename, match.group(1)
        raise RuntimeError("A página oficial do ScummVM não indicou um ZIP Windows 64-bit.")

    @classmethod
    def _latest_sameboy_build(cls) -> tuple[str, str, str]:
        release = cls._json("https://api.github.com/repos/LIJI32/SameBoy/releases/latest")
        asset = cls._named_asset(release, re.compile(r"^sameboy_winsdl_v\d+(?:\.\d+)+\.zip$", re.I))
        match = re.search(r"v(\d+(?:\.\d+)+)", str(asset["name"]), re.I)
        return str(asset["browser_download_url"]), str(asset["name"]), match.group(1) if match else cls._release_version(release, "latest")

    @classmethod
    def _latest_stella_build(cls) -> tuple[str, str, str]:
        page_url = "https://stella-emu.github.io/downloads.html"
        page = cls._download_text(page_url)
        for url in cls._extract_links(page, page_url):
            filename = Path(urlparse(url).path).name
            match = re.fullmatch(r"Stella-(\d+(?:\.\d+)+[a-z]?)-windows\.zip", filename, re.I)
            if match:
                version = re.sub(r"[a-z]$", "", match.group(1), flags=re.I)
                return url, filename, version
        raise RuntimeError("A página oficial do Stella não indicou um pacote Windows 64-bit.")

    @classmethod
    def _latest_shadps4_launcher(cls) -> tuple[str, str, str]:
        releases = cls._github_json(
            "https://api.github.com/repos/shadps4-emu/shadps4-qtlauncher/releases?per_page=100"
        )
        if not isinstance(releases, list):
            raise RuntimeError("A API oficial do shadPS4 QtLauncher retornou uma lista inválida de releases.")

        candidates: list[tuple[str, str, str]] = []
        for release in releases:
            if not isinstance(release, dict):
                continue
            assets = release.get("assets")
            for asset in assets if isinstance(assets, list) else ():
                if not isinstance(asset, dict) or not asset.get("browser_download_url"):
                    continue
                filename = str(asset.get("name", ""))
                match = re.fullmatch(
                    r"shadPS4QtLauncher-win64-qt-(\d{4}-\d{2}-\d{2})-([0-9a-f]+)\.zip",
                    filename,
                    re.I,
                )
                if match:
                    candidates.append((
                        str(release.get("published_at", "")),
                        str(asset["browser_download_url"]),
                        filename,
                    ))

        if not candidates:
            raise RuntimeError("A API oficial do shadPS4 não indicou um pacote QtLauncher Windows x64.")
        published, url, filename = max(candidates, key=lambda candidate: candidate[0])
        date_hash = re.search(r"-(\d{4}-\d{2}-\d{2})-([0-9a-f]+)\.zip$", filename, re.I)
        version = f"{date_hash.group(1)}-{date_hash.group(2)}" if date_hash else published[:10]
        return url, filename, version

    @classmethod
    def _latest_super_zsnes_build(cls) -> tuple[str, str, str]:
        page = cls._download_text("https://www.zsnes.com/")
        for url in cls._extract_links(page, "https://www.zsnes.com/"):
            filename = Path(urlparse(url).path).name
            match = re.fullmatch(r"SuperZSNES_v([\w.-]+)\.zip", filename, re.I)
            if match:
                return url, filename, match.group(1)
        raise RuntimeError("O site do SUPER ZSNES não indicou o pacote Windows ZIP.")

    @classmethod
    def _latest_winuae_build(cls) -> tuple[str, str, str]:
        page_url = "https://www.winuae.net/download/"
        try:
            page = cls._download_text(page_url)
            links = cls._extract_links(page, page_url)
        except (OSError, URLError):
            links = ()
        candidates = []
        for url in links:
            filename = Path(urlparse(url).path).name
            match = re.fullmatch(r"(?:Install)?WinUAE(\d+)_x64\.(zip|msi)", filename, re.I)
            if match:
                candidates.append((match.group(1), match.group(2), url, filename))
        if not candidates:
            # Current stable 64-bit ZIP linked from the official download page.
            return (
                "https://download.abime.net/winuae/releases/WinUAE6030_x64.zip",
                "WinUAE6030_x64.zip",
                "6.0.3",
            )
        number, extension = max(
            ((item[0], item[1]) for item in candidates),
            key=lambda candidate: (int(candidate[0]), candidate[1].casefold() == "zip"),
        )
        url, filename = next((item[2], item[3]) for item in candidates if item[:2] == (number, extension))
        version = f"{number[0]}.{int(number[1:-2])}.{int(number[-2:]) // 10}"
        return url, filename, version

    @classmethod
    def _latest_vice_build(cls) -> tuple[str, str, str]:
        version = "3.10"
        filename = f"GTK3VICE-{version}-win64.zip"
        url = f"https://downloads.sourceforge.net/project/vice-emu/releases/binaries/windows/{filename}"
        return url, filename, version

    @classmethod
    def _latest_altirra_build(cls) -> tuple[str, str, str]:
        page_url = "https://www.virtualdub.org/beta/"
        try:
            page = cls._download_text(page_url)
        except (OSError, URLError) as exc:
            logger.warning("NÃ£o foi possÃ­vel consultar as builds beta do Altirra: %s", exc)
            page = ""
        candidates = re.findall(r"Altirra-(\d+(?:\.\d+)+)-test(\d+)\.zip", html.unescape(page), re.I)
        if not candidates:
            logger.warning("Página beta do Altirra sem builds; usando o último pacote estável conhecido.")
            return (
                "https://www.virtualdub.org/downloads/Altirra-4.30.zip",
                "Altirra-4.30.zip",
                "4.30 stable",
            )
        version, build = max(
            candidates,
            key=lambda item: (tuple(int(part) for part in item[0].split(".")), int(item[1])),
        )
        filename = f"Altirra-{version}-test{build}.zip"
        return urljoin(page_url, filename), filename, f"{version} test {build}"

    @classmethod
    def _release_by_tag(cls, repository: str, tag: str) -> dict[str, Any]:
        value = cls._github_json(f"https://api.github.com/repos/{repository}/releases/tags/{tag}")
        if not isinstance(value, dict):
            raise RuntimeError(f"Resposta inesperada ao consultar {repository}@{tag}.")
        return value

    @classmethod
    def _latest_github_asset(cls, repository: str, pattern: re.Pattern[str]) -> tuple[dict[str, Any], dict[str, Any]]:
        releases = cls._github_json(f"https://api.github.com/repos/{repository}/releases?per_page=100")
        if not isinstance(releases, list):
            raise RuntimeError(f"Lista de releases inesperada para {repository}.")
        candidates: list[tuple[str, str, dict[str, Any], dict[str, Any]]] = []
        for release in releases:
            if not isinstance(release, dict):
                continue
            assets = release.get("assets")
            for asset in assets if isinstance(assets, list) else ():
                if not isinstance(asset, dict) or not asset.get("browser_download_url"):
                    continue
                if pattern.fullmatch(str(asset.get("name", ""))):
                    candidates.append((str(release.get("published_at") or ""), str(release.get("tag_name") or ""), release, asset))
        if not candidates:
            raise RuntimeError(f"Nenhum asset Windows x64 correspondente foi publicado por {repository}.")
        _, _, release, asset = max(candidates, key=lambda candidate: (candidate[0], candidate[1]))
        return release, asset

    @classmethod
    def _named_asset(cls, release: dict[str, Any], pattern: re.Pattern[str]) -> dict[str, Any]:
        assets = release.get("assets")
        asset = next(
            (
                value for value in assets if isinstance(value, dict)
                and value.get("browser_download_url")
                and pattern.fullmatch(str(value.get("name", "")))
            ),
            None,
        ) if isinstance(assets, list) else None
        if asset is None:
            raise RuntimeError(f"Asset esperado não encontrado no release {release.get('tag_name')!r}.")
        return asset

    @staticmethod
    def _release_version(release: dict[str, Any], fallback: str) -> str:
        tag = str(release.get("tag_name") or "")
        published = str(release.get("published_at") or "")[:10]
        return f"{tag} ({published})" if published else tag or fallback

    @classmethod
    def _latest_ppsspp_build(cls) -> tuple[str, str]:
        page = cls._download_text("https://www.ppsspp.org/devbuilds/")
        links = cls._extract_links(page, "https://www.ppsspp.org/devbuilds/")
        pattern = re.compile(r"ppsspp_win_(v[\w.-]+)\.zip$", re.I)
        for url in links:
            filename = Path(urlparse(url).path).name
            if pattern.fullmatch(filename):
                return url, filename
        text = html.unescape(page)
        match = re.search(r"(ppsspp_win_(v[\w.-]+)\.zip)", text, re.I)
        if match:
            filename = match.group(1)
            version = match.group(2)
            return f"https://builds.ppsspp.org/builds/{version}/{filename}", filename
        # The development page can be delivered without its JavaScript-rendered
        # build list. Its indexed/plain-text representation still contains the
        # Windows package in most responses; tolerate links with quoted markup
        # and URL escaping before giving up.
        normalized = text.replace("\\/", "/").replace("&amp;", "&")
        match = re.search(r"ppsspp_win_(v[\w.-]+\.zip)", normalized, re.I)
        if match:
            filename = match.group(0)
            version = match.group(1).removesuffix(".zip")
            return f"https://builds.ppsspp.org/builds/{version}/{filename}", filename
        raise RuntimeError("A página oficial do PPSSPP não informou o ZIP Windows x64; a lista de builds pode estar temporariamente indisponível.")

    @classmethod
    def _latest_dolphin_build(cls) -> tuple[str, str]:
        page_url = "https://br.dolphin-emu.org/download/"
        pattern = re.compile(r"dolphin-master-\d+-\d+-x64\.7z$", re.I)
        errors: list[str] = []
        for candidate_page in (page_url, "https://dolphin-emu.org/download/"):
            try:
                page = cls._download_text(candidate_page)
            except (OSError, URLError) as exc:
                errors.append(str(exc))
                continue
            for url in cls._extract_links(page, candidate_page):
                filename = Path(urlparse(url).path).name
                if pattern.fullmatch(filename):
                    return url, filename
            text = html.unescape(page)
            match = re.search(r"https?://dl\.dolphin-emu\.org/builds/[0-9a-f]{2}/[0-9a-f]{2}/(dolphin-master-\d+-\d+-x64\.7z)", text, re.I)
            if match:
                return match.group(0), match.group(1)
        detail = f" Detalhe: {'; '.join(errors)}" if errors else ""
        raise RuntimeError(f"A página oficial do Dolphin não indicou um pacote de desenvolvimento Windows x64.{detail}")

    @staticmethod
    def _extract_links(page: str, base_url: str) -> tuple[str, ...]:
        return tuple(
            urljoin(base_url, html.unescape(value))
            for value in re.findall(r"href\s*=\s*['\"]([^'\"]+)['\"]", page, re.I)
        )

    @staticmethod
    def _download_text(url: str) -> str:
        request = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
        })
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _github_json(url: str) -> Any:
        request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT})
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    @classmethod
    def _install_latest_flycast_master(cls, destination: Path, *, progress=None, install_progress=None, log=None) -> DownloadResult:
        """Instala o build MASTER Windows x64 mais recente publicado no feed oficial."""
        endpoint = "https://flycast-builds.s3.fr-par.scw.cloud/"
        prefix = "win/heads/master-"
        marker = None
        candidates: list[tuple[str, str, str, int]] = []
        while True:
            params = {"list-type": "2", "prefix": prefix}
            if marker:
                params["continuation-token"] = marker
            query = "?" + urlencode(params)
            request = Request(endpoint + query, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=30) as response:
                listing = ET.fromstring(response.read())
            for item in listing.findall("{*}Contents"):
                key = item.findtext("{*}Key", "")
                filename = key.rsplit("/", 1)[-1]
                lowered = filename.casefold()
                # The official workflow places x64 packages under win/ and names
                # the archive simply flycast.zip, so architecture is encoded by
                # the object prefix rather than the filename.
                if lowered.endswith(".zip"):
                    candidates.append((item.findtext("{*}LastModified", ""), key, filename, int(item.findtext("{*}Size", "0") or 0)))
            if listing.findtext("{*}IsTruncated", "false").casefold() != "true":
                break
            marker = listing.findtext("{*}NextContinuationToken")
            if not marker:
                break
        if not candidates:
            raise RuntimeError("O feed oficial do Flycast não publicou um arquivo ZIP no prefixo win/heads/master.")
        modified, key, archive_name, size = max(candidates, key=lambda value: value[0])
        url = endpoint + key
        build_id = key.split("/")[-2].rsplit("-", 1)[-1][:7]
        version = f"MASTER {modified[:10]} ({build_id})"
        with tempfile.TemporaryDirectory(prefix="serm-flycast-") as temp_name:
            temp = Path(temp_name)
            archive = temp / archive_name
            extracted = temp / "extracted"
            extracted.mkdir()
            if log:
                log(f"FLYCAST | canal=MASTER | plataforma=Windows x64 | versao={version} | arquivo={archive_name}")
                log(f"DOWNLOAD | {url}")
            cls._download(url, archive, size, progress, log)
            cls._extract(archive, extracted, log, install_progress=install_progress)
            cls._merge(cls._normalize_archive_root(extracted), destination, install_progress=install_progress, start=40)
        executable = next((path.resolve() for path in (destination / "flycast.exe", destination / "bin" / "flycast.exe") if path.is_file()), None)
        if executable is None:
            raise RuntimeError(f"Build MASTER baixado, mas flycast.exe não foi encontrado em {destination}.")
        return DownloadResult("flycast", version, executable, archive_name)

    @staticmethod
    def _normalize_archive_root(source: Path) -> Path:
        entries = list(source.iterdir())
        return entries[0] if len(entries) == 1 and entries[0].is_dir() else source

    def _release(self, key: str) -> dict[str, Any]:
        """Consulta o release oficial do GitHub."""
        return self._json(f"https://api.github.com/repos/{self.REPOSITORIES[key]}/releases/latest")

    @staticmethod
    def _json(url: str) -> dict[str, Any]:
        """Obtém um objeto JSON público."""
        request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT})
        with urlopen(request, timeout=30) as response:
            value = json.loads(response.read().decode("utf-8"))
        if not isinstance(value, dict):
            raise RuntimeError("Resposta JSON inesperada.")
        return value

    @classmethod
    def _select_asset(cls, key: str, assets: list[object]) -> dict[str, Any] | None:
        """Seleciona o melhor pacote Windows 64-bit."""
        candidates: list[tuple[int, dict[str, Any]]] = []
        for raw in assets:
            if not isinstance(raw, dict) or not raw.get("browser_download_url"):
                continue
            score = cls._asset_score(key, str(raw.get("name", "")).casefold())
            if score >= 70:
                candidates.append((score, raw))
        candidates.sort(key=lambda item: (item[0], int(item[1].get("size") or 0)), reverse=True)
        return candidates[0][1] if candidates else None

    @staticmethod
    def _asset_score(key: str, name: str) -> int:
        """Pontua pacotes Windows x64."""
        score = 0
        if any(t in name for t in ("windows", "win64", "win-x64", "win_x64", "mingw", "x86_64")):
            score += 50
        if any(t in name for t in ("x64", "x86_64", "amd64", "64bit", "64-bit")):
            score += 40
        if any(t in name for t in ("linux", "macos", "osx", "android", "ios", "arm64", "aarch64", "win32", "i386", "source", "src")):
            score -= 100
        if name.endswith(".zip"):
            score += 20
        elif name.endswith((".7z", ".7zip")):
            score += 10
        elif name.endswith(".exe"):
            score += 15
        if key == "mame" and re.search(r"_x64\.exe$", name):
            score += 140
        if key == "flycast" and "flycast-win64" in name:
            score += 150
        if key == "supermodel" and "supermodel" in name and "win" in name:
            score += 140
        if key == "fbneo" and name == "windows-x86_64.zip":
            score += 220
        return score

    @staticmethod
    def _download(url: str, target: Path, expected: int, progress=None, log=None) -> None:
        """Baixa um arquivo com progresso."""
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
        received = 0
        with urlopen(request, timeout=120) as response, target.open("wb") as output:
            total = int(response.headers.get("Content-Length") or expected or 0)
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                received += len(chunk)
                if progress:
                    progress(received, total)
        if received <= 0:
            raise RuntimeError("Download retornou zero bytes.")
        if log:
            log(f"DOWNLOAD | recebido={received:,} bytes | esperado={total:,} bytes")

    @classmethod
    def _extract(cls, archive: Path, destination: Path, log=None, *, install_progress=None) -> None:
        """Extrai ZIP internamente ou usa 7-Zip."""
        if install_progress:
            install_progress(0, 0)
        if archive.suffix.casefold() == ".zip" or zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(destination)
            if install_progress:
                install_progress(40, 100)
            return
        seven_zip = cls.find_7zip()
        if seven_zip is None:
            raise RuntimeError("7z.exe não foi encontrado.")
        result = subprocess.run([str(seven_zip), "x", "-y", f"-o{destination}", str(archive)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=300, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"7-Zip falhou ({result.returncode}): {(result.stdout or '').strip()}")
        if install_progress:
            install_progress(40, 100)

    @staticmethod
    def _merge(source: Path, destination: Path, *, install_progress=None, start: int = 0) -> None:
        """Mescla a árvore extraída no diretório de instalação."""
        files = [path for path in source.rglob("*") if path.is_file()]
        directories = [path for path in source.rglob("*") if path.is_dir()]
        for directory in directories:
            (destination / directory.relative_to(source)).mkdir(parents=True, exist_ok=True)
        if not files:
            if install_progress:
                install_progress(100, 100)
            return
        for index, path in enumerate(files, start=1):
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            if install_progress:
                install_progress(start + int(index * (100 - start) / len(files)), 100)

    def _find_executable(self, key: str, root: Path | None) -> Path | None:
        """Procura somente o executável oficial esperado."""
        names = self.EXECUTABLE_ALIASES.get(key, (self.EXECUTABLES[key],))
        candidates: list[Path] = []
        if root:
            for name in names:
                candidates.extend((root / name, root / "bin" / name))
            if key in self.EXECUTABLE_ALIASES:
                candidates.extend(path for name in names for path in root.rglob(name))
        return next((path.resolve() for path in candidates if path.is_file()), None)

    @staticmethod
    def _read_version(key: str, root: Path | None, executable: Path | None) -> str | None:
        """Detecta a versão instalada."""
        version = EmulatorManager._read_version_file(root) if root else None
        if version:
            return version
        if key == "fbneo":
            if root:
                version = EmulatorManager._read_fbneo_changelog_version(root)
                if version:
                    return version
            return EmulatorManager._fetch_fbneo_version()
        if key == "mame" and executable:
            return EmulatorManager._probe_mame_version(executable)
        return None

    @staticmethod
    def _read_fbneo_changelog_version(root: Path) -> str | None:
        """Obtém a versão que acompanha o pacote FBNeo, se o changelog existir."""
        paths = tuple(root.rglob("whatsnew.html")) + tuple(root.rglob("WhatsNew.html"))
        for path in paths:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            match = re.search(r"<h3>\s*v?(\d+(?:\.\d+){2,3})\s*</h3>", content, re.I)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _fetch_fbneo_version() -> str | None:
        """Lê os campos de versão usados para compilar o nightly FBNeo."""
        if EmulatorManager._FBNEO_VERSION_CACHE is not None:
            return EmulatorManager._FBNEO_VERSION_CACHE
        if EmulatorManager._FBNEO_VERSION_LOOKED_UP:
            return None
        EmulatorManager._FBNEO_VERSION_LOOKED_UP = True
        url = "https://raw.githubusercontent.com/finalburnneo/FBNeo/master/src/burn/version.h"
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=8) as response:
                source = response.read().decode("utf-8", errors="replace")
        except (OSError, URLError):
            return None
        fields = {
            name: re.search(rf"^#define\s+VER_{name}\s+(\d+)", source, re.M)
            for name in ("MAJOR", "MINOR", "BETA", "ALPHA")
        }
        if any(match is None for match in fields.values()):
            return None
        numbers = {name: int(match.group(1)) for name, match in fields.items() if match is not None}
        version = f"{numbers['MAJOR']}.{numbers['MINOR']}.{numbers['BETA']}.{numbers['ALPHA']:02d}"
        EmulatorManager._FBNEO_VERSION_CACHE = version
        return version

    @staticmethod
    def _read_version_file(root: Path) -> str | None:
        """Lê a versão a partir dos arquivos de versão conhecidos."""
        for filename in (VERSION_MARKER, "VERSION", "version.txt", "build.txt"):
            version = EmulatorManager._parse_version_file(root / filename)
            if version:
                return version
        return None

    @staticmethod
    def _parse_version_file(path: Path) -> str | None:
        if not path.is_file():
            return None
        try:
            text = path.read_text(encoding="utf-8-sig", errors="ignore").strip()
        except OSError:
            return None
        match = re.search(r"(\d+(?:\.\d+){1,3}(?:[a-z]-\d{8})?)", text, re.I)
        return match.group(1) if match else None

    @staticmethod
    def _probe_mame_version(executable: Path) -> str | None:
        """Consulta a versão do MAME."""
        try:
            result = subprocess.run([str(executable), "-noreadconfig", "-version"], cwd=str(executable.parent), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=4, check=False)
            match = re.search(r"\b(?:v)?(\d+\.\d+)\b", (result.stdout or "").strip())
            return match.group(1) if match else None
        except (OSError, subprocess.SubprocessError):
            return None


class RetroArchManager:
    """Gerencia RetroArch x64 e catálogo de cores libretro."""
    BUILD_ROOT = "https://buildbot.libretro.com"
    WINDOWS_ARCH = "x86_64"
    NIGHTLY_ROOT = f"{BUILD_ROOT}/nightly/windows/{WINDOWS_ARCH}/latest/"
    RETROARCH_ARCHIVE = "RetroArch.7z"
    VERSION_MARKER = VERSION_MARKER
    CHUNK_SIZE = 1024 * 1024
    TIMEOUT = 60
    RETRIES = 3
    LEGACY_CORE_NAMES = frozenset({"bnes2014", "desmume2015", "puae2021", "stella2014", "stella2023", "snes9x2002", "snes9x2005", "snes9x2005plus", "snes9x2010", "mame2000", "mame2003", "mame2003plus", "mame2003midway", "mame2009", "mame2010", "fbalpha2012", "fbalpha2012cps1", "fbalpha2012cps2", "fbalpha2012cps3", "fbalpha2012neogeo", "citra2018", "melonds2021", "bsnes2014accuracy", "bsnes2014balanced", "bsnes2014performance"})
    LEGACY_CORE_PATTERNS = (re.compile(r"^snes9x20(?:0[25]|10)(?:plus)?$", re.I), re.compile(r"^mame(?:2000|2003|2003plus|2003midway|2009|2010)$", re.I), re.compile(r"^(?:bnes|desmume|puae|stella)20(?:14|15|21|23)$", re.I))
    GAME_ENGINE_CORE_PATTERNS = (re.compile(r"^(?:2048|anarch|boom|boom3|boom3xp|craft|cruzes|gong|jumpnbump|mrboom|opentyrian|puzzlescript|superbroswar)$", re.I), re.compile(r"^(?:openlara|prboom|prboomplus|nxengine|cannonball|chailove|lutro|lowresnx|retro8|reminiscence|scummvm|mkxpz)$", re.I), re.compile(r"^vita(?:quake|quake2|quake3|voyager).*$", re.I), re.compile(r"^(?:xrick|pascalpong|vircon32|wasm4|3dengine|imageviewer|mpv|pocketcdg)$", re.I))

    def __init__(self, root: Path | None = None) -> None:
        """Inicializa o gerenciador."""
        self.root = Path(root).expanduser() if root else None

    def discover(self) -> tuple[Path | None, Path | None, Path | None]:
        """Localiza retroarch.exe, raiz e diretório de cores."""
        candidates = [self.root / "retroarch.exe"] if self.root else []
        candidates.extend((Path.home() / "RetroArch-Win64/retroarch.exe", Path("C:/RetroArch/retroarch.exe")))
        executable = next((path.resolve() for path in candidates if path.is_file()), None)
        root = executable.parent if executable else self.root
        cores = root / "cores" if root else None
        return executable, root, cores

    @staticmethod
    def detect_version(executable: Path | None) -> str | None:
        """Detecta a versão do RetroArch sem abrir janela."""
        if executable is None or not executable.is_file():
            return None
        marker = executable.parent / VERSION_MARKER
        if marker.is_file():
            try:
                return marker.read_text(encoding="utf-8-sig", errors="ignore").strip() or None
            except OSError:
                pass
        try:
            result = subprocess.run([str(executable), "--version"], cwd=str(executable.parent), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=4, check=False)
            match = re.search(r"RetroArch\s+(\d+\.\d+(?:\.\d+)?)", result.stdout or "", re.I)
            return match.group(1) if match else None
        except (OSError, subprocess.SubprocessError):
            return None

    @classmethod
    def _download_text(cls, url: str) -> str:
        """Baixa texto UTF-8 do Buildbot com retry."""
        last: Exception | None = None
        for _ in range(cls.RETRIES):
            try:
                request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
                with urlopen(request, timeout=cls.TIMEOUT) as response:
                    return response.read().decode("utf-8", errors="replace")
            except URLError as exc:
                last = exc
        raise RuntimeError(f"Falha ao consultar Buildbot: {url} | {last}") from last

    @classmethod
    def discover_stable_versions(cls) -> list[str]:
        """Descobre versões Stable publicadas."""
        html = cls._download_text(f"{cls.BUILD_ROOT}/stable/")
        versions: set[str] = set()
        for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.I):
            match = re.search(r"(?:^|/)v?(\d+\.\d+(?:\.\d+)*)/?$", href.strip())
            if match:
                versions.add(match.group(1))
        return sorted(versions, key=lambda value: tuple(map(int, value.split("."))), reverse=True)

    @classmethod
    def latest_stable_version(cls) -> str:
        """Retorna a Stable mais recente."""
        versions = cls.discover_stable_versions()
        if not versions:
            raise RuntimeError("Nenhuma versão Stable encontrada.")
        return versions[0]

    @classmethod
    def discover_nightly_archive(cls) -> tuple[str, str]:
        """Localiza o pacote Nightly x64 mais recente."""
        base = f"{cls.BUILD_ROOT}/nightly/windows/{cls.WINDOWS_ARCH}/"
        html = cls._download_text(base)
        filenames = [href.rsplit("/", 1)[-1] for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.I)]
        filenames = [name for name in filenames if re.fullmatch(r"\d{4}-\d{2}-\d{2}_RetroArch\.7z", name, re.I)]
        if not filenames:
            raise RuntimeError("Nenhum pacote Nightly encontrado.")
        filename = max(filenames, key=lambda value: value[:10])
        return filename, base + filename

    @classmethod
    def buildroot(cls, channel: str, stable_version: str | None = None) -> tuple[str, str]:
        """Resolve a raiz do frontend RetroArch."""
        if channel.casefold() == "stable":
            version = stable_version or cls.latest_stable_version()
            return f"{cls.BUILD_ROOT}/stable/{version}/windows/{cls.WINDOWS_ARCH}/", version
        if channel.casefold() == "nightly":
            return cls.NIGHTLY_ROOT, "nightly"
        raise ValueError(f"Canal RetroArch inválido: {channel!r}")

    @classmethod
    def _core_catalog_url(cls, channel: str) -> str:
        """Retorna o índice de cores disponível para o catálogo."""
        if channel.casefold() in {"nightly", "stable"}:
            return f"{cls.NIGHTLY_ROOT}.index-extended"
        raise ValueError(f"Canal de cores inválido: {channel!r}")

    @staticmethod
    def _parse_core_index(text: str, channel: str) -> tuple[CoreInfo, ...]:
        """Converte .index-extended em CoreInfo."""
        result: list[CoreInfo] = []
        for line in text.splitlines():
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            date, crc, filename = parts[0], parts[1], parts[-1]
            if not filename.casefold().endswith("_libretro.dll.zip"):
                continue
            name = re.sub(r"_libretro\.dll$", "", filename.removesuffix(".zip"), flags=re.I)
            result.append(CoreInfo(filename=filename, core_name=name, date=date, crc32=crc.lower().removeprefix("0x").zfill(8), channel=channel))
        return tuple(sorted(result, key=lambda item: item.core_name.casefold()))

    @classmethod
    def is_legacy_core(cls, core: CoreInfo) -> bool:
        """Identifica snapshots históricos."""
        normalized = re.sub(r"[^a-z0-9]", "", core.core_name.casefold())
        return normalized in cls.LEGACY_CORE_NAMES or any(pattern.fullmatch(normalized) for pattern in cls.LEGACY_CORE_PATTERNS)

    @classmethod
    def is_game_or_engine_core(cls, core: CoreInfo) -> bool:
        """Identifica ports, jogos e game engines."""
        normalized = re.sub(r"[^a-z0-9]", "", core.core_name.casefold())
        return any(pattern.fullmatch(normalized) for pattern in cls.GAME_ENGINE_CORE_PATTERNS)

    @classmethod
    def filter_cores(cls, cores: tuple[CoreInfo, ...], *, current_only: bool = True, hide_games: bool = True) -> tuple[CoreInfo, ...]:
        """Aplica os filtros solicitados para o catálogo."""
        return tuple(core for core in cores if (not current_only or not cls.is_legacy_core(core)) and (not hide_games or not cls.is_game_or_engine_core(core)))

    def list_cores(self, channel: str = "nightly", stable_version: str | None = None, *, current_only: bool = False, hide_games: bool = False) -> tuple[CoreInfo, ...]:
        """Lê o catálogo oficial sem gerar 404 no caminho Stable."""
        _ = stable_version
        result = self._parse_core_index(self._download_text(self._core_catalog_url(channel)), channel)
        filtered = self.filter_cores(result, current_only=current_only, hide_games=hide_games)
        if not filtered:
            raise RuntimeError(f"Nenhum core corresponde aos filtros no catálogo {channel}.")
        return filtered

    def list_filtered_cores(self, *, include_beta: bool = False, current_only: bool = True, hide_games: bool = True, stable_version: str | None = None) -> tuple[CoreInfo, ...]:
        """Monta Stable ou Stable+Nightly sem consultar uma URL Stable inexistente."""
        channels = ("stable", "nightly") if include_beta else ("stable",)
        merged: dict[str, CoreInfo] = {}
        for channel in channels:
            for core in self.list_cores(channel, stable_version, current_only=False, hide_games=False):
                key = core.core_name.casefold()
                if key not in merged or channel == "stable":
                    merged[key] = core
        return self.filter_cores(tuple(merged.values()), current_only=current_only, hide_games=hide_games)

    @staticmethod
    def _crc32(path: Path) -> str:
        """Calcula CRC32 em blocos."""
        checksum = 0
        with Path(path).open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                checksum = binascii.crc32(chunk, checksum)
        return f"{checksum & 0xFFFFFFFF:08x}"

    @classmethod
    def crc32(cls, path: Path) -> str:
        """Calcula CRC32 hexadecimal."""
        return cls._crc32(path)

    @staticmethod
    def installed_cores(cores_dir: Path | None) -> tuple[Path, ...]:
        """Lista cores instalados."""
        if cores_dir is None:
            return ()
        path = Path(cores_dir).expanduser().resolve()
        return tuple(sorted(path.glob("*_libretro.dll"), key=lambda item: item.name.casefold())) if path.is_dir() else ()

    def compare_installed_cores(self, cores: tuple[CoreInfo, ...], cores_dir: Path | None) -> list[tuple[Path, CoreInfo | None, str]]:
        """Compara CRC32 local com o catálogo."""
        remote = {core.filename.removesuffix(".zip").casefold(): core for core in cores}
        result: list[tuple[Path, CoreInfo | None, str]] = []
        for path in self.installed_cores(cores_dir):
            remote_core = remote.get(path.name.casefold())
            local_crc = self._crc32(path)
            state = "unknown" if remote_core is None else ("current" if local_crc == remote_core.crc32 else "update")
            result.append((path, remote_core, state))
        return result

    def install_core(self, filename: str, destination: Path, *, channel: str = "nightly", stable_version: str | None = None, progress=None, log=None) -> Path:
        """Baixa e instala um core individual do Buildbot Nightly."""
        self._validate_core_channel(channel)
        filename = self._validate_core_filename(filename)
        url = f"{self.NIGHTLY_ROOT}{filename}"
        destination = Path(destination).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(tempfile.mkdtemp(prefix="serm-core-"))
        archive: Path | None = None
        try:
            fd, temp_name = tempfile.mkstemp(prefix="core-", suffix=".zip", dir=temp_dir)
            os.close(fd)
            archive = Path(temp_name)
            if log:
                log(f"DOWNLOAD | core={filename} | temporário={archive}")
            self._download_file(url, archive, progress, log)
            dll_name, data = self._read_core_archive(archive, filename)
            target = (destination / Path(dll_name).name).resolve()
            self._validate_core_target(destination, target)
            temp_dll = target.with_suffix(target.suffix + ".tmp")
            temp_dll.write_bytes(data)
            actual_crc = self._crc32(temp_dll)
            remote = self._find_core(filename, stable_version)
            self._validate_core_crc(temp_dll, target, actual_crc, remote)
            temp_dll.replace(target)
        finally:
            if archive is not None:
                try:
                    archive.unlink(missing_ok=True)
                except OSError:
                    pass
            try:
                temp_dir.rmdir()
            except OSError:
                pass
        if log:
            log(f"CORE INSTALADO | {target} | CRC32={actual_crc}")
        return target

    @staticmethod
    def _validate_core_channel(channel: str) -> None:
        if channel.casefold() == "stable":
            raise RuntimeError("O Buildbot Stable não publica cores individuais; o snapshot Stable é RetroArch_cores.7z. Use Nightly para instalação individual.")

    @staticmethod
    def _validate_core_filename(filename: str) -> str:
        filename = Path(filename).name
        if not filename or not filename.casefold().endswith("_libretro.dll.zip"):
            raise ValueError(f"Nome de core inválido para download: {filename!r}")
        return filename

    @staticmethod
    def _read_core_archive(archive: Path, filename: str) -> tuple[str, bytes]:
        with zipfile.ZipFile(archive) as package:
            bad = package.testzip()
            if bad:
                raise RuntimeError(f"ZIP corrompido do core: {bad}")
            dll_names = [name for name in package.namelist() if name.casefold().endswith("_libretro.dll")]
            if not dll_names:
                raise RuntimeError(f"ZIP sem DLL libretro: {filename}")
            return dll_names[0], package.read(dll_names[0])

    @staticmethod
    def _validate_core_target(destination: Path, target: Path) -> None:
        if destination not in target.parents:
            raise RuntimeError("Caminho inseguro no core.")

    def _find_core(self, filename: str, stable_version: str | None) -> CoreInfo | None:
        return next((core for core in self.list_cores("nightly", stable_version) if core.filename.casefold() == filename.casefold()), None)

    @staticmethod
    def _validate_core_crc(temp_dll: Path, target: Path, actual_crc: str, remote: CoreInfo | None) -> None:
        if remote is None or remote.crc32 != actual_crc:
            temp_dll.unlink(missing_ok=True)
            expected = remote.crc32 if remote else "desconhecido"
            raise RuntimeError(f"CRC32 inválido para {target.name}: recebido={actual_crc}, esperado={expected}")

    def install_frontend(self, destination: Path, *, channel: str = "stable", progress=None, log=None) -> DownloadResult:
        """Baixa e instala o frontend RetroArch x64 Stable ou Nightly diretamente no diretório selecionado."""
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
                log(f"RETROARCH | canal={channel} | versão={version_label} | arquivo={archive_name}")
                log(f"DOWNLOAD | {url}")
            self._download_file(url, archive, progress, log)
            self._extract(archive, extracted, log)
            install_root = self._normalize_extracted_root(extracted)
            if log and install_root != extracted:
                log(f"RETROARCH | removendo diretório contêiner do pacote: {install_root.name}")
            self._merge(install_root, destination)
            self._flatten_retroarch_wrappers(destination, log=log)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        executable = destination / "retroarch.exe"
        if not executable.is_file():
            raise RuntimeError(f"Download concluído, mas retroarch.exe não foi encontrado diretamente em {destination}.")
        return DownloadResult("retroarch", version_label, executable.resolve(), archive_name)

    @staticmethod
    def _normalize_extracted_root(source: Path) -> Path:
        """Remove somente o diretório contêiner criado pelo pacote RetroArch.

        O arquivo oficial pode ser empacotado como uma única pasta, por exemplo
        ``RetroArch-Win64``. Essa pasta não faz parte do destino configurado pelo
        usuário; somente seu conteúdo deve ser mesclado no diretório selecionado.
        """
        executable = next(source.rglob("retroarch.exe"), None)
        if executable is not None:
            return executable.parent
        items = list(source.iterdir())
        if len(items) == 1 and items[0].is_dir():
            return items[0]
        return source

    @classmethod
    def _flatten_retroarch_wrappers(cls, destination: Path, *, log=None) -> None:
        """Move every file from wrapper folders into the configured install root.

        Stable and Nightly archives have used different top-level layouts. Work
        from the directory containing the executable when possible; any leftover
        wrapper directories are copied recursively and removed after the copy.
        """
        executable = next(
            (path for path in destination.rglob("retroarch.exe") if path.is_file()),
            None,
        )
        if executable is not None and executable.parent != destination:
            cls._merge(executable.parent, destination)

        wrappers = sorted(
            (path for path in destination.rglob("*")
             if path.is_dir() and path.name.casefold() == "retroarch-win64"),
            key=lambda path: len(path.parts),
            reverse=True,
        )
        for wrapper in wrappers:
            if not wrapper.exists():
                continue
            cls._merge(wrapper, destination)
            shutil.rmtree(wrapper)
            if log:
                log(f"RETROARCH | conteúdo de {wrapper.name} movido para a raiz configurada")

    @classmethod
    def _extract(cls, archive: Path, destination: Path, log=None) -> None:
        """Extrai um ZIP internamente ou usa o 7-Zip instalado."""
        if archive.suffix.casefold() == ".zip":
            with zipfile.ZipFile(archive) as package:
                package.extractall(destination)
            return
        seven_zip = cls.detect_7zip()
        if seven_zip is None:
            raise RuntimeError("7z.exe não foi encontrado.")
        result = subprocess.run([str(seven_zip), "x", "-y", f"-o{destination}", str(archive)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=300, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"7-Zip falhou ({result.returncode}): {(result.stdout or '').strip()}")

    @staticmethod
    def _merge(source: Path, destination: Path) -> None:
        """Mescla a árvore extraída no diretório de instalação."""
        for item in source.iterdir():
            target = destination / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)

    @classmethod
    def detect_7zip(cls) -> Path | None:
        """Localiza 7-Zip."""
        for command in ("7z.exe", "7z", "7za.exe", "7za"):
            found = shutil.which(command)
            if found:
                return Path(found).resolve()
        for root in filter(None, (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA"))):
            path = Path(root) / "7-Zip/7z.exe"
            if path.is_file():
                return path.resolve()
        return None

    @classmethod
    def _download_file(cls, url: str, target: Path, progress=None, log=None) -> None:
        """Baixa um arquivo em blocos com retry."""
        target = Path(target)
        if target.is_dir():
            raise IsADirectoryError(f"Destino do download é um diretório, não um arquivo: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        last: Exception | None = None
        for attempt in range(1, cls.RETRIES + 1):
            try:
                received = cls._download_attempt(url, target, progress)
                if log:
                    log(f"DOWNLOAD | {received:,} bytes | tentativa={attempt}")
                return
            except (OSError, RuntimeError) as exc:
                last = exc
                cls._remove_partial_download(target)
                if log:
                    log(f"DOWNLOAD ERRO | tentativa={attempt}/{cls.RETRIES} | {exc}")
        raise RuntimeError(f"Falha no download: {url} | {last}") from last

    @classmethod
    def _download_attempt(cls, url: str, target: Path, progress=None) -> int:
        """Executa uma tentativa de download e retorna o total recebido."""
        if target.exists():
            target.unlink()
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
        with urlopen(request, timeout=cls.TIMEOUT) as response, target.open("wb") as output:
            total = int(response.headers.get("Content-Length") or 0)
            received = 0
            while chunk := response.read(cls.CHUNK_SIZE):
                output.write(chunk)
                received += len(chunk)
                if progress:
                    progress(received, total)
        if received <= 0:
            raise RuntimeError("Download retornou zero bytes.")
        return received

    @staticmethod
    def _remove_partial_download(target: Path) -> None:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
