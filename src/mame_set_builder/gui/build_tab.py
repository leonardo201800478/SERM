"""
Aba Construção – lista de ROM sets (máquinas) com checkboxes, seleção em massa e persistência.
"""

import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QProgressBar, QTextEdit, QMessageBox,
    QLineEdit, QFileDialog, QListWidget, QListWidgetItem,
    QLineEdit as QSearchLineEdit
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt

from ..sets.builder import SetBuilder
from .settings import Settings

logger = logging.getLogger(__name__)


class BuildWorker(QThread):
    progress = pyqtSignal(str)
    progress_value = pyqtSignal(int, int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, db_path, source_path, dest_path, machines, profile_name):
        super().__init__()
        self.db_path = db_path
        self.source_path = source_path
        self.dest_path = dest_path
        self.machines = machines
        self.profile_name = profile_name

    def run(self):
        try:
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row

            builder = SetBuilder(conn, None)
            manifest = builder.build(
                self.machines,
                self.source_path,
                self.dest_path,
                self.profile_name,
                progress_callback=lambda msg: self.progress.emit(msg)
            )
            conn.close()
            self.finished.emit({
                "manifest": manifest,
                "copied": len(manifest.required_files) - len(manifest.missing_files),
                "missing": len(manifest.missing_files),
                "total": len(manifest.required_files)
            })
        except Exception as e:
            self.error.emit(str(e))


class BuildTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.config = Settings.load()
        self.worker = None
        self._setup_ui()
        self._load_saved_selection()
        self._refresh_machines_from_filters()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Lista de ROM Sets (Máquinas) ---
        group_machines = QGroupBox("ROM Sets (Máquinas) - Ex.: pacman, sf2, mk")
        group_machines.setToolTip("Selecione os ROM sets (máquinas) que deseja incluir no Meu Set.\n"
                                  "As dependências (BIOS, devices, CHDs) serão resolvidas automaticamente.")
        machines_layout = QVBoxLayout(group_machines)

        # Barra de ferramentas: selecionar/deselecionar/atualizar
        btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Selecionar Todos")
        self.select_all_btn.clicked.connect(self._select_all)
        btn_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Desselecionar Todos")
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        btn_layout.addWidget(self.deselect_all_btn)

        btn_layout.addStretch()

        self.refresh_btn = QPushButton("Atualizar da Tabela de Filtros")
        self.refresh_btn.setToolTip("Adiciona à lista os ROM sets atualmente exibidos na aba 'Máquinas'.")
        self.refresh_btn.clicked.connect(self._refresh_machines_from_filters)
        btn_layout.addWidget(self.refresh_btn)

        machines_layout.addLayout(btn_layout)

        # Campo de busca (opcional)
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Buscar:"))
        self.search_edit = QSearchLineEdit()
        self.search_edit.setPlaceholderText("Filtrar lista...")
        self.search_edit.textChanged.connect(self._filter_list)
        search_layout.addWidget(self.search_edit)
        machines_layout.addLayout(search_layout)

        # Lista com checkboxes
        self.machines_list = QListWidget()
        self.machines_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.machines_list.itemChanged.connect(self._on_item_changed)
        machines_layout.addWidget(self.machines_list)

        # Adicionar/Remover manualmente
        add_layout = QHBoxLayout()
        self.add_machine_edit = QLineEdit()
        self.add_machine_edit.setPlaceholderText("Digite o nome do ROM set e pressione Enter")
        self.add_machine_edit.returnPressed.connect(self._add_machine_from_edit)
        add_layout.addWidget(self.add_machine_edit, 1)

        self.add_btn = QPushButton("Adicionar")
        self.add_btn.clicked.connect(self._add_machine_from_edit)
        add_layout.addWidget(self.add_btn)

        self.remove_btn = QPushButton("Remover Selecionados")
        self.remove_btn.setToolTip("Remove os itens atualmente selecionados na lista (não apenas os marcados).")
        self.remove_btn.clicked.connect(self._remove_selected)
        add_layout.addWidget(self.remove_btn)

        machines_layout.addLayout(add_layout)

        layout.addWidget(group_machines)

        # --- Caminhos ---
        group_paths = QGroupBox("Caminhos")
        paths_layout = QVBoxLayout(group_paths)

        src_layout = QHBoxLayout()
        src_layout.addWidget(QLabel("FULLSET (origem):"))
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Caminho do FULLSET (ex.: I:/ROMS/MAME)")
        src_layout.addWidget(self.source_edit, 1)
        src_btn = QPushButton("...")
        src_btn.clicked.connect(lambda: self._browse_folder(self.source_edit))
        src_layout.addWidget(src_btn)
        paths_layout.addLayout(src_layout)

        dst_layout = QHBoxLayout()
        dst_layout.addWidget(QLabel("Meu Set (destino):"))
        self.dest_edit = QLineEdit()
        self.dest_edit.setPlaceholderText("Caminho de destino (ex.: D:/MEU_SET)")
        dst_layout.addWidget(self.dest_edit, 1)
        dst_btn = QPushButton("...")
        dst_btn.clicked.connect(lambda: self._browse_folder(self.dest_edit))
        dst_layout.addWidget(dst_btn)
        paths_layout.addLayout(dst_layout)

        layout.addWidget(group_paths)

        # --- Botão Construir ---
        self.build_btn = QPushButton("Construir Meu Set")
        self.build_btn.setToolTip("Inicia a construção copiando apenas os ROM sets selecionados e suas dependências.")
        self.build_btn.clicked.connect(self.start_build)
        layout.addWidget(self.build_btn)

        # --- Progresso ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)

        # --- Log ---
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        layout.addStretch()

        # Carregar caminhos das configurações
        self.source_edit.setText(self.config.get("fullset_path", ""))
        self.dest_edit.setText(self.config.get("destination_path", ""))

    def _browse_folder(self, line_edit):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar pasta")
        if folder:
            line_edit.setText(folder)

    def _is_valid_machine_name(self, name: str) -> bool:
        """
        Verifica se o nome parece ser um ROM set válido (não um arquivo com extensão).
        Nomes de máquinas MAME são alfanuméricos, sem extensões.
        """
        if not name:
            return False
        # Ignora se contém extensão de arquivo
        invalid_extensions = ('.6e', '.7f', '.bin', '.rom', '.zip', '.chd', '.img', '.iso', '.cue', '.wav', '.png', '.json')
        if any(name.lower().endswith(ext) for ext in invalid_extensions):
            return False
        # Ignora se contém ponto (provavelmente é um arquivo)
        if '.' in name:
            return False
        # Ignora se tiver espaços ou caracteres estranhos (nomes de máquinas são geralmente sem espaços)
        # Mas alguns têm hífen ou underline – permitimos.
        return True

    def _refresh_machines_from_filters(self):
        """Carrega ROM sets da tabela de filtros e adiciona à lista (apenas nomes válidos)."""
        machines = self._get_filtered_machines()
        if not machines:
            return

        existing = {self.machines_list.item(i).text().lower()
                    for i in range(self.machines_list.count())}

        for m in machines:
            if not self._is_valid_machine_name(m):
                continue
            if m.lower() not in existing:
                item = QListWidgetItem(m)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                self.machines_list.addItem(item)
                existing.add(m.lower())

        self._save_selection()
        self._update_count()

    def _add_machine_from_edit(self):
        name = self.add_machine_edit.text().strip()
        if not name:
            return
        if not self._is_valid_machine_name(name):
            QMessageBox.warning(self, "Nome inválido",
                                f"'{name}' não parece ser um nome de ROM set válido.\n"
                                "Use nomes como 'pacman', 'sf2', 'neogeo'.")
            self.add_machine_edit.clear()
            return

        existing = {self.machines_list.item(i).text().lower()
                    for i in range(self.machines_list.count())}
        if name.lower() in existing:
            QMessageBox.information(self, "Duplicado", f"O ROM set '{name}' já está na lista.")
            self.add_machine_edit.clear()
            return

        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        self.machines_list.addItem(item)
        self.add_machine_edit.clear()
        self._save_selection()
        self._update_count()

    def _remove_selected(self):
        """Remove os itens selecionados na lista (não apenas os marcados)."""
        items_to_remove = []
        for item in self.machines_list.selectedItems():
            items_to_remove.append(item)
        for item in items_to_remove:
            row = self.machines_list.row(item)
            self.machines_list.takeItem(row)
        self._save_selection()
        self._update_count()

    def _select_all(self):
        for i in range(self.machines_list.count()):
            self.machines_list.item(i).setCheckState(Qt.CheckState.Checked)
        self._save_selection()
        self._update_count()

    def _deselect_all(self):
        for i in range(self.machines_list.count()):
            self.machines_list.item(i).setCheckState(Qt.CheckState.Unchecked)
        self._save_selection()
        self._update_count()

    def _filter_list(self, text: str):
        """Filtra os itens da lista pelo texto de busca."""
        text = text.lower()
        for i in range(self.machines_list.count()):
            item = self.machines_list.item(i)
            item.setHidden(text not in item.text().lower())

    def _on_item_changed(self, item):
        self._save_selection()
        self._update_count()

    def _save_selection(self):
        """Salva os nomes dos ROM sets marcados no Settings."""
        selected = []
        for i in range(self.machines_list.count()):
            item = self.machines_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        self.config["build_selected_machines"] = selected
        Settings.save(self.config)

    def _load_saved_selection(self):
        """Carrega a lista salva e marca os itens conforme salvo."""
        saved = self.config.get("build_selected_machines", [])
        if not saved:
            return
        existing = {self.machines_list.item(i).text().lower()
                    for i in range(self.machines_list.count())}
        for m in saved:
            if m.lower() not in existing:
                item = QListWidgetItem(m)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                self.machines_list.addItem(item)
                existing.add(m.lower())
        # Aplicar check states conforme salvo
        for i in range(self.machines_list.count()):
            item = self.machines_list.item(i)
            if item.text() in saved:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
        self._update_count()

    def _update_count(self):
        """Atualiza o título do grupo com a contagem de itens selecionados."""
        selected = 0
        total = self.machines_list.count()
        for i in range(total):
            if self.machines_list.item(i).checkState() == Qt.CheckState.Checked:
                selected += 1
        parent = self.machines_list.parent()
        while parent and not isinstance(parent, QGroupBox):
            parent = parent.parent()
        if parent:
            parent.setTitle(f"ROM Sets (Máquinas) - {selected}/{total} selecionados")

    def _get_filtered_machines(self):
        """Obtém a lista de ROM sets da tabela de máquinas (primeira coluna)."""
        if hasattr(self.main_window, 'machines_table'):
            table = self.main_window.machines_table
            machines = []
            for row in range(table.rowCount()):
                item = table.item(row, 0)  # coluna 0 = nome da máquina
                if item:
                    machines.append(item.text())
            return machines
        return []

    def start_build(self):
        """Inicia a construção com os ROM sets marcados."""
        selected = []
        for i in range(self.machines_list.count()):
            item = self.machines_list.item(i)
            if item.checkState() == Qt.CheckState.Checked and not item.isHidden():
                selected.append(item.text())

        if not selected:
            QMessageBox.warning(self, "Aviso", "Nenhum ROM set selecionado.")
            return

        source_path = Path(self.source_edit.text().strip())
        if not source_path.exists():
            QMessageBox.warning(self, "Erro", f"FULLSET não encontrado: {source_path}")
            return
        dest_path = Path(self.dest_edit.text().strip())
        if not dest_path.exists():
            try:
                dest_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Não foi possível criar o destino: {e}")
                return

        self.build_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setVisible(True)
        self.progress_label.setText("Iniciando...")
        self.log_text.clear()

        profile_name = self.main_window.config_tab.get_config().get("profile_name", "Custom")
        self.worker = BuildWorker(
            self.main_window.db_path,
            source_path,
            dest_path,
            selected,
            profile_name
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.progress_value.connect(self._on_progress_value)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, msg):
        self.progress_label.setText(msg)

    def _on_progress_value(self, value, max_val):
        self.progress_bar.setMaximum(max_val)
        self.progress_bar.setValue(value)

    def _on_finished(self, result):
        self.build_btn.setEnabled(True)
        self.progress_label.setText("Concluído!")
        self.log_text.append(f"✅ ROM sets processados: {len(result['manifest'].selected_machines)}")
        self.log_text.append(f"📦 Arquivos copiados: {result['copied']}")
        self.log_text.append(f"❌ Arquivos faltantes: {result['missing']}")
        self.log_text.append(f"📊 Total de arquivos requeridos: {result['total']}")
        if result['missing'] > 0:
            self.log_text.append("\nArquivos faltantes (exemplo):")
            for f in result.get('manifest', {}).missing_files[:10]:
                self.log_text.append(f"  - {f}")
            if len(result['manifest'].missing_files) > 10:
                self.log_text.append(f"  ... e mais {len(result['manifest'].missing_files) - 10} arquivos.")
        QMessageBox.information(self, "Construção concluída",
                                f"Copiados: {result['copied']}\nFaltantes: {result['missing']}")

    def _on_error(self, err):
        self.build_btn.setEnabled(True)
        self.progress_label.setText("❌ Erro!")
        self.log_text.append(f"ERRO: {err}")
        QMessageBox.critical(self, "Erro", f"Falha na construção:\n{err}")