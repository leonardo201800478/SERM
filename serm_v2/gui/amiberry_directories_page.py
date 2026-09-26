"""Directory settings stored in Amiberry's native amiberry.conf file."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
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
from .directories_guide_page import ConfigFileEditor
from .directory_dialogs import get_existing_directory


class AmiberryDirectoriesPage(QWidget):
    PATHS_FILE = data_root() / "emulator_paths.json"
    OPTIONS = (
        ("base_content_path", "Conteúdo base", "dir"),
        ("retroarch_config", "Configuração RetroArch", "file"),
        ("floppy_sounds_dir", "Sons de disquete", "dir"),
        ("plugins_dir", "Plugins", "dir"),
        ("config_path", "Configurações do Amiberry", "dir"),
        ("controllers_path", "Controles", "dir"),
        ("whdboot_path", "WHDLoad / WHDBoot", "dir"),
        ("whdload_arch_path", "Arquivos WHDLoad (.lha)", "dir"),
        ("floppy_path", "Disquetes", "dir"),
        ("harddrive_path", "Discos rígidos", "dir"),
        ("cdrom_path", "CD-ROMs", "dir"),
        ("rom_path", "ROMs / Kickstart", "dir"),
        ("rp9_path", "Pacotes RP9", "dir"),
        ("saveimage_dir", "Imagens de salvamento", "dir"),
        ("savestate_dir", "Estados salvos", "dir"),
        ("ripper_path", "Ripper", "dir"),
        ("inputrecordings_dir", "Gravações de entrada", "dir"),
        ("screenshot_dir", "Capturas de tela", "dir"),
        ("nvram_dir", "NVRAM", "dir"),
        ("video_dir", "Vídeos", "dir"),
        ("themes_path", "Temas", "dir"),
        ("shaders_path", "Shaders", "dir"),
        ("bezels_path", "Bezels", "dir"),
        ("logfile_path", "Arquivo de log", "file"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fields: dict[str, QLineEdit] = {}
        root = QVBoxLayout(self)
        group = QGroupBox("Diretórios definidos em amiberry.conf")
        form = QFormLayout(group)
        for key, label, kind in self.OPTIONS:
            edit = QLineEdit()
            edit.setEnabled(False)
            button = QPushButton("Selecionar arquivo" if kind == "file" else "Selecionar pasta")
            button.clicked.connect(lambda _=False, k=key, t=kind: self._browse(k, t))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(button)
            form.addRow(label, row)
            self.fields[key] = edit
        self.status = QLabel()
        self.status.setWordWrap(True)
        form.addRow("Arquivo:", self.status)
        choose_conf = QPushButton("Selecionar amiberry.conf")
        choose_conf.clicked.connect(self._select_config)
        form.addRow("Configuração nativa:", choose_conf)
        root.addWidget(group)
        inventory = QGroupBox("Instalação Amiberry reconhecida")
        inventory_layout = QFormLayout(inventory)
        self.inventory_labels: dict[str, QLabel] = {}
        for name in (
            "Amiberry.exe",
            "amiberry.portable",
            "amiberry.conf",
            "amiberry.ini",
            "Settings",
            "CDROMs",
            "Configurations",
            "Controllers",
            "data",
            "Floppies",
            "HardDrives",
            "InputRecordings",
            "LHA",
            "NVRAM",
            "plugins",
            "Ripper",
            "ROMs",
            "RP9",
            "SaveStates",
            "Screenshots",
            "Videos",
            "Visuals",
            "WHDBoot",
            "unins000.exe",
            "unins000.dat",
            "libc++.dll",
            "libcurl.dll",
            "libFLAC.dll",
            "libmpg123.dll",
            "libogg.dll",
            "libpng16.dll",
            "libunwind.dll",
            "libwinpthread-1.dll",
            "libz.dll",
            "libzstd.dll",
            "SDL3.dll",
            "SDL3_image.dll",
        ):
            label = QLabel()
            label.setTextInteractionFlags(
                label.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse
            )
            self.inventory_labels[name] = label
            inventory_layout.addRow(name, label)
        root.addWidget(inventory)
        note = QLabel(
            "São exibidas apenas as chaves de caminho existentes no arquivo. Aplicar cria backup .bak; as entradas WHDLoad recentes e outras opções permanecem intactas."
        )
        note.setWordWrap(True)
        root.addWidget(note)
        save = QPushButton("Aplicar diretórios")
        save.clicked.connect(self.save)
        root.addWidget(save)
        root.addStretch(1)
        self.refresh()

    @classmethod
    def _paths(cls):
        try:
            value = json.loads(cls.PATHS_FILE.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _config(self):
        paths = self._paths()
        raw = paths.get("amiberry_conf")
        root = Path(str(paths.get("amiberry", ""))) if paths.get("amiberry") else None
        candidates = [Path(str(raw))] if raw else []
        if root:
            candidates += [root / "Settings" / "amiberry.conf", root / "amiberry.conf"]
        path = next((p for p in candidates if p.is_file()), None)
        try:
            return ConfigFileEditor(path) if path else None
        except (OSError, UnicodeError):
            return None

    def refresh(self):
        editor = self._config()
        paths = self._paths()
        emulator_root = Path(str(paths.get("amiberry", ""))) if paths.get("amiberry") else None
        for name, label in self.inventory_labels.items():
            relative = (
                Path("Settings") / name if name in {"amiberry.conf", "amiberry.ini"} else Path(name)
            )
            candidate = emulator_root / relative if emulator_root else None
            label.setText(str(candidate) if candidate and candidate.exists() else "Não encontrado")
        self.status.setText(
            str(editor.path) if editor else "amiberry.conf não configurado / não encontrado"
        )
        for key, field in self.fields.items():
            values = editor.values(key) if editor else []
            field.setEnabled(bool(values))
            field.setText(values[0] if values else "")

    def _browse(self, key, kind):
        current = self.fields[key].text()
        if kind == "file":
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar arquivo",
                str(Path(current).parent) if current else str(Path.home()),
            )
        else:
            path = get_existing_directory(
                self, "Selecionar diretório", current or str(Path.home())
            )
        if path:
            self.fields[key].setText(str(Path(path).resolve()))

    def _select_config(self):
        current = self._paths().get("amiberry_conf")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar amiberry.conf",
            str(Path(str(current)).parent) if current else str(Path.home()),
            "Amiberry config (amiberry.conf);;Todos os arquivos (*)",
        )
        if not path:
            return
        config = Path(path)
        if config.name.casefold() != "amiberry.conf":
            QMessageBox.warning(self, "Amiberry", "Selecione o arquivo amiberry.conf.")
            return
        data = self._paths()
        data["amiberry_conf"] = str(config.resolve())
        self.PATHS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.PATHS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        self.refresh()

    def save(self):
        editor = self._config()
        if not editor:
            QMessageBox.warning(self, "Amiberry", "Configure amiberry.conf em 01-Diretórios.")
            return
        changed = 0
        try:
            for key, field in self.fields.items():
                old = editor.values(key)
                if old and field.isEnabled() and field.text().strip() != old[0]:
                    editor.set_value(key, field.text().strip())
                    changed += 1
            if not changed:
                QMessageBox.information(self, "Amiberry", "Nenhuma alteração pendente.")
                return
            backup = editor.save()
        except (OSError, KeyError, ValueError) as exc:
            QMessageBox.critical(self, "Amiberry", f"Falha ao aplicar diretórios.\n\n{exc}")
            return
        self.refresh()
        QMessageBox.information(
            self, "Amiberry", f"{changed} caminho(s) atualizados.\nBackup:\n{backup}"
        )
