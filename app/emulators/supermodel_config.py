"""Adapter de configuração nativa do Supermodel.

O Supermodel utiliza o ``Supermodel.ini`` como arquivo de configuração global.
Esta classe trata exclusivamente os caminhos que o ARCADE MANAGER precisa
administrar e preserva as demais opções do arquivo.

A configuração de ROMs usa ``RomsDirectory`` quando a versão instalada do
Supermodel oferece essa chave. O serviço não inventa uma chave alternativa.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


class SupermodelConfig:
    """Lê e grava diretórios do Supermodel.ini sem destruir outras opções."""

    ROMS_KEY = "RomsDirectory"
    GLOBAL_SECTION = "Global"

    def __init__(self, install_dir: Path | None = None) -> None:
        self.install_dir = Path(install_dir) if install_dir else None

    @property
    def config_dir(self) -> Path | None:
        """Retorna o diretório Config da instalação configurada."""
        return self.install_dir / "Config" if self.install_dir else None

    @property
    def ini_path(self) -> Path | None:
        """Retorna o caminho esperado do Supermodel.ini."""
        if not self.config_dir:
            return None
        return self.config_dir / "Supermodel.ini"

    @property
    def games_xml_path(self) -> Path | None:
        """Retorna o caminho esperado do banco Games.xml."""
        if not self.config_dir:
            return None
        return self.config_dir / "Games.xml"

    def default_directories(self) -> dict[str, Path]:
        """Retorna os diretórios convencionais da distribuição do Supermodel."""
        if not self.install_dir:
            return {}
        return {
            "roms": self.install_dir / "ROMs",
            "config": self.install_dir / "Config",
            "nvram": self.install_dir / "NVRAM",
            "saves": self.install_dir / "Saves",
            "assets": self.install_dir / "Assets",
        }

    def read_rom_directory(self) -> Path | None:
        """Lê ``RomsDirectory`` do bloco ``[ Global ]`` quando presente."""
        path = self.ini_path
        if not path or not path.is_file():
            return None
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            return None
        value = self._read_global_key(text, self.ROMS_KEY)
        return Path(value) if value else None

    def write_rom_directory(self, directory: Path | None) -> Path:
        """Grava ``RomsDirectory`` preservando o restante do Supermodel.ini.

        O arquivo é atualizado atomicamente. Se o arquivo ainda não existir,
        é criado com uma seção ``[ Global ]`` mínima.
        """
        path = self.ini_path
        if not path:
            raise ValueError("Diretório de instalação do Supermodel não configurado")

        path.parent.mkdir(parents=True, exist_ok=True)
        text = path.read_text(encoding="utf-8-sig") if path.is_file() else "[ Global ]\n"
        value = self._format_path(directory)
        updated = self._write_global_key(text, self.ROMS_KEY, value)
        self._atomic_write(path, updated)
        return path

    @classmethod
    def _read_global_key(cls, text: str, key: str) -> str | None:
        """Extrai uma chave da seção Global, ignorando comentários."""
        in_global = False
        for raw in text.splitlines():
            stripped = raw.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_global = stripped.strip("[] ").casefold() == cls.GLOBAL_SECTION.casefold()
                continue
            if not in_global or not stripped or stripped.startswith(("#", ";")):
                continue
            if "=" not in stripped:
                continue
            current, value = stripped.split("=", 1)
            if current.strip().casefold() == key.casefold():
                return value.strip().strip('"')
        return None

    @classmethod
    def _write_global_key(cls, text: str, key: str, value: str) -> str:
        """Substitui ou acrescenta uma chave dentro de ``[ Global ]``."""
        lines = text.splitlines(keepends=True)
        start: int | None = None
        end = len(lines)
        for index, raw in enumerate(lines):
            stripped = raw.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                if stripped.strip("[] ").casefold() == cls.GLOBAL_SECTION.casefold():
                    start = index
                elif start is not None:
                    end = index
                    break

        if start is None:
            if text and not text.endswith(("\n", "\r")):
                text += "\n"
            return f"{text}\n[ Global ]\n{key} = {value}\n"

        for index in range(start + 1, end):
            stripped = lines[index].strip()
            if not stripped or stripped.startswith(("#", ";")) or "=" not in stripped:
                continue
            current, _ = stripped.split("=", 1)
            if current.strip().casefold() == key.casefold():
                newline = "\n" if lines[index].endswith(("\n", "\r")) else ""
                lines[index] = f"{key} = {value}{newline}"
                return "".join(lines)

        insert_at = end
        lines.insert(insert_at, f"{key} = {value}\n")
        return "".join(lines)

    @staticmethod
    def _format_path(directory: Path | None) -> str:
        """Normaliza um caminho para o formato textual aceito pelo INI."""
        if directory is None:
            return ""
        return str(Path(directory).expanduser())

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        """Grava um arquivo temporário e publica a alteração atomicamente."""
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8", newline="")
        os.replace(temporary, path)

    def validate_installation(self) -> dict[str, Path | bool | None]:
        """Valida a estrutura conhecida sem criar diretórios automaticamente."""
        if not self.install_dir:
            return {
                "install_dir": None,
                "executable": None,
                "config": None,
                "games_xml": None,
                "valid": False,
            }
        executable = self.install_dir / "Supermodel.exe"
        config = self.ini_path
        games_xml = self.games_xml_path
        return {
            "install_dir": self.install_dir,
            "executable": executable,
            "config": config,
            "games_xml": games_xml,
            "valid": executable.is_file(),
        }
