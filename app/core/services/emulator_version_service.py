"""Descoberta e comparação de versões dos emuladores suportados.

A camada separa deliberadamente a versão instalada da versão disponível no
GitHub. A descoberta local não inicia nenhum emulador. A consulta remota ao
GitHub só acontece quando solicitada explicitamente pela aplicação (por
exemplo, ao atualizar a Home ou iniciar uma atualização).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EmulatorVersionInfo:
    """Representa as versões instalada e disponível de um emulador."""

    emulator: str
    installed: str | None = None
    available: str | None = None
    release_tag: str | None = None
    release_url: str | None = None
    source: str | None = None
    status: str = "unknown"
    error: str | None = None


@dataclass(frozen=True, slots=True)
class EmulatorReleaseSpec:
    """Define como localizar o release oficial de um emulador."""

    emulator: str
    repository: str
    normalize_tag: Callable[[str], str | None]


class EmulatorVersionService:
    """Centraliza versão local, release oficial e comparação."""

    API_BASE = "https://api.github.com/repos"
    USER_AGENT = "MAME-Set-Builder/1.0"
    TIMEOUT = 8

    RELEASE_SPECS = {
        "mame": EmulatorReleaseSpec("mame", "mamedev/mame", lambda tag: _mame_version(tag)),
        "flycast": EmulatorReleaseSpec("flycast", "flyinghead/flycast", lambda tag: _numeric_version(tag)),
        "supermodel": EmulatorReleaseSpec("supermodel", "trzy/Supermodel", lambda tag: _supermodel_version(tag)),
        "fbneo": EmulatorReleaseSpec("fbneo", "finalburnneo/FBNeo", lambda tag: _fbneo_version(tag)),
    }

    def __init__(self, opener: Callable[..., object] | None = None) -> None:
        self._opener = opener or urlopen

    def get_installed_version(self, emulator: str, root: Path | None = None, executable: Path | None = None) -> str | None:
        """Obtém a versão instalada sem consultar a Internet ou executar instaladores."""
        name = emulator.casefold()
        if name == "mame":
            # A versão oficial do MAME deve continuar sendo obtida pelo
            # EmulatorDiscoveryService a partir do mame.exe real.
            return None
        if root is None:
            return None
        if name == "fbneo":
            return self._read_fbneo_version(root / "config" / "fbneo64.ini")
        if name == "supermodel":
            return self._read_supermodel_version(root)
        if name == "flycast":
            return self._read_flycast_version(root)
        return None

    def get_latest_release(self, emulator: str) -> EmulatorVersionInfo:
        """Consulta o último release oficial publicado no GitHub."""
        name = emulator.casefold()
        spec = self.RELEASE_SPECS.get(name)
        if spec is None:
            return EmulatorVersionInfo(name, error="emulador não suportado")

        url = f"{self.API_BASE}/{spec.repository}/releases/latest"
        logger.info("Emulator version: consultando último release | emulator=%s | url=%s", name, url)
        try:
            payload = self._get_json(url)
            tag = str(payload.get("tag_name") or "").strip()
            if not tag:
                raise ValueError("GitHub não retornou tag_name")
            version = spec.normalize_tag(tag)
            if not version:
                raise ValueError(f"tag do release não reconhecida: {tag}")
            release_url = str(payload.get("html_url") or "") or None
            logger.info(
                "Emulator version: release encontrado | emulator=%s | tag=%s | version=%s",
                name,
                tag,
                version,
            )
            return EmulatorVersionInfo(
                emulator=name,
                available=version,
                release_tag=tag,
                release_url=release_url,
                source="github_release",
                status="available",
            )
        except (OSError, HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Emulator version: falha consultando release | emulator=%s | error=%s", name, exc)
            return EmulatorVersionInfo(name, source="github_release", status="error", error=str(exc))

    def check(self, emulator: str, installed: str | None = None, root: Path | None = None) -> EmulatorVersionInfo:
        """Combina versão instalada e último release e calcula o estado."""
        name = emulator.casefold()
        local = installed if installed is not None else self.get_installed_version(name, root=root)
        remote = self.get_latest_release(name)
        status = self.compare(local, remote.available)
        return EmulatorVersionInfo(
            emulator=name,
            installed=local,
            available=remote.available,
            release_tag=remote.release_tag,
            release_url=remote.release_url,
            source=remote.source,
            status=status if remote.status != "error" else "remote_error",
            error=remote.error,
        )

    @staticmethod
    def compare(installed: str | None, available: str | None) -> str:
        """Compara versões normalizadas sem afirmar igualdade quando faltam dados."""
        if not installed:
            return "installed_unknown"
        if not available:
            return "available_unknown"
        a = _version_key(installed)
        b = _version_key(available)
        if a is None or b is None:
            return "unknown"
        if a < b:
            return "update_available"
        if a == b:
            return "up_to_date"
        return "installed_newer"

    def _get_json(self, url: str) -> dict[str, object]:
        """Baixa JSON do GitHub sem shell e com timeout limitado."""
        request = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": self.USER_AGENT,
            },
            method="GET",
        )
        with self._opener(request, timeout=self.TIMEOUT) as response:  # type: ignore[union-attr]
            raw = response.read()
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("resposta do GitHub não é um objeto JSON")
        return data

    @staticmethod
    def _read_fbneo_version(path: Path) -> str | None:
        """Extrai a versão do cabeçalho oficial do fbneo64.ini."""
        if not path.is_file():
            return None
        try:
            text = path.read_text(encoding="utf-8-sig", errors="ignore")
        except OSError:
            return None
        match = re.search(r"FinalBurn\s+Neo\s+v([0-9]+(?:\.[0-9]+)+)", text, re.IGNORECASE)
        return match.group(1) if match else None

    @staticmethod
    def _read_supermodel_version(root: Path) -> str | None:
        """Extrai a versão datada do Supermodel de metadados locais conhecidos."""
        pattern = re.compile(r"v?([0-9]+\.[0-9]+[a-z]-[0-9]{8})", re.IGNORECASE)
        for name in ("version.txt", "VERSION", "version", "build.txt"):
            path = root / name
            if not path.is_file():
                continue
            try:
                match = pattern.search(path.read_text(encoding="utf-8-sig", errors="ignore"))
            except OSError:
                continue
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _read_flycast_version(root: Path) -> str | None:
        """Lê metadados de versão que possam acompanhar uma build do Flycast."""
        pattern = re.compile(r"v?([0-9]+\.[0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
        for name in ("VERSION", "version.txt", "VERSION.txt", "build.txt"):
            path = root / name
            if not path.is_file():
                continue
            try:
                match = pattern.search(path.read_text(encoding="utf-8-sig", errors="ignore"))
            except OSError:
                continue
            if match:
                return match.group(1)
        return None


def _mame_version(tag: str) -> str | None:
    """Converte tags mameXXXX para a versão numérica correspondente."""
    match = re.fullmatch(r"mame(\d{4})", tag.strip(), re.IGNORECASE)
    if not match:
        return None
    digits = match.group(1)
    return f"{int(digits[:2])}.{int(digits[2:])}"


def _numeric_version(tag: str) -> str | None:
    """Normaliza tags numéricas como v2.7 ou v2.7.1."""
    match = re.search(r"v?(\d+\.\d+(?:\.\d+)*)", tag.strip(), re.IGNORECASE)
    return match.group(1) if match else None


def _supermodel_version(tag: str) -> str | None:
    """Remove o prefixo v e o identificador git do release do Supermodel."""
    match = re.search(r"v?(\d+\.\d+[a-z]-\d{8})", tag.strip(), re.IGNORECASE)
    return match.group(1) if match else None


def _fbneo_version(tag: str) -> str | None:
    """Normaliza versões numéricas do FBNeo quando o release as disponibiliza."""
    return _numeric_version(tag)


def _version_key(value: str) -> tuple[int, ...] | None:
    """Cria uma chave numérica para comparação das versões suportadas."""
    match = re.search(r"(\d+(?:\.\d+)+)", value)
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))
