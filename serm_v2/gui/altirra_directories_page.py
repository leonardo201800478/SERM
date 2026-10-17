"""Altirra file paths that are stored inside Altirra.ini profiles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root
from .altirra_config import AltirraConfigEditor


@dataclass(frozen=True, slots=True)
class AltirraPathOption:
    key: str
    label: str
    section: str
    description: str


class AltirraDirectoriesPage(QWidget):
    """Edit existing firmware/effect file paths without touching other sections."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    ROOT = "User\\Software\\virtualdub.org\\Altirra"
    PROFILE_ROOT = f"{ROOT}\\Profiles"
    ACTIVE_PROFILE = "@active"
    OPTIONS = (
        AltirraPathOption(
            "Kernel path",
            "Kernel / sistema operacional (arquivo ROM)",
            ACTIVE_PROFILE,
            "Imagem de firmware do sistema para o perfil ativo. Deixe vazio para usar o firmware interno do Altirra.",
        ),
        AltirraPathOption(
            "Basic path",
            "BASIC (arquivo ROM)",
            ACTIVE_PROFILE,
            "Imagem ROM do BASIC para o perfil ativo.",
        ),
        AltirraPathOption(
            "Display: Custom effect path",
            "Efeito personalizado de vídeo (arquivo)",
            f"{PROFILE_ROOT}\\00000000",
            "Arquivo de efeito personalizado de vídeo configurado pelo Altirra.",
        ),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.fields: dict[str, QLineEdit] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        group = QGroupBox("Caminhos definidos pelo Altirra.ini")
        form = QFormLayout(group)
        for option in self.OPTIONS:
            field = QLineEdit()
            field.setReadOnly(True)
            field.setPlaceholderText("Não configurado no Altirra.ini")
            field.setToolTip(option.description)
            self.fields[option.key] = field
            row = QHBoxLayout()
            row.addWidget(field, 1)
            browse = QPushButton("Selecionar arquivo")
            browse.clicked.connect(lambda _checked=False, key=option.key: self._browse(key))
            clear = QPushButton("Limpar")
            clear.clicked.connect(lambda _checked=False, key=option.key: self.fields[key].clear())
            row.addWidget(browse)
            row.addWidget(clear)
            form.addRow(option.label, row)
        self.status = QLabel()
        self.status.setWordWrap(True)
        form.addRow("Altirra.ini:", self.status)
        root.addWidget(group)
        info = QLabel(
            "Os caminhos são aplicados às chaves existentes do perfil correto. "
            "Salvar cria backup do Altirra.ini; nenhuma outra opção do arquivo é regravada."
        )
        info.setWordWrap(True)
        root.addWidget(info)
        apply_button = QPushButton("Aplicar caminhos")
        apply_button.clicked.connect(self.save)
        root.addWidget(apply_button)

    @classmethod
    def _config_path(cls) -> Path | None:
        try:
            payload = json.loads(cls.PATHS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        raw = payload.get("altirra_config") if isinstance(payload, dict) else None
        path = Path(str(raw)).expanduser() if raw else None
        return path if path and path.is_file() else None

    def _editor(self) -> AltirraConfigEditor | None:
        path = self._config_path()
        if path is None:
            return None
        try:
            return AltirraConfigEditor(path)
        except (OSError, UnicodeError):
            return None

    def _section(self, editor: AltirraConfigEditor, option: AltirraPathOption) -> str:
        if option.section == self.ACTIVE_PROFILE:
            return editor.active_profile_section()
        return option.section

    def refresh(self) -> None:
        editor = self._editor()
        if editor is None:
            self.status.setText("Não configurado ou arquivo indisponível")
            for field in self.fields.values():
                field.clear()
                field.setEnabled(False)
            return
        self.status.setText(str(editor.path))
        for option in self.OPTIONS:
            field = self.fields[option.key]
            field.setEnabled(False)
            values = editor.values(self._section(editor, option), option.key)
            if values:
                field.setEnabled(True)
                field.setText(values[0])

    def _browse(self, key: str) -> None:
        field = self.fields[key]
        current = field.text().strip()
        start = str(Path(current).parent) if current else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar arquivo de caminho do Altirra",
            start,
            "Arquivos ROM e efeitos (*.rom *.bin *.car *.fx *.fxhlsl);;Todos os arquivos (*)",
        )
        if path:
            field.setText(str(Path(path).resolve()))

    def save(self) -> None:
        editor = self._editor()
        if editor is None:
            QMessageBox.warning(
                self, "Altirra", "Selecione um Altirra.ini válido em 01-Diretórios."
            )
            return
        changed = 0
        try:
            for option in self.OPTIONS:
                section = self._section(editor, option)
                existing = editor.values(section, option.key)
                field = self.fields[option.key]
                if not existing or not field.isEnabled():
                    continue
                value = field.text().strip()
                if value != existing[0]:
                    editor.set_value(section, option.key, value)
                    changed += 1
            if not changed:
                QMessageBox.information(self, "Altirra", "Nenhuma alteração pendente.")
                return
            backup = editor.save()
        except (OSError, KeyError, ValueError) as exc:
            QMessageBox.critical(self, "Altirra", f"Falha ao aplicar os caminhos.\n\n{exc}")
            return
        self.refresh()
        QMessageBox.information(
            self, "Altirra", f"{changed} caminho(s) atualizado(s).\nBackup:\n{backup}"
        )


__all__ = ["AltirraDirectoriesPage", "AltirraPathOption"]
