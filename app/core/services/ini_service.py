"""
Serviço de alto nível para gerenciamento do MAME.INI.

O IniService não manipula diretamente o conteúdo textual do arquivo.
Toda leitura/escrita passa pelo MameIniParser.

Isso permite que a GUI trabalhe com configurações do MAME sem precisar
conhecer detalhes do formato físico do arquivo.
"""

from __future__ import annotations

from pathlib import Path

from app.core.models.ini_models import (
    IniFileInfo,
    MameDirectories,
)
from app.mame.ini_parser import MameIniParser


class IniService:
    """
    Serviço central para leitura e gravação do MAME.INI.

    A API é deliberadamente genérica.

    Exemplos:

        service.get("video")

        service.set("video", "auto")

        service.get_directories()

        service.set_rompath([...])

        service.save()
    """

    # ========================================================================
    # MAME PATH OPTIONS
    # ========================================================================

    MULTI_PATH_OPTIONS = frozenset(
        {
            "rompath",
            "hashpath",
            "samplepath",
            "artpath",
            "ctrlrpath",
            "inipath",
            "fontpath",
            "cheatpath",
            "crosshairpath",
            "pluginspath",
            "languagepath",
            "swpath",
        }
    )

    SINGLE_PATH_OPTIONS = frozenset(
        {
            "homepath",
            "cfg_directory",
            "nvram_directory",
            "input_directory",
            "state_directory",
            "snapshot_directory",
            "diff_directory",
            "comment_directory",
        }
    )

    # ========================================================================
    # INIT
    # ========================================================================

    def __init__(
        self,
        ini_path: Path,
        *,
        auto_load: bool = True,
    ) -> None:
        """
        Inicializa o serviço.

        Args:
            ini_path:
                Caminho do MAME.INI.

            auto_load:
                Carrega automaticamente o arquivo.
        """
        self.ini_path = Path(ini_path)

        self.parser = MameIniParser(
            self.ini_path,
        )

        if auto_load:
            self.load()

    # ========================================================================
    # LOAD
    # ========================================================================

    def load(self) -> None:
        """
        Carrega/recarrega o MAME.INI.
        """
        self.parser.load()

    # ========================================================================
    # GENERIC GET
    # ========================================================================

    def get(
        self,
        key: str,
        default: str | None = None,
    ) -> str | None:
        """
        Obtém qualquer configuração do MAME.INI.

        Args:
            key:
                Nome da opção.

            default:
                Valor padrão.

        Returns:
            Valor da configuração.
        """
        return self.parser.get(
            key,
            default,
        )

    # ========================================================================
    # GENERIC SET
    # ========================================================================

    def set(
        self,
        key: str,
        value: str,
    ) -> bool:
        """
        Agenda alteração de qualquer configuração existente.

        A opção não é criada caso não exista no arquivo.

        Returns:
            True se a opção existe e foi aceita.
        """
        return self.parser.set(
            key,
            value,
        )

    # ========================================================================
    # UPDATE (MÚLTIPLAS ALTERAÇÕES)
    # ========================================================================

    def update(self, changes: dict[str, str]) -> int:
        """
        Aplica múltiplas alterações de uma só vez.

        Args:
            changes:
                Dicionário com chave -> novo valor.

        Returns:
            Número de alterações efetivamente aplicadas.
        """
        count = 0
        for key, value in changes.items():
            if self.set(key, value):
                count += 1
        return count

    # ========================================================================
    # HAS
    # ========================================================================

    def has(self, key: str) -> bool:
        """
        Verifica se uma configuração existe.
        """
        return self.parser.has(key)

    # ========================================================================
    # ALL
    # ========================================================================

    def get_all(self) -> dict[str, str]:
        """
        Retorna todas as configurações conhecidas.
        """
        return self.parser.get_all_options()

    # ========================================================================
    # FILE INFORMATION
    # ========================================================================

    def get_file_info(self) -> IniFileInfo | None:
        """
        Retorna informações físicas do MAME.INI.
        """
        return self.parser.get_file_info()

    # ========================================================================
    # MANIPULAÇÃO DE CAMINHOS (pública)
    # ========================================================================

    @staticmethod
    def split_paths(value: str | None) -> list[str]:
        """
        Converte uma configuração de múltiplos caminhos em lista.

        O MAME utiliza ';' como separador de caminhos múltiplos.

        Args:
            value:
                Valor bruto.

        Returns:
            Lista de caminhos.
        """
        if value is None:
            return []

        value = value.strip()

        if not value:
            return []

        return [
            item.strip()
            for item in value.split(";")
            if item.strip()
        ]

    @staticmethod
    def join_paths(paths: list[str]) -> str:
        """
        Converte uma lista de caminhos para o formato aceito pelo MAME.

        Args:
            paths:
                Lista de diretórios.

        Returns:
            Caminhos separados por ';'.
        """
        return ";".join(
            str(path).strip()
            for path in paths
            if str(path).strip()
        )

    # ========================================================================
    # GET PATHS (lista)
    # ========================================================================

    def get_paths(self, key: str) -> list[str]:
        """
        Retorna uma opção de caminho como lista.

        Funciona tanto para opções multi-path quanto single-path.

        Args:
            key:
                Nome da configuração.

        Returns:
            Lista de caminhos.
        """
        value = self.get(key, "")

        if key in self.MULTI_PATH_OPTIONS:
            return self.split_paths(value)

        if value is None or not value.strip():
            return []

        return [value.strip()]

    # ========================================================================
    # SET PATHS (lista)
    # ========================================================================

    def set_paths(
        self,
        key: str,
        paths: list[str],
    ) -> bool:
        """
        Define uma configuração de caminhos.

        Args:
            key:
                Nome da opção.

            paths:
                Lista de caminhos.

        Returns:
            True quando a opção existe.
        """
        if key in self.MULTI_PATH_OPTIONS:
            value = self.join_paths(paths)
        else:
            value = paths[0].strip() if paths else ""

        return self.set(
            key,
            value,
        )

    # ========================================================================
    # MAME DIRECTORIES MODEL
    # ========================================================================

    def get_directories(self) -> MameDirectories:
        """
        Lê todos os principais diretórios configuráveis do MAME.

        Returns:
            MameDirectories.
        """
        return MameDirectories(
            homepath=self.get("homepath", "") or "",

            rompath=self.get_paths("rompath"),

            hashpath=self.get_paths("hashpath"),

            samplepath=self.get_paths("samplepath"),

            artpath=self.get_paths("artpath"),

            ctrlrpath=self.get_paths("ctrlrpath"),

            inipath=self.get_paths("inipath"),

            fontpath=self.get_paths("fontpath"),

            cheatpath=self.get_paths("cheatpath"),

            crosshairpath=self.get_paths("crosshairpath"),

            pluginspath=self.get_paths("pluginspath"),

            languagepath=self.get_paths("languagepath"),

            swpath=self.get_paths("swpath"),

            cfg_directory=self.get("cfg_directory", "") or "",

            nvram_directory=self.get(
                "nvram_directory",
                "",
            ) or "",

            input_directory=self.get(
                "input_directory",
                "",
            ) or "",

            state_directory=self.get(
                "state_directory",
                "",
            ) or "",

            snapshot_directory=self.get(
                "snapshot_directory",
                "",
            ) or "",

            diff_directory=self.get(
                "diff_directory",
                "",
            ) or "",

            comment_directory=self.get(
                "comment_directory",
                "",
            ) or "",
        )

    def set_directories(
        self,
        directories: MameDirectories,
    ) -> None:
        """
        Agenda todas as alterações de diretórios.

        Nenhuma alteração é gravada no disco até save() ser chamado.
        """
        self.set(
            "homepath",
            directories.homepath,
        )

        self.set_paths(
            "rompath",
            directories.rompath,
        )

        self.set_paths(
            "hashpath",
            directories.hashpath,
        )

        self.set_paths(
            "samplepath",
            directories.samplepath,
        )

        self.set_paths(
            "artpath",
            directories.artpath,
        )

        self.set_paths(
            "ctrlrpath",
            directories.ctrlrpath,
        )

        self.set_paths(
            "inipath",
            directories.inipath,
        )

        self.set_paths(
            "fontpath",
            directories.fontpath,
        )

        self.set_paths(
            "cheatpath",
            directories.cheatpath,
        )

        self.set_paths(
            "crosshairpath",
            directories.crosshairpath,
        )

        self.set_paths(
            "pluginspath",
            directories.pluginspath,
        )

        self.set_paths(
            "languagepath",
            directories.languagepath,
        )

        self.set_paths(
            "swpath",
            directories.swpath,
        )

        self.set(
            "cfg_directory",
            directories.cfg_directory,
        )

        self.set(
            "nvram_directory",
            directories.nvram_directory,
        )

        self.set(
            "input_directory",
            directories.input_directory,
        )

        self.set(
            "state_directory",
            directories.state_directory,
        )

        self.set(
            "snapshot_directory",
            directories.snapshot_directory,
        )

        self.set(
            "diff_directory",
            directories.diff_directory,
        )

        self.set(
            "comment_directory",
            directories.comment_directory,
        )

    # ========================================================================
    # COMPATIBILITY GETTERS
    # ========================================================================

    def get_rompath(self) -> str:
        """Retorna rompath no formato bruto do MAME."""
        return self.get("rompath", "") or ""

    def get_samplepath(self) -> str:
        """Retorna samplepath."""
        return self.get("samplepath", "") or ""

    def get_artpath(self) -> str:
        """Retorna artpath."""
        return self.get("artpath", "") or ""

    def get_cfgpath(self) -> str:
        """Retorna cfg_directory."""
        return self.get("cfg_directory", "") or ""

    def get_nvrampath(self) -> str:
        """Retorna nvram_directory."""
        return self.get("nvram_directory", "") or ""

    def get_statepath(self) -> str:
        """Retorna state_directory."""
        return self.get("state_directory", "") or ""

    def get_snappath(self) -> str:
        """Retorna snapshot_directory."""
        return self.get("snapshot_directory", "") or ""

    def get_diffpath(self) -> str:
        """Retorna diff_directory."""
        return self.get("diff_directory", "") or ""

    def get_inipath(self) -> str:
        """Retorna inipath."""
        return self.get("inipath", "") or ""

    # ========================================================================
    # COMPATIBILITY SETTERS
    # ========================================================================

    def set_rompath(self, value: str) -> bool:
        """Define rompath."""
        return self.set("rompath", value)

    def set_samplepath(self, value: str) -> bool:
        """Define samplepath."""
        return self.set("samplepath", value)

    def set_artpath(self, value: str) -> bool:
        """Define artpath."""
        return self.set("artpath", value)

    def set_cfgpath(self, value: str) -> bool:
        """Define cfg_directory."""
        return self.set(
            "cfg_directory",
            value,
        )

    def set_nvrampath(self, value: str) -> bool:
        """Define nvram_directory."""
        return self.set(
            "nvram_directory",
            value,
        )

    def set_statepath(self, value: str) -> bool:
        """Define state_directory."""
        return self.set(
            "state_directory",
            value,
        )

    def set_snappath(self, value: str) -> bool:
        """Define snapshot_directory."""
        return self.set(
            "snapshot_directory",
            value,
        )

    def set_diffpath(self, value: str) -> bool:
        """Define diff_directory."""
        return self.set(
            "diff_directory",
            value,
        )

    def set_inipath(self, value: str) -> bool:
        """Define inipath."""
        return self.set(
            "inipath",
            value,
        )

    # ========================================================================
    # CHANGE MANAGEMENT
    # ========================================================================

    def reset(self, key: str) -> bool:
        """
        Cancela uma alteração pendente.
        """
        return self.parser.reset(key)

    def reset_all(self) -> None:
        """
        Cancela todas as alterações pendentes.
        """
        self.parser.reset_all()

    def has_pending_changes(self) -> bool:
        """
        Informa se existem alterações pendentes.
        """
        return self.parser.has_pending_changes()

    # ========================================================================
    # SAVE
    # ========================================================================

    def save(self) -> bool:
        """
        Grava todas as alterações pendentes.

        Returns:
            True quando houve gravação.
        """
        return self.parser.save()