"""Download e instalação segura de emuladores oficiais."""
from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

from app.core.services.emulator_download_service import (
    ReleaseAsset,
    ReleaseInfo,
    choose_windows_x64_asset,
    latest_nightly_release,
    latest_release,
)


class EmulatorInstallError(RuntimeError):
    """Erro controlado durante download ou instalação."""


class EmulatorInstallService:
    """Instala pacotes Windows x64 diretamente no diretório escolhido.

    A extração usa uma área temporária para evitar deixar uma instalação parcial
    no destino. Quando o ZIP possui uma única pasta-raiz criada pelo empacotador,
    essa pasta é removida logicamente durante a instalação; seus conteúdos passam
    diretamente para o diretório escolhido pelo usuário.
    """

    def release(self, emulator: str, *, nightly: bool = False) -> ReleaseInfo:
        """Obtém metadados do release oficial solicitado."""
        return latest_nightly_release(emulator) if nightly else latest_release(emulator)

    def select_asset(self, release: ReleaseInfo) -> ReleaseAsset:
        """Seleciona o pacote Windows x64 oficial disponível no release."""
        asset = choose_windows_x64_asset(release)
        if asset is None:
            raise EmulatorInstallError(
                f"Nenhum pacote Windows x64 foi encontrado no release {release.tag!r}."
            )
        return asset

    def download_and_install(
        self,
        emulator: str,
        destination: Path,
        *,
        nightly: bool = False,
        progress=None,
    ) -> tuple[ReleaseInfo, ReleaseAsset, Path]:
        """Baixa e extrai o emulador diretamente no diretório informado.

        ``progress`` recebe ``(bytes_recebidos, total_bytes)`` durante o download.
        O diretório de destino é criado quando necessário. Nenhuma subpasta do
        pacote é usada como diretório final de instalação.
        """
        destination = Path(destination).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)

        release = self.release(emulator, nightly=nightly)
        asset = self.select_asset(release)

        with tempfile.TemporaryDirectory(prefix="mame-set-builder-emu-") as temp_name:
            temp_dir = Path(temp_name)
            archive = temp_dir / asset.name
            self._download(asset, archive, progress)

            extract_dir = temp_dir / "extracted"
            extract_dir.mkdir()
            self._extract_archive(archive, extract_dir)
            source_root = self._package_root(extract_dir)
            self._validate_root_install(source_root, emulator)
            self._merge_into_destination(source_root, destination)

        executable = self._find_executable(destination, emulator)
        if executable is None:
            raise EmulatorInstallError(
                f"O pacote de {emulator} foi extraído, mas nenhum executável do emulador "
                "foi encontrado diretamente no diretório selecionado."
            )
        return release, asset, executable

    @staticmethod
    def _download(asset: ReleaseAsset, target: Path, progress=None) -> None:
        """Baixa o asset por HTTPS e reporta progresso sem bloquear a lógica de instalação."""
        request = Request(asset.url, headers={"User-Agent": "mame-set-builder"})
        try:
            with urlopen(request, timeout=30) as response, target.open("wb") as output:
                total = int(response.headers.get("Content-Length") or asset.size or 0)
                received = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    received += len(chunk)
                    if progress:
                        progress(received, total)
        except Exception as exc:
            raise EmulatorInstallError(f"Falha no download de {asset.name}: {exc}") from exc

    @staticmethod
    def _extract_archive(archive: Path, destination: Path) -> None:
        """Extrai um ZIP sem permitir escrita fora da área temporária."""
        if not zipfile.is_zipfile(archive):
            raise EmulatorInstallError(
                f"O pacote {archive.name} não é um ZIP compatível com a instalação automática."
            )
        try:
            with zipfile.ZipFile(archive) as zf:
                base = destination.resolve()
                for member in zf.infolist():
                    target = (destination / member.filename).resolve()
                    if target != base and base not in target.parents:
                        raise EmulatorInstallError("O pacote contém um caminho de extração inseguro.")
                zf.extractall(destination)
        except zipfile.BadZipFile as exc:
            raise EmulatorInstallError(f"Arquivo ZIP inválido: {archive.name}") from exc

    @staticmethod
    def _package_root(extracted: Path) -> Path:
        """Retorna a raiz real do pacote, removendo uma única pasta empacotadora."""
        entries = list(extracted.iterdir())
        if len(entries) == 1 and entries[0].is_dir():
            return entries[0]
        return extracted

    @staticmethod
    def _validate_root_install(root: Path, emulator: str) -> None:
        """Garante que o pacote possui um executável diretamente em sua raiz."""
        executables = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".exe"]
        if not executables:
            raise EmulatorInstallError(
                f"O pacote de {emulator} não possui executável diretamente na raiz do pacote."
            )

    @staticmethod
    def _merge_into_destination(source: Path, destination: Path) -> None:
        """Copia o conteúdo da raiz do pacote para o destino, sem criar subpasta."""
        for item in source.iterdir():
            target = destination / item.name
            if item.is_dir():
                if target.exists() and target.is_dir():
                    for child in item.iterdir():
                        EmulatorInstallService._copy_tree_item(child, target / child.name)
                else:
                    shutil.copytree(item, target)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)

    @staticmethod
    def _copy_tree_item(source: Path, target: Path) -> None:
        """Mescla um item de diretório preservando subdiretórios internos."""
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            for child in source.iterdir():
                EmulatorInstallService._copy_tree_item(child, target / child.name)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    @staticmethod
    def _find_executable(destination: Path, emulator: str) -> Path | None:
        """Localiza o executável somente na raiz do diretório de instalação."""
        preferred = {
            "mame": ("mame.exe",),
            "flycast": ("flycast.exe",),
            "supermodel": ("supermodel.exe", "supermodel3.exe"),
            "fbneo": ("fbneo.exe", "fba.exe", "fba64.exe"),
        }.get(emulator.strip().lower(), ())
        for name in preferred:
            candidate = destination / name
            if candidate.is_file():
                return candidate
        executables = sorted(p for p in destination.iterdir() if p.is_file() and p.suffix.lower() == ".exe")
        return executables[0] if len(executables) == 1 else None
