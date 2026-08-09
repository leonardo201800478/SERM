"""
Modelos utilizados pelo sistema de configuração do MAME.

Este módulo não conhece a implementação do parser.
Ele apenas representa os dados extraídos de um arquivo MAME.INI.

O projeto utiliza estes modelos para manter uma separação clara entre:

    arquivo físico
        ↓
    parser
        ↓
    modelos
        ↓
    service
        ↓
    GUI
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable


# ============================================================================
# INI OPTION
# ============================================================================


@dataclass(slots=True)
class IniOption:
    """
    Representa uma opção individual encontrada no MAME.INI.

    Attributes:
        key:
            Nome da configuração.

        value:
            Valor atualmente armazenado.

        line_index:
            Índice da linha dentro do arquivo.

        original_line:
            Linha exatamente como foi carregada.

        leading_whitespace:
            Espaços existentes antes da chave.

        separator:
            Espaçamento entre a chave e o valor.

        trailing_whitespace:
            Espaços existentes depois do valor e antes da quebra de linha.

        newline:
            Terminador da linha original.

        commented:
            Indica se a linha estava comentada.
    """

    key: str
    value: str
    line_index: int

    original_line: str

    leading_whitespace: str = ""
    separator: str = ""
    trailing_whitespace: str = ""
    newline: str = "\n"

    commented: bool = False

    @property
    def is_active(self) -> bool:
        """Retorna True quando a opção está ativa."""
        return not self.commented

    def render(self, value: str | None = None) -> str:
        """
        Reconstrói a linha preservando sua estrutura original.

        Args:
            value:
                Novo valor. Se None, utiliza o valor atual.

        Returns:
            Linha reconstruída.
        """
        final_value = self.value if value is None else str(value)

        return (
            f"{self.leading_whitespace}"
            f"{self.key}"
            f"{self.separator}"
            f"{final_value}"
            f"{self.trailing_whitespace}"
            f"{self.newline}"
        )


# ============================================================================
# INI FILE INFORMATION
# ============================================================================


@dataclass(slots=True)
class IniFileInfo:
    """
    Informações físicas sobre um arquivo MAME.INI.
    """

    path: Path

    exists: bool = False

    size: int = 0

    modified_at: datetime | None = None

    encoding: str = "utf-8"

    newline: str = "\n"

    option_count: int = 0

    duplicate_keys: tuple[str, ...] = ()

    has_bom: bool = False

    @property
    def filename(self) -> str:
        """Retorna somente o nome do arquivo."""
        return self.path.name

    @property
    def directory(self) -> Path:
        """Retorna o diretório onde o arquivo está localizado."""
        return self.path.parent

    @property
    def is_valid(self) -> bool:
        """Indica se o arquivo existe e é um arquivo regular."""
        return self.exists and self.path.is_file()

    @classmethod
    def from_path(
        cls,
        path: Path,
        *,
        encoding: str = "utf-8",
        newline: str = "\n",
        option_count: int = 0,
        duplicate_keys: Iterable[str] = (),
        has_bom: bool = False,
    ) -> "IniFileInfo":
        """
        Cria informações a partir de um caminho.

        Args:
            path:
                Caminho do arquivo.

            encoding:
                Codificação detectada.

            newline:
                Terminador predominante.

            option_count:
                Quantidade de opções encontradas.

            duplicate_keys:
                Chaves duplicadas.

            has_bom:
                Indica presença de BOM UTF-8.
        """
        path = Path(path)

        if not path.exists():
            return cls(
                path=path,
                exists=False,
                encoding=encoding,
                newline=newline,
                option_count=option_count,
                duplicate_keys=tuple(duplicate_keys),
                has_bom=has_bom,
            )

        stat = path.stat()

        return cls(
            path=path,
            exists=True,
            size=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            encoding=encoding,
            newline=newline,
            option_count=option_count,
            duplicate_keys=tuple(duplicate_keys),
            has_bom=has_bom,
        )


# ============================================================================
# MAME DIRECTORIES
# ============================================================================


@dataclass(slots=True)
class MameDirectories:
    """
    Diretórios configuráveis pelo MAME.

    As opções são mantidas separadas porque algumas representam caminhos
    múltiplos e outras representam um único diretório.

    Caminhos múltiplos são separados pelo MAME usando ';' no Windows.
    """

    rompath: list[str] = field(default_factory=list)

    hashpath: list[str] = field(default_factory=list)

    samplepath: list[str] = field(default_factory=list)

    artpath: list[str] = field(default_factory=list)

    ctrlrpath: list[str] = field(default_factory=list)

    inipath: list[str] = field(default_factory=list)

    fontpath: list[str] = field(default_factory=list)

    cheatpath: list[str] = field(default_factory=list)

    crosshairpath: list[str] = field(default_factory=list)

    pluginspath: list[str] = field(default_factory=list)

    languagepath: list[str] = field(default_factory=list)

    swpath: list[str] = field(default_factory=list)

    homepath: str = ""

    cfg_directory: str = ""

    nvram_directory: str = ""

    input_directory: str = ""

    state_directory: str = ""

    snapshot_directory: str = ""

    diff_directory: str = ""

    comment_directory: str = ""

    @property
    def rom_paths(self) -> list[str]:
        """Alias mais legível para rompath."""
        return self.rompath

    @rom_paths.setter
    def rom_paths(self, value: list[str]) -> None:
        self.rompath = list(value)

    def as_dict(self) -> dict[str, str | list[str]]:
        """
        Converte o modelo para um dicionário.

        Returns:
            Dicionário contendo todas as configurações de diretório.
        """
        return {
            "homepath": self.homepath,
            "rompath": list(self.rompath),
            "hashpath": list(self.hashpath),
            "samplepath": list(self.samplepath),
            "artpath": list(self.artpath),
            "ctrlrpath": list(self.ctrlrpath),
            "inipath": list(self.inipath),
            "fontpath": list(self.fontpath),
            "cheatpath": list(self.cheatpath),
            "crosshairpath": list(self.crosshairpath),
            "pluginspath": list(self.pluginspath),
            "languagepath": list(self.languagepath),
            "swpath": list(self.swpath),
            "cfg_directory": self.cfg_directory,
            "nvram_directory": self.nvram_directory,
            "input_directory": self.input_directory,
            "state_directory": self.state_directory,
            "snapshot_directory": self.snapshot_directory,
            "diff_directory": self.diff_directory,
            "comment_directory": self.comment_directory,
        }


# ============================================================================
# GENERIC MAME CONFIGURATION
# ============================================================================


@dataclass(slots=True)
class MameIniDocument:
    """
    Representação lógica de um MAME.INI.

    O documento mantém todas as linhas e opções conhecidas.
    """

    path: Path

    lines: list[str] = field(default_factory=list)

    options: dict[str, IniOption] = field(default_factory=dict)

    modified: dict[str, str] = field(default_factory=dict)

    info: IniFileInfo | None = None

    @property
    def is_modified(self) -> bool:
        """Retorna True quando existem alterações pendentes."""
        return bool(self.modified)

    @property
    def option_count(self) -> int:
        """Retorna o número de opções conhecidas."""
        return len(self.options)

    def get(self, key: str, default: str | None = None) -> str | None:
        """
        Obtém uma configuração.

        Args:
            key:
                Nome da configuração.

            default:
                Valor utilizado quando a opção não existe.

        Returns:
            Valor atual ou default.
        """
        key = key.strip()

        if key in self.modified:
            return self.modified[key]

        option = self.options.get(key)

        if option is None:
            return default

        return option.value

    def has(self, key: str) -> bool:
        """Verifica se uma configuração existe."""
        return key.strip() in self.options

    def get_all(self) -> dict[str, str]:
        """
        Retorna todas as configurações conhecidas.

        Returns:
            Dicionário chave/valor.
        """
        result: dict[str, str] = {}

        for key, option in self.options.items():
            result[key] = self.modified.get(key, option.value)

        return result