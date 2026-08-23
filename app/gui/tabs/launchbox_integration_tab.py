"""GUI da integração direta com LaunchBox."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from app.config.app_config import AppConfig
from app.core.services.launchbox_integration_service import LaunchBoxInstallation, LaunchBoxIntegrationService, LaunchBoxSystem


class LaunchBoxIntegrationTab(QWidget):
    """Integra sistemas e emuladores preservando primeiro o estado existente do LaunchBox."""

    GROUPS = (("consoles", "Consoles"), ("portables", "Portáteis"), ("computers", "Computadores"), ("arcade", "Arcade"))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        self.service = LaunchBoxIntegrationService(config=self.config)
        self.systems: list[LaunchBoxSystem] = []
        self.installation: LaunchBoxInstallation | None = None
        self.settings_file = self.service.project_root / "data" / "launchbox" / "settings.json"
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta configuração da instalação, sistemas e exportação."""
        layout = QVBoxLayout(self)
        title = QLabel("Integração LaunchBox")
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(QLabel("O LaunchBox existente é carregado primeiro. O ARCADE MANAGER apenas completa dados ausentes e nunca reconstrói os XMLs."))
        path_row = QHBoxLayout()
        self.path_label = QLabel("LaunchBox.exe: não configurado")
        self.path_label.setWordWrap(True)
        path_row.addWidget(self.path_label, 1)
        select = QPushButton("Selecionar LaunchBox.exe")
        select.clicked.connect(self.select_launchbox)
        path_row.addWidget(select)
        self.export_button = QPushButton("Exportar somente faltantes")
        self.export_button.clicked.connect(self.export)
        self.export_button.setEnabled(False)
        path_row.addWidget(self.export_button)
        layout.addLayout(path_row)
        action_row = QHBoxLayout()
        refresh = QPushButton("Recarregar LaunchBox")
        refresh.clicked.connect(self.refresh)
        action_row.addWidget(refresh)
        reload_rules = QPushButton("Atualizar catálogo")
        reload_rules.clicked.connect(self.refresh)
        action_row.addWidget(reload_rules)
        self.status = QLabel()
        action_row.addWidget(self.status, 1)
        layout.addLayout(action_row)
        self.tabs = QTabWidget()
        self.trees: dict[str, QTreeWidget] = {}
        for key, label in self.GROUPS:
            tree = QTreeWidget()
            tree.setColumnCount(4)
            tree.setHeaderLabels(["Sistema oficial / LaunchBox", "Core / Emulador", "Estado", "Padrão"])
            tree.setAlternatingRowColors(True)
            tree.setRootIsDecorated(True)
            tree.setColumnWidth(0, 350)
            tree.setColumnWidth(1, 400)
            tree.setColumnWidth(2, 110)
            self.tabs.addTab(tree, label)
            self.trees[key] = tree
        layout.addWidget(self.tabs, 1)
        self.log = QLabel()
        self.log.setWordWrap(True)
        self.log.setStyleSheet("color:#888;")
        layout.addWidget(self.log)

    def _load_settings(self) -> Path | None:
        """Carrega o caminho persistido do LaunchBox."""
        try:
            data = json.loads(self.settings_file.read_text(encoding="utf-8"))
            value = data.get("launchbox_executable")
            return Path(value) if value else None
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def _save_settings(self, executable: Path) -> None:
        """Persiste o LaunchBox.exe fora das configurações dos emuladores."""
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text(json.dumps({"launchbox_executable": str(executable)}, indent=2), encoding="utf-8")

    def select_launchbox(self) -> None:
        """Seleciona LaunchBox.exe e imediatamente importa os XMLs existentes."""
        selected, _ = QFileDialog.getOpenFileName(self, "Selecionar LaunchBox.exe", "", "Executável (*.exe)")
        if not selected:
            return
        path = Path(selected).resolve()
        if path.name.casefold() != "launchbox.exe":
            QMessageBox.warning(self, "LaunchBox", "Selecione o arquivo LaunchBox.exe.")
            return
        try:
            installation = self.service.load_launchbox_installation(path)
        except Exception as exc:
            QMessageBox.critical(self, "LaunchBox", f"Não foi possível carregar a instalação. Nenhum XML foi alterado.\n\n{type(exc).__name__}: {exc}")
            return
        self.installation = installation
        self._save_settings(path)
        self._update_path_label(path)
        self._update_launchbox_status()
        self.refresh()

    def _update_path_label(self, path: Path | None) -> None:
        """Atualiza o indicador visual da instalação."""
        self.path_label.setText(f"LaunchBox.exe: {path if path else 'não configurado'}")

    def _update_launchbox_status(self) -> None:
        """Mostra quais arquivos de configuração foram encontrados."""
        if not self.installation:
            return
        self.log.setText(
            f"LaunchBox carregado sem alterações | Emulators.xml: {'OK' if self.installation.emulators_loaded else 'não encontrado'} | "
            f"Platforms.xml: {'OK' if self.installation.platforms_loaded else 'não encontrado'} | "
            f"Emuladores: {len(self.installation.emulators)} | Plataformas: {len(self.installation.platforms)}"
        )

    def refresh(self) -> None:
        """Recarrega LaunchBox e depois completa a visão com o catálogo do projeto."""
        self.service.reload_rules()
        launchbox = self._load_settings()
        self._update_path_label(launchbox)
        self.config.load()
        self.service.config = self.config
        self.installation = None
        if launchbox and launchbox.is_file():
            try:
                self.installation = self.service.load_launchbox_installation(launchbox)
            except Exception as exc:
                self.status.setText(f"LaunchBox: erro ao carregar XML: {type(exc).__name__}: {exc}")
                self._clear_trees()
                self.export_button.setEnabled(False)
                return
        info_dir = self.config.retroarch_native_paths.get("libretro_info_path")
        if not info_dir or not Path(info_dir).is_dir():
            self.systems = []
            self._clear_trees()
            self.status.setText("Configure o diretório de .info do RetroArch.")
            self.export_button.setEnabled(bool(self.installation))
            self._update_launchbox_status()
            return
        try:
            infos = self.service.scan_retroarch(Path(info_dir))
            self.systems = self.service.build_systems(infos, self.installation)
            self._add_standalone_entries()
            self._populate()
            existing = sum(1 for s in self.systems if s.existing)
            missing = len(self.systems) - existing
            self.status.setText(f"{len(infos)} cores .info | {len(self.systems)} sistemas | existentes={existing} | a completar={missing}")
            self.export_button.setEnabled(bool(self.installation))
            self._update_launchbox_status()
        except Exception as exc:
            self.status.setText(f"Erro: {type(exc).__name__}: {exc}")
            self.export_button.setEnabled(False)

    def _add_standalone_entries(self) -> None:
        """Inclui os standalones suportados pelo projeto como alternativas."""
        standalone = [
            {"system_id": "arcade", "name": "MAME Standalone", "emulator": "mame", "score": 100},
            {"system_id": "naomi", "name": "Flycast Standalone", "emulator": "flycast", "score": 95},
            {"system_id": "naomi2", "name": "Flycast Standalone", "emulator": "flycast", "score": 95},
            {"system_id": "atomiswave", "name": "Flycast Standalone", "emulator": "flycast", "score": 95},
            {"system_id": "model3", "name": "Supermodel Standalone", "emulator": "supermodel", "score": 100},
        ]
        self.systems = self.service.add_standalones(self.systems, standalone)

    def _clear_trees(self) -> None:
        """Limpa as quatro visões."""
        for tree in self.trees.values():
            tree.clear()

    def _populate(self) -> None:
        """Preenche Sistema → Core/Emulador e distingue estado existente/faltante."""
        self._clear_trees()
        for system in self.systems:
            tree = self.trees.get(system.group)
            if tree is None:
                continue
            parent = QTreeWidgetItem(tree)
            parent.setText(0, system.name)
            parent.setToolTip(0, system.system_id)
            parent.setExpanded(True)
            parent.setText(2, "EXISTENTE" if system.existing else "NOVO")
            parent.setForeground(2, Qt.GlobalColor.green if system.existing else Qt.GlobalColor.darkYellow)
            for option in sorted(system.options, key=lambda x: (not x.default, not x.existing, -x.score, x.name.casefold())):
                child = QTreeWidgetItem(parent)
                child.setText(1, option.name)
                if option.core_dll:
                    child.setToolTip(1, f"Core: {option.core_dll}\nCaminho: {option.core_path or 'não encontrado'}")
                elif option.executable:
                    child.setToolTip(1, f"Executável: {option.executable}")
                child.setText(2, "EXISTENTE" if option.existing else "A ADICIONAR")
                child.setForeground(2, Qt.GlobalColor.green if option.existing else Qt.GlobalColor.darkYellow)
                child.setText(3, "★ Padrão" if option.default else "Alternativa")
                if option.default:
                    child.setForeground(3, Qt.GlobalColor.green)

    def export(self) -> None:
        """Completa o LaunchBox sem reconstruir configurações existentes."""
        if not self.installation:
            QMessageBox.warning(self, "LaunchBox", "Selecione primeiro o LaunchBox.exe.")
            return
        try:
            target = self.service.export_emulators_xml(self.installation.root, self.systems, overwrite=False)
            self.installation = self.service.load_launchbox_installation(self.installation.executable)
            self._populate()
            QMessageBox.information(self, "LaunchBox", f"Integração concluída. Apenas itens ausentes foram adicionados.\n\nArquivo: {target}")
            self.status.setText(f"Integração concluída: {target}")
        except Exception as exc:
            QMessageBox.critical(self, "LaunchBox", f"Falha na integração; o XML original não foi substituído.\n\n{type(exc).__name__}: {exc}")


__all__ = ["LaunchBoxIntegrationTab"]
