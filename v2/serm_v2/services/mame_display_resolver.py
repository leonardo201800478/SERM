"""Resolução de display do MAME com fontes externas e precedência explícita."""

from __future__ import annotations

from .sqlite_utils import require_lastrowid

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..runtime.paths import database_path


class MameDisplayResolverError(RuntimeError):
    """Erro ao importar fontes ou gerar perfis de display."""


@dataclass(frozen=True, slots=True)
class ExternalDisplayFact:
    """Fato de display obtido de resolução.ini/Vsync.ini."""

    machine_name: str
    width: int | None = None
    height: int | None = None
    refresh_hz: float | None = None
    orientation: str | None = None
    pixel_aspect_x: int | None = None
    pixel_aspect_y: int | None = None
    raw_value: str = ""
    line_number: int | None = None


class MameDisplayResolver:
    """Importa fallbacks e resolve um Machine Display Profile determinístico."""

    PARSER_VERSION = "1.0"

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or database_path()

    def import_fallback(self, path: str | Path, source_name: str) -> int:
        """Importa ``resolution.ini`` ou ``Vsync.ini`` preservando valor bruto."""
        source_path = Path(path).expanduser().resolve()
        if not source_path.is_file():
            raise MameDisplayResolverError(f"Arquivo não encontrado: {source_path}")
        text = source_path.read_text(encoding="utf-8", errors="replace")
        source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        facts = self._parse_external(text, source_name)
        now = datetime.now(UTC).isoformat()
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            row = connection.execute(
                "SELECT id FROM emulator_definition WHERE slug='mame'"
            ).fetchone()
            if row is None:
                raise MameDisplayResolverError("emulator_definition('mame') não existe.")
            emulator_id = int(row[0])
            connection.execute(
                """INSERT INTO mame_display_source
                (emulator_id, source_name, source_path, source_hash, imported_at, parser_version, row_count, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'imported')""",
                (
                    emulator_id,
                    source_name,
                    str(source_path),
                    source_hash,
                    now,
                    self.PARSER_VERSION,
                    len(facts),
                ),
            )
            source_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            for fact in facts:
                connection.execute(
                    """INSERT INTO mame_external_display_fact
                    (source_id,machine_name,resolution_width,resolution_height,refresh_hz,refresh_raw,
                     orientation,pixel_aspect_x,pixel_aspect_y,raw_value,line_number)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (fact.machine_name,)
                    if False
                    else (
                        source_id,
                        fact.machine_name,
                        fact.width,
                        fact.height,
                        fact.refresh_hz,
                        str(fact.refresh_hz) if fact.refresh_hz is not None else None,
                        fact.orientation,
                        fact.pixel_aspect_x,
                        fact.pixel_aspect_y,
                        fact.raw_value,
                        fact.line_number,
                    ),
                )
            connection.commit()
        return source_id

    def resolve_all(self, *, profile_version: str = "1.0") -> dict[str, int]:
        """Resolve todos os displays do último ListXML usando fallback por campo."""
        now = datetime.now(UTC).isoformat()
        stats = {"machines": 0, "profiles": 0, "fallbacks": 0, "missing": 0, "comparisons": 0}
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            latest = connection.execute(
                "SELECT id FROM mame_listxml_import ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if latest is None:
                raise MameDisplayResolverError("Nenhum ListXML foi importado.")
            import_id = int(latest[0])
            machines = connection.execute(
                "SELECT id,name FROM mame_machine WHERE import_id=? ORDER BY name", (import_id,)
            ).fetchall()
            sources = {
                row[0]: row[1]
                for row in connection.execute(
                    """SELECT source_name,id FROM mame_display_source
                    WHERE id IN (SELECT MAX(id) FROM mame_display_source GROUP BY source_name)"""
                ).fetchall()
            }
            facts: dict[str, dict[str, tuple]] = {}
            for source_name, source_id in sources.items():
                facts[source_name] = {
                    row[0]: row[1:]
                    for row in connection.execute(
                        """SELECT machine_name,resolution_width,resolution_height,refresh_hz,refresh_raw,
                        orientation,pixel_aspect_x,pixel_aspect_y,raw_value,line_number
                        FROM mame_external_display_fact WHERE source_id=?""",
                        (source_id,),
                    ).fetchall()
                }

            for machine_id, machine_name in machines:
                stats["machines"] += 1
                displays = connection.execute(
                    """SELECT id,width,height,refresh_hz,rotate FROM mame_display
                    WHERE machine_id=? ORDER BY id""",
                    (machine_id,),
                ).fetchall()
                if not displays:
                    stats["missing"] += 1
                    self._record_missing(connection, machine_id, machine_name, now)
                    continue
                for display_id, width, height, refresh, rotate in displays:
                    resolution_fact = self._fact(facts, "resolution.ini", machine_name)
                    vsync_fact = self._fact(facts, "Vsync.ini", machine_name)
                    resolved_width, res_source = width, "listxml"
                    resolved_height, _ = height, "listxml"
                    if resolved_width is None or resolved_height is None:
                        if (
                            resolution_fact
                            and resolution_fact[0] is not None
                            and resolution_fact[1] is not None
                        ):
                            resolved_width, resolved_height = resolution_fact[0], resolution_fact[1]
                            res_source = "resolution.ini"
                    resolved_refresh, refresh_source = refresh, "listxml"
                    if resolved_refresh is None and vsync_fact and vsync_fact[2] is not None:
                        resolved_refresh, refresh_source = vsync_fact[2], "Vsync.ini"
                    resolved_orientation = self._orientation(rotate)
                    orientation_source = "listxml" if rotate is not None else "resolution.ini"
                    if rotate is None and resolution_fact and resolution_fact[4]:
                        resolved_orientation = resolution_fact[4]
                    pixel_x = resolution_fact[5] if resolution_fact else None
                    pixel_y = resolution_fact[6] if resolution_fact else None
                    pixel_source = "resolution.ini" if pixel_x and pixel_y else "missing"
                    fallback = int(
                        res_source != "listxml"
                        or refresh_source != "listxml"
                        or orientation_source != "listxml"
                        or pixel_source != "missing"
                    )
                    status = (
                        "resolved"
                        if resolved_width and resolved_height and resolved_refresh
                        else "partial"
                    )
                    if not resolved_width or not resolved_height or resolved_refresh is None:
                        stats["missing"] += 1
                    if fallback:
                        stats["fallbacks"] += 1
                    connection.execute(
                        """INSERT INTO mame_display_resolution
                        (machine_id,display_id,width,height,refresh_hz,orientation,pixel_aspect_x,pixel_aspect_y,
                         resolution_source,refresh_source,orientation_source,pixel_aspect_source,
                         resolution_confidence,refresh_confidence,orientation_confidence,pixel_aspect_confidence,
                         fallback_used,compared_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(machine_id,display_id) DO UPDATE SET
                        width=excluded.width,height=excluded.height,refresh_hz=excluded.refresh_hz,
                        orientation=excluded.orientation,pixel_aspect_x=excluded.pixel_aspect_x,
                        pixel_aspect_y=excluded.pixel_aspect_y,resolution_source=excluded.resolution_source,
                        refresh_source=excluded.refresh_source,orientation_source=excluded.orientation_source,
                        pixel_aspect_source=excluded.pixel_aspect_source,resolution_confidence=excluded.resolution_confidence,
                        refresh_confidence=excluded.refresh_confidence,orientation_confidence=excluded.orientation_confidence,
                        pixel_aspect_confidence=excluded.pixel_aspect_confidence,fallback_used=excluded.fallback_used,
                        compared_at=excluded.compared_at""",
                        (
                            machine_id,
                            display_id,
                            resolved_width,
                            resolved_height,
                            resolved_refresh,
                            resolved_orientation,
                            pixel_x,
                            pixel_y,
                            res_source,
                            refresh_source,
                            orientation_source,
                            pixel_source,
                            "authoritative" if res_source == "listxml" else "fallback",
                            "authoritative" if refresh_source == "listxml" else "fallback",
                            "authoritative" if orientation_source == "listxml" else "fallback",
                            "fallback" if pixel_source != "missing" else "missing",
                            fallback,
                            now,
                        ),
                    )
                    self._compare(
                        connection,
                        machine_id,
                        display_id,
                        width,
                        height,
                        refresh,
                        resolution_fact,
                        vsync_fact,
                        now,
                    )
                    connection.execute(
                        """INSERT INTO mame_machine_display_profile
                        (machine_id,display_id,profile_version,width,height,refresh_hz,orientation,pixel_aspect_x,pixel_aspect_y,
                         source_resolution,source_refresh,source_orientation,source_pixel_aspect,fallback_used,status,generated_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(machine_id,display_id,profile_version) DO UPDATE SET
                        width=excluded.width,height=excluded.height,refresh_hz=excluded.refresh_hz,
                        orientation=excluded.orientation,pixel_aspect_x=excluded.pixel_aspect_x,
                        pixel_aspect_y=excluded.pixel_aspect_y,source_resolution=excluded.source_resolution,
                        source_refresh=excluded.source_refresh,source_orientation=excluded.source_orientation,
                        source_pixel_aspect=excluded.source_pixel_aspect,fallback_used=excluded.fallback_used,
                        status=excluded.status,generated_at=excluded.generated_at""",
                        (
                            machine_id,
                            display_id,
                            profile_version,
                            resolved_width,
                            resolved_height,
                            resolved_refresh,
                            resolved_orientation,
                            pixel_x,
                            pixel_y,
                            res_source,
                            refresh_source,
                            orientation_source,
                            pixel_source,
                            fallback,
                            status,
                            now,
                        ),
                    )
                    stats["profiles"] += 1
            connection.commit()
        return stats

    @staticmethod
    def _fact(
        facts: dict[str, dict[str, tuple]], source_name: str, machine_name: str
    ) -> tuple | None:
        """Obtém o fato mais recente de uma fonte por nome curto da máquina."""
        return facts.get(source_name, {}).get(machine_name)

    @staticmethod
    def _orientation(rotate: str | None) -> str | None:
        """Converte rotação ListXML em orientação lógica sem perder o valor original."""
        if rotate is None:
            return None
        return "vertical" if rotate in {"90", "270"} else "horizontal"

    def _record_missing(self, connection, machine_id: int, machine_name: str, now: str) -> None:
        """Registra uma máquina sem display ListXML para auditoria posterior."""
        connection.execute(
            """INSERT INTO mame_machine_display_profile
            (machine_id,display_id,profile_version,width,height,refresh_hz,orientation,
             source_resolution,source_refresh,source_orientation,source_pixel_aspect,
             fallback_used,status,generated_at)
            VALUES(?,NULL,'1.0',NULL,NULL,NULL,NULL,'missing','missing','missing','missing',0,'missing',?)
            ON CONFLICT(machine_id,display_id,profile_version) DO UPDATE SET
            status='missing',generated_at=excluded.generated_at""",
            (machine_id, now),
        )

    def _compare(
        self,
        connection,
        machine_id,
        display_id,
        width,
        height,
        refresh,
        resolution_fact,
        vsync_fact,
        now,
    ):
        """Registra divergências campo a campo entre ListXML e fallbacks."""
        checks = [
            (
                "resolution",
                f"{width}x{height}" if width and height else None,
                f"{resolution_fact[0]}x{resolution_fact[1]}"
                if resolution_fact and resolution_fact[0] and resolution_fact[1]
                else None,
                "resolution.ini",
            ),
            (
                "refresh",
                str(refresh) if refresh is not None else None,
                str(vsync_fact[2]) if vsync_fact and vsync_fact[2] is not None else None,
                "Vsync.ini",
            ),
        ]
        for field, a, b, source_b in checks:
            if b is None:
                result = "missing_fallback"
            elif a is None:
                result = "listxml_missing"
            elif a == b:
                result = "match"
            else:
                result = "mismatch"
            connection.execute(
                """INSERT INTO mame_display_comparison
                (machine_id,display_id,source_a,source_b,field_name,value_a,value_b,result,detail,compared_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (machine_id, display_id, "ListXML", source_b, field, a, b, result, None, now),
            )

    @classmethod
    def _parse_external(cls, text: str, source_name: str) -> list[ExternalDisplayFact]:
        """Aceita formatos INI, ``name=value`` e ``name widthxheight``."""
        facts: dict[str, dict[str, object]] = {}
        section: str | None = None
        for line_number, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip()
                facts.setdefault(section, {})
                continue
            key, value = cls._split_line(line)
            if key is None:
                continue
            machine = section or key
            payload = facts.setdefault(machine, {})
            if section:
                payload[key.lower()] = value
            else:
                payload["value"] = value
                payload["line"] = line_number
        result: list[ExternalDisplayFact] = []
        for machine, payload in facts.items():
            raw = str(payload.get("value", ""))
            width, height = cls._resolution(payload.get("resolution") or payload.get("value"))
            refresh = cls._number(payload.get("refresh"))
            if refresh is None and source_name.lower() == "vsync.ini":
                refresh = cls._number(payload.get("value"))
            orientation = str(payload.get("orientation")) if payload.get("orientation") else None
            aspect = str(payload.get("pixel_aspect")) if payload.get("pixel_aspect") else None
            ax, ay = cls._aspect(aspect)
            line_value = payload.get("line")
            line_number = line_value if isinstance(line_value, int) else None
            result.append(
                ExternalDisplayFact(
                    machine, width, height, refresh, orientation, ax, ay, raw, line_number
                )
            )
        return result

    @staticmethod
    def _split_line(line: str) -> tuple[str | None, str | None]:
        """Separa chave/valor aceitando ``=`` ou whitespace."""
        if "=" in line:
            key, value = line.split("=", 1)
            return key.strip(), value.strip()
        parts = re.split(r"\s+", line, maxsplit=1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        return None, None

    @staticmethod
    def _resolution(value: object) -> tuple[int | None, int | None]:
        """Extrai ``width x height`` de uma string livre."""
        if value is None:
            return None, None
        match = re.search(r"(\d+)\s*[xX×]\s*(\d+)", str(value))
        return (int(match.group(1)), int(match.group(2))) if match else (None, None)

    @staticmethod
    def _number(value: object) -> float | None:
        """Extrai um número decimal de uma configuração externa."""
        if value is None:
            return None
        match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
        return float(match.group(0)) if match else None

    @staticmethod
    def _aspect(value: str | None) -> tuple[int | None, int | None]:
        """Extrai um aspecto ``X:Y``."""
        if not value:
            return None, None
        match = re.search(r"(\d+)\s*[:/]\s*(\d+)", value)
        return (int(match.group(1)), int(match.group(2))) if match else (None, None)


__all__ = ["ExternalDisplayFact", "MameDisplayResolver", "MameDisplayResolverError"]
