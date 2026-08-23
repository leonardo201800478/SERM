"""Parser e catálogo local dos arquivos ``*.info`` do RetroArch."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


_BOOL_KEYS = {
    "savestate", "cheats", "input_descriptors", "memory_descriptors",
    "libretro_saves", "core_options", "load_subsystem", "supports_no_game",
    "single_purpose", "database_match_archive_member", "hw_render",
    "needs_fullpath", "disk_control", "is_experimental",
}


@dataclass(frozen=True, slots=True)
class RetroArchInfoFirmware:
    """Firmware declarada por um arquivo .info."""
    index: int
    description: str
    path: str
    optional: bool
    md5: str | None = None
    is_directory: bool = False


@dataclass(frozen=True, slots=True)
class RetroArchInfoCore:
    """Representação normalizada de um core descrito por .info."""
    info_path: Path
    filename: str
    display_name: str
    corename: str
    display_version: str | None
    authors: tuple[str, ...]
    manufacturer: str | None
    categories: tuple[str, ...]
    supported_extensions: tuple[str, ...]
    system_name: str | None
    system_id: str | None
    databases: tuple[str, ...]
    license: str | None
    permissions: str | None
    description: str | None
    features: dict[str, str]
    firmware: tuple[RetroArchInfoFirmware, ...] = field(default_factory=tuple)


class RetroArchInfoService:
    """Lê, normaliza e expõe os .info do diretório ``libretro_info_path``."""

    def scan_directory(self, info_directory: str | Path) -> list[RetroArchInfoCore]:
        """Varre todos os .info válidos do diretório configurado."""
        root = Path(info_directory).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Diretório de informações do RetroArch não encontrado: {root}")
        result: list[RetroArchInfoCore] = []
        for path in sorted(root.glob("*_libretro.info"), key=lambda item: item.name.casefold()):
            if path.name.casefold() == "00_example_libretro.info":
                continue
            try:
                result.append(self.parse_file(path))
            except (OSError, ValueError):
                continue
        return result

    def parse_file(self, path: str | Path) -> RetroArchInfoCore:
        """Analisa um único arquivo .info preservando os campos oficiais."""
        path = Path(path).expanduser().resolve()
        values: dict[str, str] = {}
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
                value = value[1:-1]
            values[key] = value

        corename = values.get("corename") or path.stem.removesuffix("_libretro")
        firmware = self._parse_firmware(values)
        notes = values.get("notes", "")
        firmware = tuple(
            RetroArchInfoFirmware(
                f.index, f.description, f.path, f.optional,
                self._find_md5(notes, f.path), f.is_directory,
            )
            for f in firmware
        )
        return RetroArchInfoCore(
            info_path=path,
            filename=path.name,
            display_name=values.get("display_name") or corename,
            corename=corename,
            display_version=values.get("display_version"),
            authors=tuple(self._split(values.get("authors", ""))),
            manufacturer=values.get("manufacturer"),
            categories=tuple(self._split(values.get("categories", ""))),
            supported_extensions=tuple(self._split(values.get("supported_extensions", ""))),
            system_name=values.get("systemname"),
            system_id=values.get("systemid"),
            databases=tuple(self._split(values.get("database", ""))),
            license=values.get("license"),
            permissions=values.get("permissions"),
            description=values.get("description"),
            features={key: value for key, value in values.items() if key in _BOOL_KEYS or key in {"savestate_features", "core_options_version", "required_hw_api"}},
            firmware=firmware,
        )

    @staticmethod
    def _split(value: str) -> list[str]:
        """Divide campos Libretro delimitados por ``|`` removendo vazios."""
        return [item.strip() for item in value.split("|") if item.strip()]

    @staticmethod
    def _bool(value: str | None, default: bool = False) -> bool:
        """Converte o booleano textual usado nos .info."""
        if value is None:
            return default
        return value.strip().casefold() in {"true", "yes", "1"}

    def _parse_firmware(self, values: dict[str, str]) -> tuple[RetroArchInfoFirmware, ...]:
        """Extrai firmware_count e identifica corretamente arquivos e diretórios."""
        try:
            count = int(values.get("firmware_count", "0"))
        except ValueError:
            count = 0
        entries: list[RetroArchInfoFirmware] = []
        for index in range(max(0, count)):
            path = values.get(f"firmware{index}_path")
            if not path:
                continue
            desc = values.get(f"firmware{index}_desc") or path
            # O formato .info não possui um campo is_directory. O caso oficial
            # do LRPS2 é explicitamente descrito como uma pasta; a ausência de
            # extensão no path também é um forte sinal, mas a descrição é a
            # autoridade quando informa "folder".
            normalized = path.replace("\\", "/").rstrip("/")
            description = desc.casefold()
            is_directory = (
                path.endswith(("/", "\\"))
                or "folder" in description
                or "directory" in description
                or normalized.casefold().endswith("/bios")
            )
            entries.append(RetroArchInfoFirmware(
                index=index,
                description=desc,
                path=path,
                optional=self._bool(values.get(f"firmware{index}_opt"), False),
                is_directory=is_directory,
            ))
        return tuple(entries)

    @staticmethod
    def _find_md5(notes: str, filename: str) -> str | None:
        """Extrai o MD5 associado ao firmware quando o campo notes o fornece."""
        name = re.escape(Path(filename).name)
        match = re.search(rf"{name}\s*\(md5\):\s*([0-9a-fA-F]{{32}})", notes)
        return match.group(1).lower() if match else None


__all__ = ["RetroArchInfoService", "RetroArchInfoCore", "RetroArchInfoFirmware"]
