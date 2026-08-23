"""Leitura e escrita segura do arquivo nativo de configuração do FBNeo.

O FBNeo não usa INI tradicional: o arquivo é composto por comentários e
linhas ``chave valor``. Este serviço preserva linhas desconhecidas e comentários
para evitar destruir configurações existentes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable


class FBNeoConfig:
    """Gerencia caminhos do ``fbneo64.ini``/``fbneo.ini``."""

    ROM_KEYS = tuple(f"szAppRomPaths[{index}]" for index in range(20))

    SUPPORT_KEYS = {
        "neocd": "szNeoCDGamesDir",
        "previews": "szAppPreviewsPath",
        "titles": "szAppTitlesPath",
        "cheats": "szAppCheatsPath",
        "hiscore": "szAppHiscorePath",
        "samples": "szAppSamplesPath",
        "hdd": "szAppHDDPath",
        "ips": "szAppIpsPath",
        "romdata": "szAppRomdataPath",
        "icons": "szAppIconsPath",
        "neocd_covers": "szNeoCDCoverDir",
        "neocd_previews": "szNeoCDPreviewDir",
        "blend": "szAppBlendPath",
        "select": "szAppSelectPath",
        "versus": "szAppVersusPath",
        "howto": "szAppHowtoPath",
        "scores": "szAppScoresPath",
        "bosses": "szAppBossesPath",
        "gameover": "szAppGameoverPath",
        "flyers": "szAppFlyersPath",
        "marquees": "szAppMarqueesPath",
        "controls": "szAppControlsPath",
        "cabinets": "szAppCabinetsPath",
        "pcbs": "szAppPCBsPath",
        "history": "szAppHistoryPath",
        "commands": "szAppCommandPath",
        "eeprom": "szAppEEPROMPath",
    }

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lines: list[str] = []
        self._newline = "\n"
        self.load()

    def load(self) -> None:
        """Carrega o arquivo preservando a representação textual."""
        if not self.path.is_file():
            self._lines = []
            return
        text = self.path.read_text(encoding="utf-8")
        if "\r\n" in text:
            self._newline = "\r\n"
        self._lines = text.splitlines()

    @staticmethod
    def _parse_line(line: str) -> tuple[str, str] | None:
        """Extrai chave e valor de uma linha FBNeo ``key value``."""
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            return None
        parts = stripped.split(None, 1)
        if len(parts) != 2:
            return None
        return parts[0], parts[1].strip()

    def get(self, key: str, default: str = "") -> str:
        """Obtém o valor de uma chave, preservando string vazia."""
        for line in self._lines:
            parsed = self._parse_line(line)
            if parsed and parsed[0] == key:
                return parsed[1]
        return default

    def set(self, key: str, value: str) -> None:
        """Altera uma chave existente ou adiciona a chave ao final do arquivo."""
        replacement = f"{key} {value}".rstrip()
        for index, line in enumerate(self._lines):
            parsed = self._parse_line(line)
            if parsed and parsed[0] == key:
                prefix = line[: len(line) - len(line.lstrip())]
                self._lines[index] = prefix + replacement
                return
        self._lines.append(replacement)

    def get_rom_paths(self, limit: int = 4) -> list[str]:
        """Retorna os primeiros caminhos de ROM configuráveis na GUI.

        O FBNeo suporta até 20 entradas. O ARCADE MANAGER expõe somente quatro
        entradas principais, preservando as demais entradas nativas no arquivo.
        """
        return [self.get(key) for key in self.ROM_KEYS[:limit]]

    def set_rom_paths(self, paths: Iterable[str], limit: int = 4) -> None:
        """Grava até quatro caminhos principais sem tocar nos slots restantes."""
        values = [str(path).strip() for path in paths][:limit]
        while len(values) < limit:
            values.append("")
        for key, value in zip(self.ROM_KEYS[:limit], values):
            self.set(key, value)

    def get_support_paths(self) -> dict[str, str]:
        """Retorna todos os diretórios auxiliares conhecidos pelo FBNeo."""
        return {name: self.get(key) for name, key in self.SUPPORT_KEYS.items()}

    def set_support_paths(self, paths: dict[str, str]) -> None:
        """Atualiza somente os diretórios auxiliares fornecidos."""
        for name, key in self.SUPPORT_KEYS.items():
            if name in paths:
                self.set(key, str(paths[name]).strip())

    def save(self, create_backup: bool = True) -> None:
        """Salva atomicamente e opcionalmente cria backup do arquivo original."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if create_backup and self.path.is_file():
            backup = self.path.with_suffix(self.path.suffix + ".bak")
            backup.write_bytes(self.path.read_bytes())
        text = self._newline.join(self._lines) + (self._newline if self._lines else "")
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(text, encoding="utf-8", newline="")
        temp.replace(self.path)
