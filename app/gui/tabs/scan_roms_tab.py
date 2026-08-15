# app/gui/tabs/scan_roms_tab.py
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QProgressBar, QTreeWidget, QTreeWidgetItem,
    QGroupBox, QGridLayout, QMessageBox, QDialog,
    QComboBox, QDialogButtonBox, QFormLayout, QTextEdit,
    QSplitter, QPlainTextEdit
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject

from app.core.models.scan_result import ScanResult, MachineScanResult, ScanStatus
from app.core.models.filter_profile import FilterProfile
from app.core.services.listxml_export_service import ListxmlExportService
from app.core.services.rom_scan_service import RomScanService
from app.core.services.filter_service import FilterService
from app.database.repositories.filter_profile_repository import FilterProfileRepository
from app.config.app_config import AppConfig
from app.database.database import Database


class ScanLogEmitter(QObject):
    """Emite sinais para atualizar o log de escaneamento."""
    log_line = Signal(str)
    progress = Signal(int, str)  # valor, mensagem


class ProfileSelectionDialog(QDialog):
    """Diálogo para selecionar o perfil que será usado na geração do LISTXML."""

    def __init__(self, profiles: List[FilterProfile], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Selecionar perfil de filtro")
        self.setMinimumWidth(520)

        self.profiles = profiles
        self.selected_profile: Optional[FilterProfile] = None

        layout = QVBoxLayout(self)

        layout.addWidget(
            QLabel("Selecione o perfil de filtro que será utilizado para gerar o XML:")
        )

        self.combo = QComboBox()
        for profile in profiles:
            suffix = " [Padrão]" if profile.is_default else ""
            self.combo.addItem(f"{profile.name}{suffix}", profile.id)

        layout.addWidget(self.combo)

        self.description = QTextEdit()
        self.description.setReadOnly(True)
        self.description.setMaximumHeight(90)
        layout.addWidget(self.description)

        self.combo.currentIndexChanged.connect(self._update_description)
        self._update_description(0)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_description(self, index: int) -> None:
        """Atualiza a descrição e um resumo dos critérios do perfil selecionado."""
        if index < 0 or index >= len(self.profiles):
            self.description.clear()
            return

        profile = self.profiles[index]
        criteria = profile.criteria

        excluded = ", ".join(criteria.exclude_categories) or "Nenhuma"
        included = ", ".join(criteria.include_categories) or "Nenhuma"
        statuses = ", ".join(criteria.emulation_status) or "Todos"

        self.description.setPlainText(
            f"Descrição: {profile.description or 'Sem descrição'}\n"
            f"Estado: {statuses}\n"
            f"Categorias incluídas: {included}\n"
            f"Categorias excluídas: {excluded}\n"
            f"Clones: {'Sim' if criteria.include_clones else 'Não'} | "
            f"BIOS: {'Sim' if criteria.include_bios else 'Não'} | "
            f"Devices: {'Sim' if criteria.include_devices else 'Não'} | "
            f"CHDs: {'Sim' if criteria.include_chd else 'Não'}"
        )

    def get_selected_profile(self) -> Optional[FilterProfile]:
        """Retorna o perfil correspondente à opção selecionada."""
        index = self.combo.currentIndex()
        if index < 0 or index >= len(self.profiles):
            return None
        return self.profiles[index]


class ScanRomsTab(QWidget):
    """Aba responsável por gerar o LISTXML filtrado e escanear as ROMs."""

    def __init__(self, parent=None, db: Optional[Database] = None):
        super().__init__(parent)

        self.parent = parent
        self.config = AppConfig()
        self.db = db
        self.scan_result: Optional[ScanResult] = None
        self.scanning = False
        self.filtered_xml_path: Optional[Path] = None
        self.selected_profile: Optional[FilterProfile] = None
        self.log_emitter = ScanLogEmitter()

        self.setup_ui()
        self.update_ui_state()

        # Conecta sinais de log
        self.log_emitter.log_line.connect(self._append_log)
        self.log_emitter.progress.connect(self._update_progress)

    def setup_ui(self):
        """Cria os controles da aba Scan Roms."""
        main_layout = QVBoxLayout(self)

        # --- Topo: botões ---
        top_layout = QHBoxLayout()

        self.btn_generate = QPushButton("Gerar LISTXML filtrado")
        self.btn_generate.clicked.connect(self.generate_filtered_xml)

        self.btn_scan = QPushButton("Iniciar escaneamento")
        self.btn_scan.clicked.connect(self.start_scan)

        self.btn_stop = QPushButton("Parar")
        self.btn_stop.clicked.connect(self.stop_scan)
        self.btn_stop.setEnabled(False)

        top_layout.addWidget(self.btn_generate)
        top_layout.addWidget(self.btn_scan)
        top_layout.addWidget(self.btn_stop)
        top_layout.addStretch()
        main_layout.addLayout(top_layout)

        # --- Perfil selecionado ---
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("Perfil:"))
        self.profile_label = QLabel("Nenhum perfil selecionado")
        self.profile_label.setStyleSheet("font-weight: bold;")
        profile_layout.addWidget(self.profile_label)
        profile_layout.addStretch()
        main_layout.addLayout(profile_layout)

        # --- Arquivo XML ---
        xml_layout = QHBoxLayout()
        xml_layout.addWidget(QLabel("Arquivo:"))
        self.xml_label = QLabel("Nenhum arquivo gerado")
        self.xml_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        xml_layout.addWidget(self.xml_label)
        main_layout.addLayout(xml_layout)

        # --- Resumo ---
        summary_group = QGroupBox("RESUMO")
        summary_layout = QGridLayout(summary_group)

        self.summary_labels = {}
        categories = [
            ("ROMs", "roms_total"),
            ("BIOS", "bios_total"),
            ("DEVICES", "devices_total"),
            ("CHDs", "chds_total"),
            ("🟢 OK", "ok_count"),
            ("🟡 Corrigíveis", "fixable_count"),
            ("🔴 Ausentes", "missing_count"),
            ("⬛ Corrompidos", "corrupted_count"),
        ]

        for idx, (label, key) in enumerate(categories):
            row, col = divmod(idx, 4)
            summary_layout.addWidget(QLabel(f"{label}:"), row, col * 2)

            lbl = QLabel("0")
            lbl.setStyleSheet("font-weight: bold;")
            self.summary_labels[key] = lbl
            summary_layout.addWidget(lbl, row, col * 2 + 1)

        main_layout.addWidget(summary_group)

        # --- Barra de progresso ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Pronto")
        main_layout.addWidget(self.status_label)

        # --- Splitter: árvore + logs ---
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Árvore
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["ROM", "Jogo", "Tamanho", "CRC", "Status"])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 200)
        self.tree.setColumnWidth(2, 100)
        self.tree.setColumnWidth(3, 120)
        self.tree.setColumnWidth(4, 100)
        self.tree.itemDoubleClicked.connect(self.on_tree_double_click)
        splitter.addWidget(self.tree)

        # Painel de logs
        log_group = QGroupBox("Log de escaneamento")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(5000)  # Limita histórico
        # Configurar fonte (corrigido)
        font = self.log_text.font()
        font.setFamily("Consolas")
        font.setPointSize(9)
        self.log_text.setFont(font)
        log_layout.addWidget(self.log_text)

        splitter.addWidget(log_group)

        # Define proporções iniciais (70% árvore, 30% logs)
        splitter.setSizes([500, 200])

        main_layout.addWidget(splitter)

    def update_ui_state(self):
        """Atualiza os estados dos botões conforme o estado atual da operação."""
        has_xml = self.filtered_xml_path is not None and self.filtered_xml_path.exists()
        self.btn_scan.setEnabled(has_xml and not self.scanning)
        self.btn_stop.setEnabled(self.scanning)
        self.btn_generate.setEnabled(not self.scanning)

    def _append_log(self, message: str):
        """Adiciona uma linha ao log."""
        self.log_text.appendPlainText(message)
        # Rola para o final
        self.log_text.ensureCursorVisible()

    def _update_progress(self, value: int, message: str):
        """Atualiza a barra de progresso e o status."""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)

    def _get_profiles(self) -> List[FilterProfile]:
        """Carrega os perfis armazenados no banco de dados."""
        if self.db is None or self.db.conn is None:
            raise RuntimeError("Banco de dados não está conectado.")

        repository = FilterProfileRepository(self.db.conn)
        return repository.get_all()

    def _select_profile(self) -> Optional[FilterProfile]:
        profiles = self._get_profiles()

        if not profiles:
            QMessageBox.warning(
                self,
                "Nenhum perfil",
                "Não existem perfis de filtro salvos.\n\n"
                "Crie e salve um perfil na aba 'Filtragem' antes de gerar "
                "o LISTXML filtrado."
            )
            return None

        dialog = ProfileSelectionDialog(profiles, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        profile = dialog.get_selected_profile()
        if profile is None:
            QMessageBox.warning(
                self,
                "Perfil inválido",
                "Não foi possível identificar o perfil selecionado."
            )
            return None

        return profile

    def generate_filtered_xml(self):
        if self.scanning:
            return

        self.status_label.setText("Selecionando perfil...")
        self.btn_generate.setEnabled(False)

        try:
            profile = self._select_profile()
            if profile is None:
                self.status_label.setText("Geração cancelada.")
                return

            self.selected_profile = profile
            self.profile_label.setText(profile.name)
            self.profile_label.setToolTip(profile.description or profile.name)

            self.status_label.setText(
                f"Aplicando perfil '{profile.name}'..."
            )

            service = ListxmlExportService(
                self.config.db_path,
                self.config.mame_path,
            )

            machine_names = service.get_machine_names_from_criteria(
                profile.criteria
            )

            if not machine_names:
                QMessageBox.warning(
                    self,
                    "Nenhuma máquina",
                    f"O perfil '{profile.name}' não retornou nenhuma máquina."
                )
                self.status_label.setText("Nenhuma máquina encontrada.")
                return

            version = self._get_mame_version()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mame_{version}_filtered_{timestamp}.xml"

            output_path = self.config.PROJECT_ROOT / "data" / "scans" / filename

            self.status_label.setText(
                f"Gerando XML com {len(machine_names):,} máquinas..."
            )

            service.generate_filtered_xml(machine_names, output_path)

            self.filtered_xml_path = output_path
            self.xml_label.setText(str(output_path))
            self.xml_label.setStyleSheet("color: green;")
            self.status_label.setText(
                f"XML gerado: {output_path.name}"
            )

            QMessageBox.information(
                self,
                "Sucesso",
                f"LISTXML filtrado gerado com sucesso.\n\n"
                f"Perfil: {profile.name}\n"
                f"Máquinas: {len(machine_names):,}\n\n"
                f"Arquivo:\n{output_path}"
            )

        except Exception as e:
            self.status_label.setText(f"Erro: {e}")
            QMessageBox.critical(
                self,
                "Erro",
                f"Erro ao gerar XML:\n{e}"
            )
        finally:
            self.btn_generate.setEnabled(True)
            self.update_ui_state()

    def start_scan(self):
        if not self.filtered_xml_path or not self.filtered_xml_path.exists():
            QMessageBox.critical(
                self,
                "Erro",
                "Nenhum XML filtrado disponível."
            )
            return

        if self.scanning:
            return

        # Limpa logs e árvore
        self.log_text.clear()
        self.tree.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("Iniciando escaneamento...")
        self._append_log("=== Início do escaneamento ===")
        self._append_log(f"XML filtrado: {self.filtered_xml_path}")

        self.scanning = True
        self.update_ui_state()

        import threading
        self.scan_thread = threading.Thread(target=self._do_scan, daemon=True)
        self.scan_thread.start()

    def _do_scan(self):
        try:
            rom_paths = self._get_rom_paths()
            if not rom_paths:
                self.log_emitter.log_line.emit("⚠️ Nenhum diretório de ROMs configurado!")
                QTimer.singleShot(0, lambda: self._show_scan_error(
                    "Nenhum diretório de ROMs encontrado.\n"
                    "Configure os caminhos na aba 'Diretórios'."
                ))
                return

            self.log_emitter.log_line.emit(f"📁 Diretórios de ROMs: {', '.join(str(p) for p in rom_paths)}")

            scanner_service = RomScanService(rom_paths, log_emitter=self.log_emitter)
            result = scanner_service.scan_machines(self.filtered_xml_path)

            QTimer.singleShot(0, lambda r=result: self._show_scan_result(r))

        except Exception as e:
            QTimer.singleShot(
                0,
                lambda: self._show_scan_error(str(e))
            )

    def _show_scan_result(self, result: ScanResult):
        self.scan_result = result
        self.tree.clear()

        machine_results = getattr(result, "machines", None) or []
        total = len(machine_results)

        for idx, machine_result in enumerate(machine_results, start=1):
            self._add_machine_to_tree(machine_result)
            progress = int(idx / total * 100) if total else 100
            self.progress_bar.setValue(progress)

        self._update_summary_from_result(result)

        # Salva resultados em arquivo JSON
        self._save_scan_results(result)

        self.scanning = False
        self.update_ui_state()
        self.progress_bar.setValue(100)
        self.status_label.setText("Escaneamento concluído")
        self.log_emitter.log_line.emit("=== Escaneamento finalizado ===")
        self.log_emitter.log_line.emit(
            f"✅ {result.ok_count} OK | "
            f"🟡 {result.fixable_count} Corrigíveis | "
            f"🔴 {result.missing_count} Ausentes | "
            f"⬛ {result.corrupted_count} Corrompidos"
        )

        QMessageBox.information(
            self,
            "Escaneamento concluído",
            f"Escaneamento finalizado!\n\n"
            f"Total de máquinas: {result.total_machines}\n"
            f"✅ OK: {result.ok_count}\n"
            f"🟡 Corrigíveis: {result.fixable_count}\n"
            f"🔴 Ausentes: {result.missing_count}\n"
            f"⬛ Corrompidos: {result.corrupted_count}\n\n"
            f"Resultados salvos em:\n"
            f"{self.config.PROJECT_ROOT / 'data' / 'scans' / 'scan_results_{timestamp}.json'}"
        )

    def _save_scan_results(self, result: ScanResult):
        """Salva os resultados do escaneamento em um arquivo JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scan_results_{timestamp}.json"
        output_path = self.config.PROJECT_ROOT / "data" / "scans" / filename

        data = {
            "version": result.version,
            "timestamp": timestamp,
            "total_machines": result.total_machines,
            "summary": {
                "roms_total": result.roms_total,
                "bios_total": result.bios_total,
                "devices_total": result.devices_total,
                "chds_total": result.chds_total,
                "ok_count": result.ok_count,
                "fixable_count": result.fixable_count,
                "missing_count": result.missing_count,
                "corrupted_count": result.corrupted_count,
            },
            "machines": []
        }

        for machine in result.machines:
            machine_data = {
                "name": machine.name,
                "description": machine.description,
                "cloneof": machine.cloneof,
                "status": machine.status.value,
                "total_size": machine.total_size,
                "roms": []
            }
            for rom in machine.roms:
                machine_data["roms"].append({
                    "name": rom.name,
                    "size": rom.size,
                    "crc": rom.crc,
                    "sha1": rom.sha1,
                    "merge": rom.merge,
                    "status": rom.status.value,
                    "found_in": str(rom.found_in) if rom.found_in else None,
                    "actual_crc": rom.actual_crc,
                    "actual_size": rom.actual_size,
                })
            data["machines"].append(machine_data)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.log_emitter.log_line.emit(f"💾 Resultados salvos em: {output_path}")

    def _update_summary_from_result(self, result: ScanResult):
        fields = (
            "roms_total",
            "bios_total",
            "devices_total",
            "chds_total",
            "ok_count",
            "fixable_count",
            "missing_count",
            "corrupted_count",
        )

        for field in fields:
            if field in self.summary_labels:
                self.summary_labels[field].setText(
                    str(getattr(result, field, 0))
                )

    def _show_scan_error(self, error: str):
        self.scanning = False
        self.update_ui_state()
        self.status_label.setText(f"Erro: {error}")
        self.log_emitter.log_line.emit(f"❌ ERRO: {error}")
        QMessageBox.critical(
            self,
            "Erro",
            f"Erro durante o escaneamento:\n{error}"
        )

    def stop_scan(self):
        if self.scanning:
            self.scanning = False
            self.status_label.setText("Parando...")
            self.btn_stop.setEnabled(False)
            self.log_emitter.log_line.emit("⏹ Parada solicitada pelo usuário.")

    def _add_machine_to_tree(self, machine_result: MachineScanResult):
        icon = "📦" if machine_result.cloneof else "📁"
        item = QTreeWidgetItem(self.tree)

        item.setText(0, f"{icon} {machine_result.name}")
        item.setText(1, machine_result.description[:50])
        item.setText(2, self._format_size(machine_result.total_size))
        item.setText(3, "-")
        item.setText(4, machine_result.status.label)
        self._apply_status_color(item, machine_result.status)

        for rom in machine_result.roms:
            child = QTreeWidgetItem(item)
            child.setText(0, f"  ├─ {rom.name}")
            child.setText(1, "")
            child.setText(2, self._format_size(rom.size))
            child.setText(3, rom.crc[:8] if rom.crc else "-")
            child.setText(4, rom.status.label)
            self._apply_status_color(child, rom.status)

    def _apply_status_color(self, item, status):
        colors = {
            ScanStatus.OK: "#00AA00",
            ScanStatus.FIXABLE: "#FFAA00",
            ScanStatus.MISSING: "#808080",
            ScanStatus.UNAVAILABLE: "#FF0000",
            ScanStatus.CORRUPTED: "#000000",
            ScanStatus.NOT_SCANNED: "#808080",
        }
        item.setForeground(4, colors.get(status, "#000000"))

    def on_tree_double_click(self, item, column):
        text = item.text(0)
        status = item.text(4)
        QMessageBox.information(
            self,
            "Detalhes",
            f"Item: {text}\nStatus: {status}"
        )

    def _get_rom_paths(self) -> List[Path]:
        paths = []

        # Tenta obter do config
        if hasattr(self.config, "roms_dir") and self.config.roms_dir:
            paths.append(Path(self.config.roms_dir))

        # Tenta obter do mame.ini via DirectoriesTab
        if self.parent and hasattr(self.parent, "directories_tab"):
            ini_service = getattr(self.parent.directories_tab, "ini_service", None)
            if ini_service:
                rom_list = ini_service.get_paths("rompath")
                for rom_path in rom_list:
                    p = Path(rom_path)
                    if p.exists():
                        paths.append(p)

        # Fallback
        if not paths:
            fallback = self.config.PROJECT_ROOT / "roms"
            if fallback.exists():
                paths.append(fallback)

        return paths

    def _get_mame_version(self) -> str:
        try:
            import subprocess
            import re

            if self.config.mame_path and self.config.mame_path.exists():
                result = subprocess.run(
                    [str(self.config.mame_path), "-help"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )

                first_line = result.stdout.strip().split("\n")[0]
                match = re.search(r"v?(\d+\.\d+)", first_line)

                if match:
                    return match.group(1)
        except Exception:
            pass

        return "0.289"

    def _format_size(self, size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        if size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / (1024 * 1024 * 1024):.2f} GB"