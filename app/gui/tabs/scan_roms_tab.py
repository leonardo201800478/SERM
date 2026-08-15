import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QProgressBar, QTreeWidget, QTreeWidgetItem,
    QGroupBox, QGridLayout, QMessageBox
)
from PySide6.QtCore import Qt, QTimer

from app.core.models.scan_result import ScanResult, MachineScanResult, ScanStatus
from app.core.services.listxml_export_service import ListxmlExportService
from app.core.services.rom_scan_service import RomScanService
from app.config.app_config import AppConfig


class ScanRomsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.config = AppConfig()
        self.scan_result: Optional[ScanResult] = None
        self.scanning = False
        self.filtered_xml_path: Optional[Path] = None

        self.setup_ui()
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

    def update_ui_state(self):
        has_xml = self.filtered_xml_path is not None
        self.btn_scan.setEnabled(has_xml and not self.scanning)
        self.btn_stop.setEnabled(self.scanning)
        self.btn_generate.setEnabled(not self.scanning)

    def generate_filtered_xml(self):
        self.status_label.setText("Gerando XML filtrado...")
        self.btn_generate.setEnabled(False)
        try:
            service = ListxmlExportService(self.config.db_path, self.config.mame_path)
            filter_criteria = {
                'working_arcade': True,  # TODO: obter dos filtros da GUI
                'machine_category': 'Arcade',
                'no_clones': True,
            }
            machine_ids = service.get_machine_ids_from_db(filter_criteria)
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
            self.status_label.setText(f"XML gerado: {output_path.name}")
            QMessageBox.information(self, "Sucesso", f"XML filtrado gerado em:\n{output_path}")
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
        self.progress_bar.setValue(0)
        self.status_label.setText("Escaneando...")

        self.scan_thread = threading.Thread(target=self._do_scan)
        self.scan_thread.daemon = True
        self.scan_thread.start()

    def _do_scan(self):
        try:
            machines = self._load_machines_from_xml(self.filtered_xml_path)
            rom_paths = self._get_rom_paths()
            scanner = RomScanner(rom_paths)

            total = len(machines)
            for idx, machine in enumerate(machines):
                if not self.scanning:
                    break
                result = scanner._scan_single_machine(machine)
                QTimer.singleShot(0, lambda r=result: self._add_machine_to_tree(r))
                progress = int((idx + 1) / total * 100)
                QTimer.singleShot(0, lambda p=progress: self.progress_bar.setValue(p))
                QTimer.singleShot(0, lambda i=idx+1, t=total: self.status_label.setText(f"Escaneando {i}/{t}..."))

            QTimer.singleShot(0, self._finish_scan)
        except Exception as e:
            QTimer.singleShot(0, lambda: self._show_scan_error(str(e)))

    def _finish_scan(self):
        self.scanning = False
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
        paths = []
        # Tenta obter o diretório de ROMs da configuração ou do mame.ini
        if hasattr(self.config, 'roms_dir') and self.config.roms_dir:
            paths.append(Path(self.config.roms_dir))
        else:
            # Fallback: diretório "roms" na raiz
            roms_dir = Path("roms")
            if roms_dir.exists():
                paths.append(roms_dir)
        return paths

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