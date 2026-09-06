"""Aquisição e normalização da base WHDLoad do Amiberry."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..runtime.paths import data_root, database_path

logger = logging.getLogger(__name__)


class WHLoaderDataError(RuntimeError):
    """Erro de aquisição, validação ou persistência da base WHDLoad."""


@dataclass(frozen=True, slots=True)
class WHLoaderScanResult:
    """Resultado resumido da sincronização da base WHDLoad."""

    games: int
    slaves: int
    schema_version: str | None
    source_hash: str
    raw_path: Path
    elapsed_seconds: float


class WHLoaderDataService:
    """Baixa a base oficial publicada pelo projeto Amiberry e cria índice local."""

    SOURCE_URL = "https://db.amiberry.com/whdload_db.json"
    RAW_PATH = data_root() / "sources" / "amiberry" / "whdload_db.json"

    def __init__(self, db_path: Path | None = None, timeout: int = 120) -> None:
        self.db_path = (db_path or database_path()).expanduser().resolve()
        self.timeout = timeout

    @staticmethod
    def _bool(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, str):
            return int(value.strip().lower() in {"1", "true", "yes", "on"})
        return int(bool(value))

    @staticmethod
    def _text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _int(value: Any) -> int | None:
        try:
            return None if value is None else int(value)
        except (TypeError, ValueError):
            return None

    def _download(self) -> tuple[bytes, float]:
        started = time.perf_counter()
        request = urllib.request.Request(
            self.SOURCE_URL,
            headers={"User-Agent": "SERM/2.0 (WHLoader database)"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except Exception as exc:  # noqa: BLE001
            raise WHLoaderDataError(f"Falha ao baixar a base Amiberry: {exc}") from exc
        if not payload:
            raise WHLoaderDataError("A base Amiberry retornou conteúdo vazio.")
        return payload, time.perf_counter() - started

    def _parse(self, payload: bytes) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        try:
            document = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WHLoaderDataError(f"JSON WHDLoad inválido: {exc}") from exc
        if not isinstance(document, dict):
            raise WHLoaderDataError("A raiz da base WHDLoad deve ser um objeto JSON.")
        games = document.get("games")
        if not isinstance(games, list):
            raise WHLoaderDataError("A base WHDLoad não contém a lista 'games'.")
        valid = [game for game in games if isinstance(game, dict)]
        return document, valid

    def _deduplicate_games(self, games: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
        """Remove duplicatas da fonte sem perder slaves presentes em outra ocorrência.

        A tabela local possui UNIQUE(filename, sha1). Algumas versões da base
        Amiberry podem publicar o mesmo par mais de uma vez. Mantemos a primeira
        ocorrência como registro principal e mesclamos os slaves das ocorrências
        seguintes, evitando que um dado válido seja perdido.
        """
        unique: dict[tuple[str, str | None], dict[str, Any]] = {}
        duplicates = 0

        for game in games:
            filename = self._text(game.get("filename"))
            if not filename:
                continue
            key = (filename, self._text(game.get("sha1")))
            existing = unique.get(key)
            if existing is None:
                unique[key] = game
                continue

            duplicates += 1
            existing_slaves = existing.get("slaves")
            if not isinstance(existing_slaves, list):
                existing_slaves = []
                existing["slaves"] = existing_slaves

            incoming_slaves = game.get("slaves")
            if not isinstance(incoming_slaves, list):
                incoming_slaves = []

            known_slaves = {
                self._text(slave.get("filename"))
                for slave in existing_slaves
                if isinstance(slave, dict) and self._text(slave.get("filename"))
            }
            for slave in incoming_slaves:
                if not isinstance(slave, dict):
                    continue
                slave_name = self._text(slave.get("filename"))
                if slave_name and slave_name not in known_slaves:
                    existing_slaves.append(slave)
                    known_slaves.add(slave_name)

        return list(unique.values()), duplicates

    def _replace_database(
        self,
        document: dict[str, Any],
        games: list[dict[str, Any]],
        payload: bytes,
        source_hash: str,
        raw_path: Path,
    ) -> int:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(payload)
        now = datetime.now(UTC).isoformat()
        connection = sqlite3.connect(self.db_path, timeout=60.0)
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN")
            connection.execute("DELETE FROM whloader_slave")
            connection.execute("DELETE FROM whloader_game")
            slave_total = 0
            for game in games:
                hardware = game.get("hardware") if isinstance(game.get("hardware"), dict) else {}
                filename = self._text(game.get("filename")) or ""
                name = self._text(game.get("name")) or filename or "Unknown"
                if not filename:
                    continue
                slaves = game.get("slaves")
                if not isinstance(slaves, list):
                    slaves = []

                cursor = connection.execute(
                    """INSERT INTO whloader_game (
                        filename, sha1, name, subpath, slave_default, slave_count,
                        primary_control, port0, port1, chipset, cpu, fast_copper,
                        cpu_compatible, jit, screen_autoheight, screen_centerh,
                        screen_centerv, screen_height, screen_y_offset, line_doubling,
                        ntsc, sprites, source_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        filename,
                        self._text(game.get("sha1")),
                        name,
                        self._text(game.get("subpath")),
                        self._text(game.get("slave_default")),
                        len(slaves),
                        self._text(hardware.get("primary_control")),
                        self._text(hardware.get("port0")),
                        self._text(hardware.get("port1")),
                        self._text(hardware.get("chipset")),
                        self._text(hardware.get("cpu")),
                        self._bool(hardware.get("fast_copper")),
                        self._bool(hardware.get("cpu_compatible")),
                        self._bool(hardware.get("jit")),
                        self._bool(hardware.get("screen_autoheight")),
                        self._text(hardware.get("screen_centerh")),
                        self._text(hardware.get("screen_centerv")),
                        self._int(hardware.get("screen_height")),
                        self._int(hardware.get("screen_y_offset")),
                        self._bool(hardware.get("line_doubling")),
                        self._bool(hardware.get("ntsc")),
                        self._text(hardware.get("sprites")),
                        json.dumps(game, ensure_ascii=False, separators=(",", ":")),
                        now,
                    ),
                )
                game_id = int(cursor.lastrowid)
                for slave in slaves:
                    if not isinstance(slave, dict):
                        continue
                    slave_name = self._text(slave.get("filename"))
                    if not slave_name:
                        continue
                    connection.execute(
                        "INSERT OR IGNORE INTO whloader_slave(game_id, filename, datapath, custom_json) VALUES (?, ?, ?, ?)",
                        (
                            game_id,
                            slave_name,
                            self._text(slave.get("datapath")),
                            json.dumps(
                                slave.get("custom_fields", []),
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        ),
                    )
                    slave_total += 1
            connection.execute(
                """INSERT INTO whloader_database_meta(id, source_url, source_hash, schema_version, game_count, scanned_at, raw_path)
                   VALUES (1, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET source_url=excluded.source_url,
                   source_hash=excluded.source_hash, schema_version=excluded.schema_version,
                   game_count=excluded.game_count, scanned_at=excluded.scanned_at, raw_path=excluded.raw_path""",
                (
                    self.SOURCE_URL,
                    source_hash,
                    self._text(document.get("schema_version")),
                    len(games),
                    now,
                    str(raw_path),
                ),
            )
            connection.commit()
            return slave_total
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def scan(self) -> WHLoaderScanResult:
        """Baixa, valida, preserva e indexa a base WHDLoad atual."""
        started = time.perf_counter()
        payload, download_seconds = self._download()
        document, games = self._parse(payload)
        source_hash = hashlib.sha256(payload).hexdigest()
        games, duplicates = self._deduplicate_games(games)
        raw_path = self.RAW_PATH
        slaves = self._replace_database(document, games, payload, source_hash, raw_path)
        elapsed = time.perf_counter() - started
        logger.info(
            "[WHLOADER][SCAN] jogos=%d | duplicatas=%d | slaves=%d | sha256=%s | download=%.2fs | total=%.2fs",
            len(games),
            duplicates,
            slaves,
            source_hash,
            download_seconds,
            elapsed,
        )
        return WHLoaderScanResult(
            games=len(games),
            slaves=slaves,
            schema_version=self._text(document.get("schema_version")),
            source_hash=source_hash,
            raw_path=raw_path,
            elapsed_seconds=elapsed,
        )
