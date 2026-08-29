"""Descoberta resiliente dos releases oficiais dos emuladores."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class EmulatorRepository:
    """Repositório oficial e política de release de um emulador."""
    emulator: str
    repository: str
    nightly_release_tag: str | None = None


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    """Asset oficial disponibilizado em um release."""
    name: str
    url: str
    size: int
    content_type: str | None


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    """Metadados normalizados de um release do GitHub."""
    emulator: str
    tag: str
    name: str
    published_at: str | None
    prerelease: bool
    draft: bool
    html_url: str
    assets: tuple[ReleaseAsset, ...]


REPOSITORIES: dict[str, EmulatorRepository] = {
    "mame": EmulatorRepository("mame", "mamedev/mame"),
    "flycast": EmulatorRepository("flycast", "flyinghead/flycast"),
    "supermodel": EmulatorRepository("supermodel", "trzy/supermodel"),
    "fbneo": EmulatorRepository("fbneo", "finalburnneo/FBNeo", nightly_release_tag="latest"),
}


def _github_json(url: str) -> Any:
    """Lê uma URL pública da API do GitHub sem autenticação."""
    request = Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "mame-set-builder"},
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _assets(payload: dict[str, Any]) -> tuple[ReleaseAsset, ...]:
    """Normaliza os assets de um payload de release."""
    return tuple(
        ReleaseAsset(
            name=str(asset.get("name", "")),
            url=str(asset.get("browser_download_url", "")),
            size=int(asset.get("size", 0) or 0),
            content_type=asset.get("content_type"),
        )
        for asset in payload.get("assets", [])
        if asset.get("browser_download_url")
    )


def _release_info(emulator: str, payload: dict[str, Any]) -> ReleaseInfo:
    """Converte um payload do GitHub para o modelo interno."""
    return ReleaseInfo(
        emulator=emulator,
        tag=str(payload.get("tag_name", "")),
        name=str(payload.get("name", payload.get("tag_name", ""))),
        published_at=payload.get("published_at"),
        prerelease=bool(payload.get("prerelease", False)),
        draft=bool(payload.get("draft", False)),
        html_url=str(payload.get("html_url", "")),
        assets=_assets(payload),
    )


def latest_release(emulator: str) -> ReleaseInfo:
    """Obtém o release estável mais recente do repositório oficial."""
    key = emulator.strip().lower()
    repository = REPOSITORIES[key]
    payload = _github_json(f"https://api.github.com/repos/{repository.repository}/releases/latest")
    return _release_info(key, payload)


def latest_nightly_release(emulator: str) -> ReleaseInfo:
    """Obtém o nightly oficial quando o projeto expõe um release rolling."""
    key = emulator.strip().lower()
    repository = REPOSITORIES[key]
    if not repository.nightly_release_tag:
        raise ValueError(f"O repositório oficial de {key} não expõe um release nightly padronizado.")
    payload = _github_json(
        f"https://api.github.com/repos/{repository.repository}/releases/tags/{repository.nightly_release_tag}"
    )
    return _release_info(key, payload)


def _score_asset(emulator: str, asset: ReleaseAsset) -> int:
    """Calcula a confiança de que um asset seja o pacote Windows x64 correto."""
    name = asset.name.lower()
    score = 0

    if any(token in name for token in ("windows", "win64", "win-x64", "win_x64", "mingw")):
        score += 50
    if any(token in name for token in ("x64", "x86_64", "amd64", "64bit", "64-bit")):
        score += 35

    if "source" in name or "src" in name:
        score -= 100
    if any(token in name for token in ("linux", "ubuntu", "appimage", "macos", "osx", "android", "ios")):
        score -= 100
    if any(token in name for token in ("arm64", "aarch64", "armv7", "win32", "i386")):
        score -= 100

    if name.endswith(".zip"):
        score += 20
    elif name.endswith((".7z", ".7zip")):
        score += 10
    elif name.endswith(".exe"):
        score += 15

    if emulator == "mame":
        if re.search(r"_x64\.exe$", name):
            score += 140
        if name.startswith("mame") and "x64" in name:
            score += 40
    elif emulator == "flycast":
        if re.search(r"flycast-win64(?:[-_]|\.zip$)", name):
            score += 150
        elif "flycast" in name and "win64" in name:
            score += 80
    elif emulator == "supermodel":
        if "supermodel" in name and "windows" in name:
            score += 140
        elif "supermodel" in name and "win" in name:
            score += 100
    elif emulator == "fbneo":
        if name == "windows-x86_64.zip":
            score += 180
        elif "windows" in name and "x86_64" in name:
            score += 130

    return score


def choose_windows_x64_asset(release: ReleaseInfo) -> ReleaseAsset | None:
    """Escolhe o melhor asset Windows x64 sem depender de versão fixa."""
    candidates = [(asset, _score_asset(release.emulator, asset)) for asset in release.assets]
    candidates = [item for item in candidates if item[1] > 0]
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[1], item[0].size), reverse=True)
    best, score = candidates[0]
    return best if score >= 70 else None
