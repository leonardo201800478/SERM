"""RetroBIOS BIOS-pack acquisition and local pack store."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..runtime.paths import data_root, integrations_root


class RetroBiosPackError(RuntimeError):
    """Actionable BIOS-pack acquisition error."""


@dataclass(frozen=True, slots=True)
class RetroBiosPackAsset:
    name: str
    url: str
    size: int
    sha256: str
    part: int | None = None


@dataclass(frozen=True, slots=True)
class RetroBiosPack:
    platform: str
    archive_name: str
    assets: tuple[RetroBiosPackAsset, ...]
    extracted_size_label: str = ""

    @property
    def multipart(self) -> bool:
        return len(self.assets) > 1

    @property
    def size(self) -> int:
        return sum(asset.size for asset in self.assets)


class RetroBiosPackService:
    """Downloads official RetroBIOS platform packs into a reusable local source."""

    API_URL = "https://api.github.com/repos/Abdess/retrobios/releases/latest"
    PACKS_ROOT = data_root() / "retrobios_packs"
    CONFIG_PATH = integrations_root() / "tools.json"
    DOWNLOADS_ROOT = PACKS_ROOT / ".downloads"
    MAX_RELEASE_BYTES = 4 * 1024 * 1024
    MAX_CHECKSUM_BYTES = 2 * 1024 * 1024
    CHUNK_SIZE = 1024 * 1024
    PACK_RE = re.compile(r"^(?P<base>.+_BIOS_Pack\\.zip)(?:\\.(?P<part>\\d{3}))?$", re.IGNORECASE)
    SAFE_PART_RE = re.compile(r"^\\d{3}$")

    @classmethod
    def default_directory(cls) -> Path:
        return cls.PACKS_ROOT

    @classmethod
    def storage_directory(cls) -> Path:
        """Retorna a pasta configurada em Ferramentas ou o padrão do SERM."""
        try:
            payload = json.loads(cls.CONFIG_PATH.read_text(encoding="utf-8"))
            value = payload.get("retrobios_packs_directory") if isinstance(payload, dict) else None
            if isinstance(value, str) and value.strip():
                return Path(value).expanduser().resolve()
        except (OSError, ValueError, TypeError):
            pass
        return cls.PACKS_ROOT.resolve()

    @classmethod
    def list_available(cls) -> tuple[RetroBiosPack, ...]:
        payload = cls._get_json(cls.API_URL, cls.MAX_RELEASE_BYTES)
        if not isinstance(payload, dict):
            raise RetroBiosPackError("A resposta da release RetroBIOS é inválida.")
        assets = payload.get("assets")
        if not isinstance(assets, list):
            raise RetroBiosPackError("A release RetroBIOS não informou seus assets.")

        grouped: dict[str, list[RetroBiosPackAsset]] = {}
        for raw in assets:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "").strip()
            match = cls.PACK_RE.fullmatch(name)
            if not match:
                continue
            url = str(raw.get("browser_download_url") or "").strip()
            if not url.startswith("https://github.com/Abdess/retrobios/releases/download/"):
                continue
            digest = str(raw.get("digest") or "").strip()
            sha256 = digest.removeprefix("sha256:").casefold() if digest.startswith("sha256:") else ""
            try:
                size = int(raw.get("size") or 0)
            except (TypeError, ValueError):
                size = 0
            part_text = match.group("part")
            part = int(part_text) if part_text else None
            grouped.setdefault(match.group("base"), []).append(
                RetroBiosPackAsset(name, url, max(size, 0), sha256, part)
            )

        packs: list[RetroBiosPack] = []
        for archive_name, pack_assets in grouped.items():
            pack_assets.sort(key=lambda item: (item.part is None, item.part or 0, item.name.casefold()))
            if len(pack_assets) > 1 and any(asset.part is None for asset in pack_assets):
                continue
            platform = archive_name.removesuffix("_BIOS_Pack.zip").replace("_", " ").strip()
            packs.append(RetroBiosPack(platform, archive_name, tuple(pack_assets)))
        return tuple(sorted(packs, key=lambda pack: pack.platform.casefold()))

    @classmethod
    def download_and_extract(
        cls,
        pack: RetroBiosPack,
        *,
        destination: str | Path | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
    ) -> Path:
        root = Path(destination).expanduser().resolve() if destination else cls.storage_directory()
        root.mkdir(parents=True, exist_ok=True)
        safe_platform = cls._safe_name(pack.platform)
        target = root / safe_platform
        target.mkdir(parents=True, exist_ok=True)
        download_dir = root / ".downloads" / safe_platform
        download_dir.mkdir(parents=True, exist_ok=True)

        total_bytes = pack.size
        done_bytes = 0
        downloaded: list[Path] = []
        for asset in pack.assets:
            if cancel_callback and cancel_callback():
                raise RetroBiosPackError("Download do pack cancelado.")
            target_file = download_dir / asset.name
            cls._download(
                asset,
                target_file,
                progress_callback=lambda done, _total, base=done_bytes: (
                    progress_callback(base + done, total_bytes)
                    if progress_callback
                    else None
                ),
                cancel_callback=cancel_callback,
            )
            done_bytes += asset.size
            downloaded.append(target_file)

        archive = cls._assemble_archive(pack, downloaded, download_dir)
        cls._verify_pack_checksum(pack, archive)
        cls._extract_safe(archive, target, cancel_callback=cancel_callback)
        return target

    @classmethod
    def _download(
        cls,
        asset: RetroBiosPackAsset,
        target: Path,
        *,
        progress_callback: Callable[[int, int], None] | None,
        cancel_callback: Callable[[], bool] | None,
    ) -> None:
        if target.is_file() and (not asset.sha256 or cls._sha256_file(target) == asset.sha256):
            if progress_callback:
                progress_callback(asset.size, asset.size)
            return
        request = urllib.request.Request(
            asset.url,
            headers={"User-Agent": "SERM/2.x", "Accept": "application/octet-stream"},
        )
        temp = target.with_suffix(target.suffix + ".part")
        try:
            with urllib.request.urlopen(request, timeout=60) as response, temp.open("wb") as stream:
                done = 0
                while True:
                    if cancel_callback and cancel_callback():
                        raise RetroBiosPackError("Download do pack cancelado.")
                    chunk = response.read(cls.CHUNK_SIZE)
                    if not chunk:
                        break
                    stream.write(chunk)
                    done += len(chunk)
                    if progress_callback:
                        progress_callback(done, asset.size)
            if asset.size and temp.stat().st_size != asset.size:
                raise RetroBiosPackError(
                    f"Tamanho inesperado para {asset.name}: {temp.stat().st_size} bytes."
                )
            if asset.sha256 and cls._sha256_file(temp) != asset.sha256:
                raise RetroBiosPackError(f"SHA-256 inválido para {asset.name}.")
            temp.replace(target)
        except RetroBiosPackError:
            temp.unlink(missing_ok=True)
            raise
        except Exception as exc:  # noqa: BLE001
            temp.unlink(missing_ok=True)
            raise RetroBiosPackError(f"Não foi possível baixar {asset.name}: {exc}") from exc

    @classmethod
    def _assemble_archive(
        cls, pack: RetroBiosPack, files: list[Path], work_dir: Path
    ) -> Path:
        if len(files) == 1 and files[0].name.casefold().endswith(".zip"):
            return files[0]
        output = work_dir / pack.archive_name
        temp = output.with_suffix(output.suffix + ".part")
        with temp.open("wb") as target:
            for source in files:
                with source.open("rb") as stream:
                    shutil.copyfileobj(stream, target, length=cls.CHUNK_SIZE)
        temp.replace(output)
        return output

    @classmethod
    def _verify_pack_checksum(cls, pack: RetroBiosPack, archive: Path) -> None:
        sums_url = "https://github.com/Abdess/retrobios/releases/download/"
        # The release API asset digest verifies every downloaded volume. For split packs,
        # the joined ZIP is additionally checked when the release publishes SHA256SUMS.txt.
        if not pack.multipart:
            return
        release_tag = cls._release_tag_from_asset(pack.assets[0].url)
        if not release_tag:
            return
        url = f"{sums_url}{release_tag}/SHA256SUMS.txt"
        try:
            raw = cls._get_bytes(url, cls.MAX_CHECKSUM_BYTES)
        except RetroBiosPackError:
            return
        expected = ""
        for line in raw.decode("utf-8", errors="replace").splitlines():
            parts = line.split()
            if len(parts) >= 2 and Path(parts[-1].lstrip("*")).name == pack.archive_name:
                expected = parts[0].casefold()
                break
        if expected and cls._sha256_file(archive) != expected:
            raise RetroBiosPackError(
                f"SHA-256 do ZIP montado não confere com SHA256SUMS.txt: {pack.archive_name}."
            )

    @staticmethod
    def _release_tag_from_asset(url: str) -> str:
        marker = "/releases/download/"
        if marker not in url:
            return ""
        value = url.split(marker, 1)[1]
        return value.split("/", 1)[0]

    @classmethod
    def _extract_safe(
        cls,
        archive: Path,
        destination: Path,
        *,
        cancel_callback: Callable[[], bool] | None,
    ) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="serm-retrobios-", dir=str(destination.parent)))
        try:
            with zipfile.ZipFile(archive, "r") as zin:
                for info in zin.infolist():
                    if cancel_callback and cancel_callback():
                        raise RetroBiosPackError("Extração do pack cancelada.")
                    relative = cls._safe_archive_path(info.filename)
                    if relative is None:
                        raise RetroBiosPackError(
                            f"Entrada insegura no pack RetroBIOS: {info.filename!r}"
                        )
                    mode = (info.external_attr >> 16) & 0o170000
                    if mode == 0o120000:
                        raise RetroBiosPackError(
                            f"Link simbólico não permitido no pack RetroBIOS: {info.filename!r}"
                        )
                    output = temp_root.joinpath(*relative.parts)
                    if info.is_dir():
                        output.mkdir(parents=True, exist_ok=True)
                        continue
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with zin.open(info, "r") as source, output.open("wb") as target:
                        shutil.copyfileobj(source, target, length=cls.CHUNK_SIZE)
            cls._merge_tree(temp_root, destination)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    @staticmethod
    def _merge_tree(source: Path, destination: Path) -> None:
        for item in source.iterdir():
            target = destination / item.name
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                RetroBiosPackService._merge_tree(item, target)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and target.is_file():
                    # Never replace an existing local file during pack acquisition.
                    if target.stat().st_size == item.stat().st_size:
                        continue
                    raise RetroBiosPackError(
                        f"Conflito de arquivo ao extrair pack: {target}"
                    )
                item.replace(target)

    @staticmethod
    def _safe_archive_path(name: str) -> Path | None:
        normalized = name.replace("\\", "/")
        path = Path(normalized)
        if (
            not normalized
            or normalized.startswith("/")
            or Path(normalized).drive
            or ".." in path.parts
        ):
            return None
        parts = tuple(part for part in path.parts if part not in ("", "."))
        return Path(*parts) if parts else None

    @staticmethod
    def _safe_name(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip(" ._")
        return cleaned or "retrobios"

    @classmethod
    def _get_json(cls, url: str, limit: int) -> object:
        return json.loads(cls._get_bytes(url, limit).decode("utf-8"))

    @staticmethod
    def _get_bytes(url: str, limit: int) -> bytes:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "SERM/2.x", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read(limit + 1)
        except Exception as exc:  # noqa: BLE001
            raise RetroBiosPackError(f"Falha ao acessar RetroBIOS: {exc}") from exc
        if len(data) > limit:
            raise RetroBiosPackError("Resposta RetroBIOS excedeu o limite permitido.")
        return data

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(RetroBiosPackService.CHUNK_SIZE):
                digest.update(chunk)
        return digest.hexdigest()


__all__ = ["RetroBiosPack", "RetroBiosPackAsset", "RetroBiosPackError", "RetroBiosPackService"]
