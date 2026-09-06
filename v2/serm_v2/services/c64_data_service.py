"""Aquisição do índice TOSEC de jogos Commodore C64 para o SERM V2."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ..runtime.paths import data_root

logger = logging.getLogger(__name__)


class C64DataError(RuntimeError):
    """Erro de aquisição ou validação da fonte C64."""


@dataclass(frozen=True, slots=True)
class C64ScanResult:
    """Resumo do scan do catálogo de jogos C64."""

    release: str
    dat_count: int
    game_categories: int
    source_hash: str
    raw_path: Path
    manifest_path: Path
    elapsed_seconds: float


class C64DataService:
    """Baixa o índice público do TOSEC e extrai somente DATs de jogos C64.

    Nesta primeira etapa não baixamos o pacote completo do TOSEC. O SERM
    registra o manifesto oficial da release e identifica exclusivamente os
    DATs que pertencem a ``Commodore C64 - Games``. Isso evita trazer
    Applications, Demos, Music, Graphics, Educational e demais categorias
    para o catálogo de jogos.
    """

    SOURCE_URL = "https://tosecdev.org/downloads/category/59-2025-03-13"
    RAW_PATH = data_root() / "sources" / "tosec" / "c64_games_source.html"
    MANIFEST_PATH = data_root() / "sources" / "tosec" / "c64_games_manifest.json"

    _DAT_RE = re.compile(
        r"Commodore C64 - Games(?: - [^<\r\n()]+)? \(TOSEC-[^<\r\n()]+\)\.dat"
    )
    _RELEASE_RE = re.compile(r"(?<!\d)(20\d{2}-\d{2}-\d{2})(?!\d)")

    def __init__(self, timeout: int = 120) -> None:
        self.timeout = timeout

    def _download(self) -> bytes:
        request = urllib.request.Request(
            self.SOURCE_URL,
            headers={"User-Agent": "SERM/2.0 (C64 DAT scanner)"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except Exception as exc:  # noqa: BLE001
            raise C64DataError(f"Falha ao baixar índice TOSEC C64: {exc}") from exc
        if not payload:
            raise C64DataError("O índice TOSEC C64 retornou conteúdo vazio.")
        return payload

    @classmethod
    def _parse(cls, payload: bytes) -> tuple[str, list[str]]:
        text = payload.decode("utf-8", errors="replace")
        release_match = cls._RELEASE_RE.search(text)
        release = release_match.group(1) if release_match else "desconhecida"
        names = sorted(set(cls._DAT_RE.findall(text)), key=str.casefold)
        if not names:
            raise C64DataError("Nenhum DAT 'Commodore C64 - Games' foi encontrado na fonte TOSEC.")
        return release, names

    def scan(self) -> C64ScanResult:
        started = time.perf_counter()
        payload = self._download()
        release, dat_names = self._parse(payload)
        source_hash = hashlib.sha256(payload).hexdigest()

        self.RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.RAW_PATH.write_bytes(payload)

        categories = sorted(
            {
                name.removeprefix("Commodore C64 - Games - ")
                .split(" [", 1)[0]
                .removesuffix(f" (TOSEC-v{release}_CM).dat")
                for name in dat_names
            },
            key=str.casefold,
        )
        manifest = {
            "source": "TOSEC",
            "source_url": self.SOURCE_URL,
            "release": release,
            "system": "Commodore C64",
            "scope": "Games",
            "media_policy": "single_media_priority",
            "dat_count": len(dat_names),
            "game_categories": categories,
            "dat_files": dat_names,
            "source_sha256": source_hash,
        }
        self.MANIFEST_PATH.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        elapsed = time.perf_counter() - started
        logger.info(
            "[C64-DAT] release=%s dats=%d categorias=%d tempo=%.2fs",
            release,
            len(dat_names),
            len(categories),
            elapsed,
        )
        return C64ScanResult(
            release=release,
            dat_count=len(dat_names),
            game_categories=len(categories),
            source_hash=source_hash,
            raw_path=self.RAW_PATH,
            manifest_path=self.MANIFEST_PATH,
            elapsed_seconds=elapsed,
        )


__all__ = ["C64DataError", "C64DataService", "C64ScanResult"]
