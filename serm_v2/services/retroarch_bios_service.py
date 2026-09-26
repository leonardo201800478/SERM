"""RetroArch-specific BIOS validation from installed libretro .info files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from .ares_firmware_service import (
    AresFirmwareEntry,
    AresFirmwareScan,
    AresFirmwareService,
)


class RetroArchBiosError(RuntimeError):
    """Erro de leitura/validação do contrato BIOS de um core RetroArch."""


class RetroArchBiosService:
    """Valida BIOS do RetroArch usando os .info instalados pelos cores.

    O .info é a autoridade estrutural: caminho relativo e opcionalidade.
    O catálogo RetroBIOS fornece hashes/metadados quando houver correspondência.
    """

    INFO_DIR_NAME = "info"
    INFO_SUFFIX = "_libretro.info"
    _KEY_VALUE = re.compile(r"^([A-Za-z0-9_]+)\\s*=\\s*"(.*)"$")

    @classmethod
    def _info_directory(cls, system_directory: str | Path) -> Path:
        root = Path(system_directory).expanduser().resolve()
        candidates = (root.parent / cls.INFO_DIR_NAME, root / cls.INFO_DIR_NAME)
        for candidate in candidates:
            if candidate.is_dir():
                return candidate
        raise RetroArchBiosError(
            f"Diretório 'info' do RetroArch não encontrado para {root}."
        )

    @classmethod
    def _parse_info(cls, path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise RetroArchBiosError(f"Não foi possível ler {path}: {exc}") from exc
        for raw in lines:
            line = raw.strip()
            match = cls._KEY_VALUE.match(line)
            if match:
                values[match.group(1)] = match.group(2).replace("\\n", "\n")
            elif "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"')
        return values

    @classmethod
    def _firmware_from_info(
        cls,
        info_path: Path,
        values: dict[str, str],
        catalog_entries: tuple[AresFirmwareEntry, ...],
    ) -> list[AresFirmwareEntry]:
        try:
            count = int(values.get("firmware_count", "0"))
        except ValueError:
            count = 0
        if count <= 0:
            return []

        profile_id = info_path.stem.removesuffix("_libretro").casefold()
        catalog = [
            entry for entry in catalog_entries
            if entry.profile_id.casefold() == profile_id
        ]
        result: list[AresFirmwareEntry] = []
        for index in range(count):
            path_value = values.get(f"firmware{index}_path", "").replace("\\", "/").strip()
            if not path_value:
                continue
            normalized = Path(path_value).as_posix()
            name = Path(normalized).name
            optional = values.get(f"firmware{index}_opt", "false").casefold() == "true"
            desc = values.get(f"firmware{index}_desc", name)
            matches = [
                entry for entry in catalog
                if entry.output_path.casefold() == normalized.casefold()
                or Path(entry.output_path).name.casefold() == name.casefold()
            ]
            base = matches[0] if matches else None
            result.append(
                AresFirmwareEntry(
                    name=name,
                    system=values.get("systemname", profile_id),
                    description=desc,
                    required=not optional,
                    sha256=base.sha256 if base else "",
                    size=base.size if base else None,
                    sha1=base.sha1 if base else "",
                    md5=base.md5 if base else "",
                    crc32=base.crc32 if base else "",
                    validation=base.validation if base else (),
                    output_path=normalized,
                    aliases=base.aliases if base else (),
                    profile_id=profile_id,
                    repository_path=base.repository_path if base else "",
                    release_asset=base.release_asset if base else "",
                    catalog_available=base.catalog_available if base else False,
                    gap_layer=base.gap_layer if base else "",
                    gap_status=base.gap_status if base else "",
                    gap_in_repo=base.gap_in_repo if base else None,
                    gap_reason=base.gap_reason if base else "",
                    container_name=base.container_name if base else "",
                    archive_required=base.archive_required if base else False,
                )
            )
        return result

    @classmethod
    def load_catalog(
        cls,
        system_directory: str | Path,
        *,
        refresh: bool = False,
    ) -> tuple[str, tuple[AresFirmwareEntry, ...]]:
        version, catalog = AresFirmwareService.load_catalog(
            emulator="retroarch", refresh=refresh
        )
        info_dir = cls._info_directory(system_directory)
        entries: list[AresFirmwareEntry] = []
        for info_path in sorted(info_dir.glob(f"*{cls.INFO_SUFFIX}"), key=lambda p: p.name.casefold()):
            values = cls._parse_info(info_path)
            entries.extend(cls._firmware_from_info(info_path, values, catalog))
        unique: dict[str, AresFirmwareEntry] = {entry.key: entry for entry in entries}
        if not unique:
            raise RetroArchBiosError(
                f"Nenhum core RetroArch com firmware foi encontrado em {info_dir}."
            )
        return version, tuple(unique.values())

    @classmethod
    def scan(
        cls,
        source: str | Path,
        entries: tuple[AresFirmwareEntry, ...],
        **kwargs,
    ) -> AresFirmwareScan:
        return AresFirmwareService.scan(
            source, entries, emulator="retroarch", **kwargs
        )
