"""Gerenciamento dos diretórios nativos do RetroArch."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config.app_config import AppConfig


class RetroArchDirectoriesTab(QWidget):
    """Seleciona o retroarch.exe e importa os diretórios do retroarch.cfg."""

    PATHS = (
        ("config", "Configuração / overrides"),
        ("cores", "Cores libretro"),
        ("system", "System / BIOS"),
        ("assets", "Assets"),
        ("shaders", "Shaders"),
        ("saves", "Save files"),
        ("states", "Save states"),
        ("downloads", "Core assets / downloads"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        self.edits: dict[str, QLineEdit] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta a interface de descoberta e diagnóstico dos diretórios."""
        layout = QVBoxLayout(self)
        anchor = QGroupBox("Instalação do RetroArch")
        anchor_form = QFormLayout(anchor)
        self.executable_edit = QLineEdit()
        choose_exe = QPushButton("Selecionar retroarch.exe")
        choose_exe.clicked.connect(self._choose_executable)
        row = QHBoxLayout(); row.addWidget(self.executable_edit, 1); row.addWidget(choose_exe)
        anchor_form.addRow("Executável:", row)
        self.cfg_label = QLabel(); self.cfg_label.setWordWrap(True); anchor_form.addRow("retroarch.cfg:", self.cfg_label)
        self.source_label = QLabel("Fonte: ainda não importada"); self.source_label.setWordWrap(True); anchor_form.addRow("Fonte:", self.source_label)
        layout.addWidget(anchor)

        group = QGroupBox("Diretórios importados do retroarch.cfg")
        form = QFormLayout(group)
        for key, label in self.PATHS:
            edit = QLineEdit(); edit.setReadOnly(True); edit.setToolTip("Importado do retroarch.cfg; altere pelo próprio RetroArch para manter uma única fonte de verdade.")
            form.addRow(f"{label}:", edit); self.edits[key] = edit
        layout.addWidget(group)

        core_group = QGroupBox("Estrutura por core")
        core_form = QFormLayout(core_group)
        self.core_config_label, self.core_remap_label, self.core_shader_label = QLabel(), QLabel(), QLabel()
        for label in (self.core_config_label, self.core_remap_label, self.core_shader_label): label.setWordWrap(True)
        core_form.addRow("Overrides / opções:", self.core_config_label); core_form.addRow("Remaps:", self.core_remap_label); core_form.addRow("Shaders automáticos:", self.core_shader_label)
        layout.addWidget(core_group)

        actions = QHBoxLayout()
        import_button = QPushButton("Importar / atualizar do retroarch.cfg"); import_button.clicked.connect(self.import_config); actions.addWidget(import_button)
        self.save_button = QPushButton("Salvar configurações do ARCADE MANAGER"); self.save_button.clicked.connect(self.save_settings); actions.addWidget(self.save_button)
        actions.addStretch(); layout.addLayout(actions)
        self.status_label = QLineEdit(); self.status_label.setReadOnly(True); self.status_label.setPlaceholderText("Status"); layout.addWidget(self.status_label); layout.addStretch()

    def refresh(self) -> None:
        """Carrega a âncora e os diretórios já importados."""
        self.config.load()
        self.executable_edit.setText(str(self.config.retroarch_path or ""))
        self.cfg_label.setText(str(self.config.retroarch_config_file or "não encontrado"))
        self.source_label.setText("Fonte: retroarch.cfg nativo — somente leitura pelo ARCADE MANAGER" if self.config.retroarch_config_file else "Fonte: ainda não importada")
        for key, edit in self.edits.items():
            value = self.config.get_emulator_path("retroarch", key); edit.setText(str(value) if value else "")
        root = self.config.retroarch_core_config_dir; remaps = self.config.retroarch_core_remap_dir
        self.core_config_label.setText(str(root or "não descoberto")); self.core_remap_label.setText(str(remaps or "não descoberto"))
        self.core_shader_label.setText(str(root or "não descoberto") + "\\<core>\\<game>.slangp/.glslp/.cgp" if root else "não descoberto")
        self.status_label.setText("Diretórios importados do RetroArch. Configuração do ARCADE MANAGER salva automaticamente ao importar." if self.config.retroarch_config_file else "Selecione o retroarch.exe para começar.")

    def _choose_executable(self) -> None:
        """Seleciona retroarch.exe como âncora da instalação."""
        current = self.executable_edit.text().strip() or str(Path.home())
        selected, _ = QFileDialog.getOpenFileName(self, "Selecionar retroarch.exe", current, "RetroArch (retroarch.exe);;Executáveis (*.exe)")
        if selected:
            self.executable_edit.setText(selected); self.import_config()

    def import_config(self) -> None:
        """Lê o retroarch.cfg associado ao executável selecionado e persiste a descoberta."""
        value = self.executable_edit.text().strip()
        if not value:
            self.status_label.setText("Selecione o retroarch.exe primeiro."); return
        try:
            native = self.config.set_retroarch_executable(Path(value)); self.config.save(); self.refresh()
            self.status_label.setText(f"Importação concluída e salva: {len(native)} diretórios encontrados no retroarch.cfg.")
            parent = self.parent_window
            if parent is not None and hasattr(parent, "retroarch_home_tab"): parent.retroarch_home_tab.refresh()
            if parent is not None and hasattr(parent, "retroarch_catalog_tab"): parent.retroarch_catalog_tab.refresh()
        except (FileNotFoundError, OSError, ValueError) as exc:
            self.status_label.setText(f"Falha na importação: {exc}")

    def save_settings(self) -> None:
        """Persiste explicitamente a descoberta no arquivo de configuração do ARCADE MANAGER."""
        try:
            value = self.executable_edit.text().strip()
            if value:
                self.config.set_retroarch_executable(Path(value))
            self.config.save()
            self.status_label.setText("Configurações do ARCADE MANAGER salvas. O retroarch.cfg nativo não foi alterado.")
        except (FileNotFoundError, OSError, ValueError) as exc:
            self.status_label.setText(f"Falha ao salvar: {exc}")


__all__ = ["RetroArchDirectoriesTab"]
