"""
Parser específico para arquivos MAME.INI.

IMPORTANTE:

O MAME.INI não é um INI tradicional no formato:

    chave=valor

O formato utilizado pelo MAME normalmente é:

    chave                   valor

Exemplo:

    rompath                 roms
    samplepath              samples
    video                   auto
    window                  0

Este parser foi desenvolvido especificamente para preservar o arquivo
original e alterar somente os valores explicitamente solicitados.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Iterable
from pathlib import Path

from app.core.models.ini_models import (
    IniFileInfo,
    IniOption,
    MameIniDocument,
)


class MameIniParser:
    """
    Parser seguro para MAME.INI.

    Características:

    - preserva comentários;
    - preserva linhas vazias;
    - preserva a ordem;
    - preserva espaçamento;
    - preserva linhas desconhecidas;
    - não cria opções inexistentes;
    - altera somente opções existentes;
    - suporta caminhos contendo espaços;
    - suporta múltiplos caminhos separados por ';';
    - detecta CRLF/LF;
    - detecta BOM;
    - utiliza escrita atômica;
    - mantém uma lista explícita das modificações.
    """

    # Regex captura chave, separador, valor e trailing spaces, incluindo newline
    _OPTION_RE = re.compile(
        r"^(?P<leading>[ \t]*)"
        r"(?P<key>[^\s#;]+)"
        r"(?P<separator>[ \t]+)"
        r"(?P<value>.*?)"  # valor (non-greedy)
        r"(?P<trailing>[ \t]*)"  # espaços após o valor
        r"(?P<newline>\r\n|\n|\r)?$"  # quebra de linha opcional
    )

    def __init__(
        self,
        ini_path: Path,
        *,
        encoding: str | None = None,
    ) -> None:
        """
        Inicializa o parser.

        Args:
            ini_path:
                Caminho do MAME.INI.

            encoding:
                Codificação forçada. Quando None, será detectada.
        """
        self.ini_path = Path(ini_path)

        self.encoding = encoding

        self.document = MameIniDocument(
            path=self.ini_path,
        )

        self._loaded = False

    # ========================================================================
    # LOAD
    # ========================================================================

    def load(self) -> MameIniDocument:
        """
        Carrega o arquivo MAME.INI.

        Returns:
            Documento carregado.

        Raises:
            FileNotFoundError:
                Caso o arquivo não exista.
        """
        if not self.ini_path.exists():
            raise FileNotFoundError(
                f"MAME.INI não encontrado: {self.ini_path}"
            )

        if not self.ini_path.is_file():
            raise IsADirectoryError(
                f"O caminho informado não é um arquivo: {self.ini_path}"
            )

        raw = self.ini_path.read_bytes()

        encoding, has_bom = self._detect_encoding(raw)

        text = raw.decode(encoding)

        lines = text.splitlines(keepends=True)

        self.document.lines = lines

        self.encoding = encoding

        self._parse_options()

        newline = self._detect_newline(lines)

        duplicate_keys = self._find_duplicate_keys()

        self.document.info = IniFileInfo.from_path(
            self.ini_path,
            encoding=encoding,
            newline=newline,
            option_count=len(self.document.options),
            duplicate_keys=duplicate_keys,
            has_bom=has_bom,
        )

        self._loaded = True

        return self.document

    # ========================================================================
    # ENCODING
    # ========================================================================

    @staticmethod
    def _detect_encoding(raw: bytes) -> tuple[str, bool]:
        """
        Detecta a codificação do arquivo.

        O MAME.INI normalmente utiliza ASCII/UTF-8.
        UTF-8 com BOM também é suportado.

        Returns:
            Tupla contendo encoding e presença de BOM.
        """
        if raw.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig", True

        try:
            raw.decode("utf-8")
            return "utf-8", False
        except UnicodeDecodeError:
            return "cp1252", False

    # ========================================================================
    # PARSE
    # ========================================================================

    def _parse_options(self) -> None:
        """
        Analisa todas as linhas e identifica opções ativas.

        O parser não altera as linhas durante esta etapa.
        """
        self.document.options.clear()
        self.document.modified.clear()

        for index, line in enumerate(self.document.lines):
            option = self._parse_line(line, index)

            if option is None:
                continue

            # Em caso de chave duplicada, mantemos a última ocorrência como
            # opção efetiva. Todas as linhas continuam preservadas.
            self.document.options[option.key] = option

    def _parse_line(
        self,
        line: str,
        index: int,
    ) -> IniOption | None:
        """
        Analisa uma linha individual.

        Args:
            line:
                Linha original.

            index:
                Índice da linha.

        Returns:
            IniOption ou None.
        """
        if not line.strip():
            return None

        stripped = line.lstrip(" \t")

        # Comentários do MAME.
        if stripped.startswith("#"):
            return None

        if stripped.startswith(";"):
            return None

        match = self._OPTION_RE.match(line)

        if not match:
            return None

        key = match.group("key")
        value = match.group("value")
        leading = match.group("leading")
        separator = match.group("separator")
        trailing = match.group("trailing")
        newline = match.group("newline") or ""

        if not key:
            return None

        # Evita interpretar fragmentos estranhos como configuração.
        if value == "" and separator == "":
            return None

        # Remove trailing spaces do valor (preservados em trailing)
        value = value.rstrip()

        return IniOption(
            key=key,
            value=value,
            line_index=index,
            original_line=line,
            leading_whitespace=leading,
            separator=separator,
            trailing_whitespace=trailing,
            newline=newline,
        )

    # ========================================================================
    # GET
    # ========================================================================

    def get(
        self,
        key: str,
        default: str | None = None,
    ) -> str | None:
        """
        Obtém uma configuração.

        Args:
            key:
                Nome da opção.

            default:
                Valor padrão.

        Returns:
            Valor da configuração.
        """
        self._ensure_loaded()

        return self.document.get(key, default)

    # ========================================================================
    # HAS
    # ========================================================================

    def has(self, key: str) -> bool:
        """
        Verifica se uma configuração existe no arquivo.
        """
        self._ensure_loaded()

        return self.document.has(key)

    # ========================================================================
    # SET
    # ========================================================================

    def set(
        self,
        key: str,
        value: str,
    ) -> bool:
        """
        Agenda uma alteração.

        IMPORTANTE:
        Uma opção inexistente NÃO é adicionada automaticamente.

        Args:
            key:
                Nome da configuração.

            value:
                Novo valor.

        Returns:
            True se a alteração foi aceita.
            False se a opção não existe.
        """
        self._ensure_loaded()

        key = key.strip()

        if key not in self.document.options:
            return False

        value = str(value).strip()

        current = self.document.get(key)

        if current == value:
            self.document.modified.pop(key, None)
            return True

        self.document.modified[key] = value

        return True

    # ========================================================================
    # REMOVE MODIFICATION
    # ========================================================================

    def reset(self, key: str) -> bool:
        """
        Cancela uma alteração pendente.

        Não modifica o arquivo físico.
        """
        self._ensure_loaded()

        key = key.strip()

        if key not in self.document.options:
            return False

        self.document.modified.pop(key, None)

        return True

    def reset_all(self) -> None:
        """
        Cancela todas as alterações pendentes.
        """
        self._ensure_loaded()

        self.document.modified.clear()

    # ========================================================================
    # ALL OPTIONS
    # ========================================================================

    def get_all_options(self) -> dict[str, str]:
        """
        Retorna todas as opções conhecidas.
        """
        self._ensure_loaded()

        return self.document.get_all()

    def get_option(self, key: str) -> IniOption | None:
        """
        Retorna o modelo da opção.
        """
        self._ensure_loaded()

        return self.document.options.get(key.strip())

    # ========================================================================
    # SAVE
    # ========================================================================

    def save(self) -> bool:
        """
        Salva as alterações pendentes.

        A escrita é realizada através de arquivo temporário e substituição
        atômica para reduzir o risco de corrupção caso o processo seja
        interrompido durante a gravação.

        Returns:
            True quando o arquivo foi salvo.
            False quando não havia alterações.
        """
        self._ensure_loaded()

        if not self.document.modified:
            return False

        new_lines = list(self.document.lines)

        for key, new_value in self.document.modified.items():
            option = self.document.options.get(key)

            if option is None:
                continue

            index = option.line_index

            # Renderiza a nova linha preservando espaçamento e quebra de linha
            new_lines[index] = option.render(new_value)

        self._atomic_write(new_lines)

        # Atualiza o estado interno somente depois de uma gravação bem-sucedida.
        self.document.lines = new_lines

        for key, new_value in self.document.modified.items():
            option = self.document.options.get(key)

            if option is None:
                continue

            option.value = new_value

            option.original_line = new_lines[option.line_index]

        self.document.modified.clear()

        # Atualiza metadados.
        self.document.info = IniFileInfo.from_path(
            self.ini_path,
            encoding=self.encoding or "utf-8",
            newline=self._detect_newline(new_lines),
            option_count=len(self.document.options),
            duplicate_keys=self._find_duplicate_keys(),
            has_bom=(self.encoding == "utf-8-sig"),
        )

        return True

    # ========================================================================
    # ATOMIC WRITE
    # ========================================================================

    def _atomic_write(self, lines: Iterable[str]) -> None:
        """
        Grava o arquivo usando escrita atômica.

        O arquivo temporário é criado no mesmo diretório do MAME.INI para
        garantir que os.replace() ocorra no mesmo volume.
        """
        parent = self.ini_path.parent

        parent.mkdir(parents=True, exist_ok=True)

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.ini_path.name}.",
            suffix=".tmp",
            dir=parent,
            text=False,
        )

        temp_path = Path(temp_name)

        try:
            with os.fdopen(fd, "wb") as file:
                content = "".join(lines)

                encoding = self.encoding or "utf-8"

                file.write(content.encode(encoding))

                file.flush()

                os.fsync(file.fileno())

            os.replace(temp_path, self.ini_path)

        except Exception:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

            raise

    # ========================================================================
    # METADATA
    # ========================================================================

    def get_file_info(self) -> IniFileInfo | None:
        """
        Retorna informações do arquivo.
        """
        return self.document.info

    def get_path(self) -> Path:
        """
        Retorna o caminho do MAME.INI.
        """
        return self.ini_path

    # ========================================================================
    # DUPLICATES
    # ========================================================================

    def _find_duplicate_keys(self) -> tuple[str, ...]:
        """
        Localiza chaves duplicadas no arquivo.
        """
        counts: dict[str, int] = {}

        for line in self.document.lines:
            option = self._parse_line(
                line,
                -1,
            )

            if option is None:
                continue

            counts[option.key] = counts.get(option.key, 0) + 1

        return tuple(
            sorted(
                key
                for key, count in counts.items()
                if count > 1
            )
        )

    # ========================================================================
    # NEWLINE
    # ========================================================================

    @staticmethod
    def _detect_newline(lines: Iterable[str]) -> str:
        """
        Detecta o terminador predominante.
        """
        crlf = 0
        lf = 0
        cr = 0

        for line in lines:
            if line.endswith("\r\n"):
                crlf += 1
            elif line.endswith("\n"):
                lf += 1
            elif line.endswith("\r"):
                cr += 1

        if crlf >= lf and crlf >= cr and crlf > 0:
            return "\r\n"

        if lf >= cr and lf > 0:
            return "\n"

        if cr > 0:
            return "\r"

        return "\n"

    # ========================================================================
    # STATE
    # ========================================================================

    def is_loaded(self) -> bool:
        """
        Retorna True quando o arquivo foi carregado.
        """
        return self._loaded

    def has_pending_changes(self) -> bool:
        """
        Retorna True quando existem alterações não salvas.
        """
        return bool(self.document.modified)

    def _ensure_loaded(self) -> None:
        """
        Garante que o parser foi carregado.
        """
        if not self._loaded:
            self.load()