import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QProgressBar, QTreeWidget, QTreeWidgetItem,
    QGroupBox, QGridLayout, QMessageBox, QFileDialog, QLineEdit, QComboBox
)
from PySide6.QtCore import Qt, QTimer
import threading

from app.mame.rom_scanner import RomScanner
from app.core.services.reconstruction_service import ReconstructionOptions, ReconstructionService

from app.core.models.scan_result import ScanResult, MachineScanResult, ScanStatus
from app.core.services.listxml_export_service import ListxmlExportService
from app.core.services.rom_scan_service import RomScanService
from app.config.app_config import AppConfig
from app.core.services.filter_service import FilterService
from app.core.models.filter_profile import FilterCriteria
from app.database.database import Database
import logging

logger = logging.getLogger(__name__)


class ScanRomsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.config = AppConfig()
        self.scan_result: Optional[ScanResult] = None
        self.scanning = False
        self.filtered_xml_path: Optional[Path] = None

        self.setup_ui()
        self._load_filter_profiles()
        self.update_ui_state()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Topo: botões e status
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
        layout.addLayout(top_layout)

        # Arquivo XML
        xml_layout = QHBoxLayout()
        xml_layout.addWidget(QLabel("Arquivo:"))
        self.xml_label = QLabel("Nenhum arquivo gerado")
        xml_layout.addWidget(self.xml_label)
        layout.addLayout(xml_layout)

        # Fontes e destino: não dependem de mame.ini.
        paths_group = QGroupBox("ORIGENS E DESTINO")
        paths_layout = QGridLayout(paths_group)
        self.source_edits = []
        for row in range(3):
            edit = QLineEdit(str(self.config.source_dirs[row]) if row < len(self.config.source_dirs) else "")
            button = QPushButton("Escolher")
            button.clicked.connect(lambda _=False, e=edit: self._choose_directory(e))
            paths_layout.addWidget(QLabel(f"Origem {row + 1}:"), row, 0)
            paths_layout.addWidget(edit, row, 1)
            paths_layout.addWidget(button, row, 2)
            self.source_edits.append(edit)
        self.destination_edit = QLineEdit(str(self.config.destination_dir) if self.config.destination_dir else "")
        destination_button = QPushButton("Escolher")
        destination_button.clicked.connect(lambda: self._choose_directory(self.destination_edit))
        self.layout_combo = QComboBox()
        self.layout_combo.addItem("Uma pasta", "single")
        self.layout_combo.addItem("Roms / CHD / Devices / Bios", "split")
        self.layout_combo.setCurrentIndex(1 if self.config.output_layout == "split" else 0)
        paths_layout.addWidget(QLabel("Destino:"), 3, 0)
        paths_layout.addWidget(self.destination_edit, 3, 1)
        paths_layout.addWidget(destination_button, 3, 2)
        paths_layout.addWidget(QLabel("Organização:"), 4, 0)
        paths_layout.addWidget(self.layout_combo, 4, 1, 1, 2)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Split — pai separado dos clones", "split")
        self.mode_combo.addItem("Non-merged — cada jogo completo", "non-merged")
        self.mode_combo.addItem("Merged — pai contém os clones", "merged")
        paths_layout.addWidget(QLabel("Modo MAME:"), 5, 0)
        paths_layout.addWidget(self.mode_combo, 5, 1, 1, 2)
        self.btn_reconstruct = QPushButton("Reconstruir válidos")
        self.btn_reconstruct.clicked.connect(self.reconstruct_validated)
        paths_layout.addWidget(self.btn_reconstruct, 6, 1, 1, 2)
        layout.addWidget(paths_group)
        xml_layout.addWidget(self.xml_label)
        layout.addLayout(xml_layout)
        # Perfil de filtro usado para selecionar as máquinas do XML/scan.
        profile_group = QGroupBox("PERFIL DE FILTRO PARA O SET")
        profile_layout = QHBoxLayout(profile_group)
        profile_layout.addWidget(QLabel("Perfil:"))
        self.profile_combo = QComboBox()
        self.profile_combo.setToolTip(
            "Perfil de filtro (criado/salvo na aba Filtragem) usado para "
            "selecionar quais máquinas entram no XML filtrado e no scan.\n"
            "'Todas as máquinas' gera o set completo, sem filtro."
        )
        profile_layout.addWidget(self.profile_combo, stretch=1)
        btn_refresh_profiles = QPushButton("Atualizar perfis")
        btn_refresh_profiles.clicked.connect(self._load_filter_profiles)
        profile_layout.addWidget(btn_refresh_profiles)
        layout.addWidget(profile_group)

        # Resumo
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
            summary_layout.addWidget(QLabel(f"{label}:"), row, col*2)
            lbl = QLabel("0")
            lbl.setStyleSheet("font-weight: bold;")
            self.summary_labels[key] = lbl
            summary_layout.addWidget(lbl, row, col*2+1)
        layout.addWidget(summary_group)

        # Barra de progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Pronto")
        layout.addWidget(self.status_label)

        # Árvore
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["ROM", "Jogo", "Tamanho", "CRC", "Status"])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 200)
        self.tree.setColumnWidth(2, 100)
        self.tree.setColumnWidth(3, 120)
        self.tree.setColumnWidth(4, 100)
        self.tree.itemDoubleClicked.connect(self.on_tree_double_click)
        layout.addWidget(self.tree)

    def _choose_directory(self, edit: QLineEdit):
        selected = QFileDialog.getExistingDirectory(self, "Escolher diretório")
        if selected:
            edit.setText(selected)
            self._save_paths()

    def _save_paths(self):
        self.config.source_dirs = [Path(e.text()) for e in self.source_edits if e.text().strip()][:3]
        self.config.destination_dir = Path(self.destination_edit.text()) if self.destination_edit.text().strip() else None
        self.config.output_layout = self.layout_combo.currentData()
        self.config.save()

    def _get_db_connection(self):
        """Retorna (conn, owns_connection)."""
        main_db = getattr(self.parent, "db", None)
        if main_db is not None and getattr(main_db, "conn", None) is not None:
            return main_db.conn, False

        db = Database(self.config.db_path)
        db.connect()
        return db.conn, True

    def _load_filter_profiles(self):
        """Carrega no combo os perfis de filtro salvos na aba Filtragem."""
        self.profile_combo.clear()
        self.profile_combo.addItem("Todas as máquinas (sem filtro)", None)

        conn, owns = self._get_db_connection()
        try:
            filter_service = FilterService(conn)
            for profile in filter_service.get_profiles():
                self.profile_combo.addItem(profile.name, profile.id)

            default = filter_service.get_default_profile()
            if default:
                idx = self.profile_combo.findData(default.id)
                if idx >= 0:
                    self.profile_combo.setCurrentIndex(idx)
        except Exception as e:
            logger.warning(f"Não foi possível carregar perfis de filtro: {e}")
        finally:
            if owns:
                conn.close()

    def _get_selected_criteria(self) -> FilterCriteria:
        """Retorna os critérios do perfil selecionado no combo local."""
        profile_id = self.profile_combo.currentData()
        if not profile_id:
            return FilterCriteria()

        conn, owns = self._get_db_connection()
        try:
            filter_service = FilterService(conn)
            profile = next(
                (p for p in filter_service.get_profiles() if p.id == profile_id),
                None,
            )
            return profile.criteria if profile else FilterCriteria()
        finally:
            if owns:
                conn.close()

    def update_ui_state(self):
        has_xml = self.filtered_xml_path is not None
        self.btn_scan.setEnabled(has_xml and not self.scanning)
        self.btn_stop.setEnabled(self.scanning)
        self.btn_generate.setEnabled(not self.scanning)
        self.btn_reconstruct.setEnabled(bool(self.scan_result) and not self.scanning)

    def generate_filtered_xml(self):
        self.status_label.setText("Gerando XML filtrado...")
        self.btn_generate.setEnabled(False)
        try:
            service = ListxmlExportService(self.config.db_path, self.config.mame_path)
            criteria = self._get_selected_criteria()
            machine_ids = service.get_machine_ids_from_db(criteria)
            if not machine_ids:
                QMessageBox.warning(self, "Aviso", "Nenhuma máquina encontrada com os filtros atuais.")
                return

            version = self._get_mame_version()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mame_{version}_filtered_{timestamp}.xml"
            output_path = Path("data/scans") / filename

            service.generate_filtered_xml(machine_ids, output_path)
            self.filtered_xml_path = output_path
            self.xml_label.setText(str(output_path))
            self.xml_label.setStyleSheet("color: green;")
            self.status_label.setText(
                f"XML gerado: {output_path.name} ({len(machine_ids)} máquinas)"
            )
            QMessageBox.information(
                self,
                "Sucesso",
                f"XML filtrado gerado em:\n{output_path}\n\n"
                f"{len(machine_ids)} máquina(s) selecionada(s) "
                f"(perfil: {self.profile_combo.currentText()}).",
            )
        except Exception as e:
            self.status_label.setText(f"Erro: {e}")
            QMessageBox.critical(self, "Erro", f"Erro ao gerar XML: {e}")
        finally:
            self.btn_generate.setEnabled(True)
            self.update_ui_state()

    def start_scan(self):
        if not self.filtered_xml_path or not self.filtered_xml_path.exists():
            QMessageBox.critical(self, "Erro", "Nenhum XML filtrado disponível.")
            return

        if self.scanning:
            return

        self.scanning = True
        self.update_ui_state()
        self.tree.clear()
        self.scan_result = ScanResult(version="unknown")
        self.progress_bar.setValue(0)
        self.status_label.setText("Escaneando...")

        self.scan_thread = threading.Thread(target=self._do_scan)
        self.scan_thread.daemon = True
        self.scan_thread.start()

    def _do_scan(self):
        try:
            machines = self._load_machines_from_xml(self.filtered_xml_path)
            self._save_paths()
            rom_paths = self._get_rom_paths()
            scanner = RomScanner(rom_paths)

            total = len(machines)
            for idx, machine in enumerate(machines):
                if not self.scanning:
                    break
                result = scanner._scan_single_machine(machine)
                self.scan_result = self.scan_result or ScanResult(version="unknown")
                self.scan_result.machines.append(result)
                QTimer.singleShot(0, lambda r=result: self._add_machine_to_tree(r))
                progress = int((idx + 1) / total * 100)
                QTimer.singleShot(0, lambda p=progress: self.progress_bar.setValue(p))
                QTimer.singleShot(0, lambda i=idx+1, t=total: self.status_label.setText(f"Escaneando {i}/{t}..."))

            QTimer.singleShot(0, self._finish_scan)
        except Exception as e:
            QTimer.singleShot(0, lambda: self._show_scan_error(str(e)))

    def _finish_scan(self):
        self.scanning = False
        if self.scan_result:
            self.scan_result.total_machines = len(self.scan_result.machines)
            self.scan_result.update_summary()
        self.update_ui_state()
        self.progress_bar.setValue(100)
        self.status_label.setText("Escaneamento concluído")

    def _show_scan_error(self, error: str):
        self.scanning = False
        self.update_ui_state()
        self.status_label.setText(f"Erro: {error}")
        QMessageBox.critical(self, "Erro", f"Erro durante o escaneamento:\n{error}")

    def stop_scan(self):
        if self.scanning:
            self.scanning = False
            self.status_label.setText("Parando...")
            self.btn_stop.setEnabled(False)

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
        color = colors.get(status, "#000000")
        item.setForeground(4, color)

    def on_tree_double_click(self, item, column):
        text = item.text(0)
        status = item.text(4)
        QMessageBox.information(self, "Detalhes", f"Item: {text}\nStatus: {status}")

    def _load_machines_from_xml(self, xml_path: Path) -> List[dict]:
        import xml.etree.ElementTree as ET
        machines = []
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for machine_elem in root.findall("machine"):
            machine = {
                'name': machine_elem.get('name', ''),
                'description': '',
                'cloneof': machine_elem.get('cloneof', ''),
                'roms': [],
                'disks': []
            }
            desc = machine_elem.find("description")
            if desc is not None:
                machine['description'] = desc.text or ''
            for rom_elem in machine_elem.findall("rom"):
                machine['roms'].append({
                    'name': rom_elem.get('name', ''),
                    'size': int(rom_elem.get('size', 0)),
                    'crc': rom_elem.get('crc', ''),
                    'sha1': rom_elem.get('sha1', ''),
                    'merge': rom_elem.get('merge', ''),
                })
            for disk_elem in machine_elem.findall("disk"):
                machine['disks'].append({
                    'name': disk_elem.get('name', ''),
                    'sha1': disk_elem.get('sha1', ''),
                })
            machines.append(machine)
        return machines

    def _get_rom_paths(self) -> List[Path]:
        return [Path(e.text()) for e in self.source_edits if e.text().strip() and Path(e.text()).is_dir()][:3]

    def reconstruct_validated(self):
        if not self.scan_result:
            return
        self._save_paths()
        if not self.config.destination_dir:
            QMessageBox.warning(self, "Destino ausente", "Escolha o diretório de destino antes de reconstruir.")
            return
        try:
            service = ReconstructionService(ReconstructionOptions(
                destination=self.config.destination_dir,
                layout=self.config.output_layout,
                mode=self.mode_combo.currentData(),
            ))
            manifest = service.reconstruct(self.scan_result)
            QMessageBox.information(self, "Reconstrução", f"Concluída. Manifesto salvo em:\n{manifest}")
        except Exception as exc:
            QMessageBox.critical(self, "Reconstrução", str(exc))

    def _get_mame_version(self) -> str:
        try:
            import subprocess
            if self.config.mame_path and self.config.mame_path.exists():
                result = subprocess.run([str(self.config.mame_path), "-help"], capture_output=True, text=True, timeout=5)
                first_line = result.stdout.strip().split('\n')[0]
                import re
                match = re.search(r'v?(\d+\.\d+)', first_line)
                if match:
                    return match.group(1)
        except:
            pass
        return "0.289"

    def _format_size(self, size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"