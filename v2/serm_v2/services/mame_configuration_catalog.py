"""Catálogo de configurações MAME derivado do executável configurado.

A V2 não mantém uma lista paralela de opções MAME como fonte de verdade. O
executável selecionado pelo usuário é consultado com ``-showconfig`` e
``-showusage``; os resultados são normalizados para o banco de configurações.
A documentação oficial é usada como referência sem substituir a versão real
instalada.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..runtime.paths import data_root, database_path


class MameConfigurationError(RuntimeError):
    """Erro ao consultar ou persistir as opções de configuração do MAME."""


@dataclass(frozen=True, slots=True)
class MameOption:
    """Representa uma opção descoberta no ``-showusage`` do MAME."""

    key: str
    description: str
    category: str
    value_type: str
    control_type: str
    default_value: str | None
    choices: tuple[str, ...] = ()


class MameConfigurationCatalog:
    """Consulta o MAME configurado e atualiza o catálogo de opções da V2."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    DB_FILE = database_path()
    RAW_ROOT = data_root() / "mame" / "metadata" / "configuration"

    CATEGORY_MAP = {
        "Core Search Path Options": ("paths", "configuration"),
        "Core Output Directory Options": ("paths", "configuration"),
        "Core State/Playback Options": ("system", "configuration"),
        "Core Performance Options": ("performance", "configuration"),
        "Core Rotation Options": ("video", "configuration"),
        "Core Video Options": ("video", "configuration"),
        "Core Full Screen Options": ("video", "configuration"),
        "Core Per-Window Video Options": ("video", "configuration"),
        "Core Per-Window Options": ("video", "configuration"),
        "Core Artwork Options": ("visuals", "shaders_artworks"),
        "Core Screen Options": ("visuals", "shaders_artworks"),
        "Core Vector Options": ("visuals", "shaders_artworks"),
        "Core Video OpenGL Debugging Options": ("visuals", "shaders_artworks"),
        "Core Video OpenGL Feature Options": ("visuals", "shaders_artworks"),
        "Core Video OpenGL GLSL Options": ("visuals", "shaders_artworks"),
        "Core Sound Options": ("audio", "configuration"),
        "Core Input Options": ("input", "configuration"),
        "Core Input Automatic Enable Options": ("input", "configuration"),
        "Core Debugging Options": ("debug", "configuration"),
        "Debugging Options": ("debug", "configuration"),
        "Core Communication Options": ("system", "configuration"),
        "Core Misc Options": ("system", "configuration"),
        "Scripting Options": ("system", "configuration"),
        "HTTP Server Options": ("system", "configuration"),
        "OSD-related Options": ("system", "configuration"),
        "Windows Performance Options": ("performance", "configuration"),
        "Windows Full Screen Options": ("video", "configuration"),
        "Windows Input Device Options": ("input", "configuration"),
        "SDL Performance Options": ("performance", "configuration"),
        "SDL Video Options": ("video", "configuration"),
        "SDL Video Soft-Specific Options": ("video", "configuration"),
        "SDL Keyboard Mapping": ("input", "configuration"),
        "SDL Input Options": ("input", "configuration"),
        "SDL Lightgun Mapping": ("input", "configuration"),
        "SDL Low-level Driver Options": ("video", "configuration"),
    }

    BOOL_RE = re.compile(r"^\[no\](.+)$")
    OPTION_RE = re.compile(r"^\s*-{1,2}([^\s]+)(?:\s+(.*))?$")
    CHOICE_RE = re.compile(r"[<(]([^>)]*)[>)]")

    def configured_executable(self) -> Path:
        """Retorna o executável MAME escolhido explicitamente na guia Diretórios."""
        try:
            data = json.loads(self.PATHS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise MameConfigurationError("Não foi possível ler emulator_paths.json.") from exc
        raw = data.get("mame_executable")
        if not isinstance(raw, str) or not raw.strip():
            raise MameConfigurationError("Nenhum mame.exe foi configurado em Diretórios.")
        executable = Path(raw).expanduser().resolve()
        if not executable.is_file():
            raise MameConfigurationError(f"Executável MAME não encontrado: {executable}")
        return executable

    def refresh(self, *, timeout: float = 30.0) -> dict[str, object]:
        """Consulta versão/configuração/uso e atualiza o catálogo de opções."""
        executable = self.configured_executable()
        version = self._run(executable, ["-version"], timeout)[0].strip()
        showconfig = self._run(executable, ["-showconfig"], timeout)[0]
        defaults = self._run(executable, ["-noreadconfig", "-showconfig"], timeout)[0]
        usage = self._run(executable, ["-showusage"], timeout)[0]

        self.RAW_ROOT.mkdir(parents=True, exist_ok=True)
        (self.RAW_ROOT / "showconfig.ini").write_text(showconfig, encoding="utf-8", newline="\n")
        (self.RAW_ROOT / "defaults.ini").write_text(defaults, encoding="utf-8", newline="\n")
        (self.RAW_ROOT / "showusage.txt").write_text(usage, encoding="utf-8", newline="\n")

        current = self._parse_config(showconfig)
        default_values = self._parse_config(defaults)
        options = self._parse_usage(usage, current, default_values)
        now = datetime.now(UTC).isoformat()
        digest = hashlib.sha256((showconfig + defaults + usage).encode("utf-8")).hexdigest()

        self._persist(executable, version, options, now, digest)
        return {
            "executable": executable,
            "version": version,
            "option_count": len(options),
            "raw_root": self.RAW_ROOT,
            "output_hash": digest,
        }

    @staticmethod
    def _run(executable: Path, args: list[str], timeout: float) -> tuple[str, str]:
        """Executa o MAME sem shell e retorna stdout/stderr validados."""
        try:
            result = subprocess.run(
                [str(executable), *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                timeout=timeout,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MameConfigurationError(f"Falha ao executar MAME {' '.join(args)}: {exc}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise MameConfigurationError(
                f"MAME retornou código {result.returncode} em {' '.join(args)}: {detail}"
            )
        return result.stdout, result.stderr

    @staticmethod
    def _parse_config(text: str) -> dict[str, str]:
        """Extrai pares ``opção valor`` do formato produzido por ``-showconfig``."""
        values: dict[str, str] = {}
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split(None, 1)
            if len(parts) == 2:
                values[parts[0]] = parts[1].strip()
        return values

    @classmethod
    def _parse_usage(
        cls,
        text: str,
        current: dict[str, str],
        defaults: dict[str, str],
    ) -> list[MameOption]:
        """Extrai opções, grupos, descrições e choices do ``-showusage``."""
        result: list[MameOption] = []
        current_category = "Core Misc Options"
        pending_key: str | None = None
        pending_spec = ""
        pending_description: list[str] = []
        pending_boolean = False
        seen: set[str] = set()

        def flush() -> None:
            nonlocal pending_key, pending_spec, pending_description, pending_boolean
            if pending_key is None:
                return
            canonical = pending_key.lstrip("-")
            value = current.get(canonical, defaults.get(canonical))
            if canonical and canonical not in seen:
                choices = cls._extract_choices(pending_spec)
                if pending_boolean:
                    value_type, control = "bool", "checkbox"
                elif choices:
                    value_type, control = "enum", "combobox"
                elif canonical.endswith("path") or canonical.endswith("_directory"):
                    value_type, control = "path", "path"
                elif value is not None and cls._is_number(value):
                    value_type, control = "number", "spinbox"
                else:
                    value_type, control = "string", "text"
                result.append(
                    MameOption(
                        key=canonical,
                        description=" ".join(pending_description).strip(),
                        category=current_category,
                        value_type=value_type,
                        control_type=control,
                        default_value=defaults.get(canonical, value),
                        choices=choices,
                    )
                )
                seen.add(canonical)
            pending_key = None
            pending_spec = ""
            pending_description = []
            pending_boolean = False

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if not line.startswith((" ", "\t")) and stripped.endswith("Options"):
                flush()
                current_category = stripped
                continue
            match = cls.OPTION_RE.match(line)
            if match:
                flush()
                token = match.group(1)
                spec = match.group(2) or ""
                token = token.split("/", 1)[0]
                pending_boolean = token.startswith("[no]")
                if pending_boolean:
                    token = token[4:]
                pending_key = token
                pending_spec = spec
                continue
            if pending_key is not None:
                pending_description.append(stripped)
        flush()
        return result

    @classmethod
    def _extract_choices(cls, spec: str) -> tuple[str, ...]:
        """Extrai alternativas declaradas diretamente na assinatura da opção."""
        if not spec:
            return ()
        match = cls.CHOICE_RE.search(spec)
        if not match:
            return ()
        raw = match.group(1)
        values = tuple(part.strip().strip("`") for part in raw.split("|") if part.strip())
        return values

    @staticmethod
    def _is_number(value: str) -> bool:
        """Indica se um valor descoberto pode ser tratado como numérico."""
        try:
            float(value)
            return True
        except ValueError:
            return False

    def _persist(
        self,
        executable: Path,
        version: str,
        options: list[MameOption],
        observed_at: str,
        output_hash: str,
    ) -> None:
        """Atualiza opções sem apagar perfis ou valores definidos pelo usuário."""
        self.DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.DB_FILE) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            self._ensure_schema(connection)
            emulator_id = connection.execute(
                "SELECT id FROM emulator_definition WHERE slug='mame'"
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO config_observation
                (emulator_id, executable, version, observed_at, command, output_hash, status, raw_output_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (emulator_id, str(executable), version, observed_at, "-showconfig -noreadconfig -showusage", output_hash, "validated", str(self.RAW_ROOT)),
            )
            group_cache: dict[str, int] = {}
            for order, option in enumerate(options):
                group_slug, surface = self.CATEGORY_MAP.get(option.category, ("system", "configuration"))
                group_id = group_cache.get(group_slug)
                if group_id is None:
                    row = connection.execute(
                        "SELECT id FROM config_group WHERE emulator_id=? AND slug=?",
                        (emulator_id, group_slug),
                    ).fetchone()
                    if row is None:
                        connection.execute(
                            "INSERT INTO config_group(emulator_id, slug, name, description, sort_order) VALUES (?, ?, ?, ?, ?)",
                            (emulator_id, group_slug, group_slug.replace("_", " ").title(), None, order),
                        )
                        row = connection.execute("SELECT last_insert_rowid()").fetchone()
                    group_id = int(row[0])
                    group_cache[group_slug] = group_id
                connection.execute(
                    """INSERT INTO config_option
                    (emulator_id, group_id, key, label, description, value_type, control_type,
                     default_value, scope_slug, surface, advanced, source_kind, source_version,
                     source_reference, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'global', ?, ?, 'emulator', ?, ?, ?)
                    ON CONFLICT(emulator_id, key) DO UPDATE SET
                        group_id=excluded.group_id,
                        description=excluded.description,
                        value_type=excluded.value_type,
                        control_type=excluded.control_type,
                        default_value=excluded.default_value,
                        surface=excluded.surface,
                        source_version=excluded.source_version,
                        source_reference=excluded.source_reference,
                        sort_order=excluded.sort_order""",
                    (
                        emulator_id, group_id, option.key, option.key, option.description,
                        option.value_type, option.control_type, option.default_value,
                        surface, 0, version, "mame -showusage", order,
                    ),
                )
                option_id = connection.execute(
                    "SELECT id FROM config_option WHERE emulator_id=? AND key=?",
                    (emulator_id, option.key),
                ).fetchone()[0]
                connection.execute("DELETE FROM config_option_value WHERE option_id=?", (option_id,))
                for value_order, choice in enumerate(option.choices):
                    connection.execute(
                        """INSERT INTO config_option_value
                        (option_id, value, label, description, sort_order, is_default)
                        VALUES (?, ?, ?, NULL, ?, ?)""",
                        (option_id, choice, choice, value_order, int(choice == option.default_value)),
                    )
            connection.commit()

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        """Garante que a migration de configuração foi aplicada ao banco atual."""
        migration = Path(__file__).resolve().parents[1] / "database" / "migrations" / "001_configuration_schema.sql"
        if not migration.is_file():
            raise MameConfigurationError(f"Migration não encontrada: {migration}")
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='config_option'"
        ).fetchone()
        if row is None:
            connection.executescript(migration.read_text(encoding="utf-8"))


__all__ = ["MameConfigurationCatalog", "MameConfigurationError", "MameOption"]
