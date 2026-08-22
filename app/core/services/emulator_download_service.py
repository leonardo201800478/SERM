"""Discover official emulator releases for Windows x64.

Only official GitHub release metadata is consulted. This service does not
install or overwrite existing emulator files.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class EmulatorRepository:
    """Official repository and release policy for a supported emulator."""

    emulator: str
    repository: str
    nightly_release_tag: str | None = None


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    """Downloadable release asset."""

    name: str
    url: str
    size: int
    content_type: str | None


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    """Normalized GitHub release metadata."""

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
    """Read one public GitHub API endpoint without authentication."""
    request = Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "mame-set-builder"},
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _assets(payload: dict[str, Any]) -> tuple[ReleaseAsset, ...]:
    """Normalize GitHub release assets."""
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
    """Convert a GitHub release payload to the project model."""
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
    """Return the latest stable release published by the official project."""
    key = emulator.strip().lower()
    repository = REPOSITORIES[key]
    payload = _github_json(f"https://api.github.com/repos/{repository.repository}/releases/latest")
    return _release_info(key, payload)


def latest_nightly_release(emulator: str) -> ReleaseInfo:
    """Return an official rolling nightly release when the project exposes one.

    FBNeo currently publishes its rolling nightly under the release tag
    ``latest``. Other projects raise an error here rather than treating a
    stable release as a nightly build.
    """
    key = emulator.strip().lower()
    repository = REPOSITORIES[key]
    if not repository.nightly_release_tag:
        raise ValueError(
            f"O repositório oficial de {key} não expõe um release nightly "
            "padronizado nesta camada."
        )
    payload = _github_json(
        f"https://api.github.com/repos/{repository.repository}/releases/tags/{repository.nightly_release_tag}"
    )
    return _release_info(key, payload)


def choose_windows_x64_asset(release: ReleaseInfo) -> ReleaseAsset | None:
    """Choose a likely Windows x64 archive without hard-coding filenames."""
    preferred = ("x64", "x86_64", "amd64", "win64")
    candidates: list[ReleaseAsset] = []

    for asset in release.assets:
        name = asset.name.lower()
        is_windows = "windows" in name or "win" in name
        is_x64 = any(token in name for token in preferred)
        is_archive = name.endswith((".zip", ".7z", ".7zip"))
        if is_windows and is_x64 and is_archive:
            candidates.append(asset)

    return candidates[0] if candidates else None
