"""GUI da integração direta com LaunchBox."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QMenu

from app.config.app_config import AppConfig
from app.core.services.launchbox_integration_service import LaunchBoxInstallation, LaunchBoxIntegrationService, LaunchBoxSystem, LaunchBoxCoreOption


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
        self.filters: dict[str, QLineEdit] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta configuração, filtros, sistemas e exportação."""
        layout = QVBoxLayout(self)
        title = QLabel("Integração LaunchBox")
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(QLabel("O LaunchBox existente é carregado primeiro. O ARCADE MANAGER apenas completa dados ausentes e permite escolher um único padrão por sistema."))
        path_row = QHBoxLayout()
        self.path_label = QLabel("LaunchBox.exe: não configurado")
        self.path_label.setWordWrap(True)
        path_row.addWidget(self.path_label, 1)
        select = QPushButton("Selecionar LaunchBox.exe")
        select.clicked.connect(self.select_launchbox)
        path_row.addWidget(select)
        self.export_button = QPushButton("Exportar / Aplicar alterações")
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
            tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            tree.customContextMenuRequested.connect(lambda pos, t=tree: self._show_context_menu(t, pos))
            tree.setColumnWidth(0, 350)
            tree.setColumnWidth(1, 400)
            tree.setColumnWidth(2, 110)
            tree.setColumnWidth(3, 110)
            self.tabs.addTab(tree, label)
            self.trees[key] = tree
            filter_row = QHBoxLayout()
            filter_row.addWidget(QLabel("Filtro:"))
            edit = QLineEdit()
            edit.setPlaceholderText("Filtrar sistema, core/emulador, estado ou padrão...")
            edit.textChanged.connect(lambda text, k=key: self._filter_tree(k, text))
            filter_row.addWidget(edit)
            layout.addLayout(filter_row)
            self.filters[key] = edit
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
            self.installation = self.service.load_launchbox_installation(path)
        except Exception as exc:
            QMessageBox.critical(self, "LaunchBox", f"Não foi possível carregar a instalação. Nenhum XML foi alterado.\n\n{type(exc).__name__}: {exc}")
            return
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
        self.log.setText(f"LaunchBox carregado sem alterações | Emulators.xml: {'OK' if self.installation.emulators_loaded else 'não encontrado'} | Platforms.xml: {'OK' if self.installation.platforms_loaded else 'não encontrado'} | Emuladores: {len(self.installation.emulators)} | Plataformas: {len(self.installation.platforms)}")

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
        """Preenche Sistema → Core/Emulador e distingue estado."""
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
            parent.setData(0, Qt.ItemDataRole.UserRole, system.system_id)
            for option in sorted(system.options, key=lambda x: (not x.default, not x.existing, -x.score, x.name.casefold())):
                child = QTreeWidgetItem(parent)
                child.setText(1, option.name)
                child.setText(2, "EXISTENTE" if option.existing else "A ADICIONAR")
                child.setForeground(2, Qt.GlobalColor.green if option.existing else Qt.GlobalColor.darkYellow)
                child.setText(3, "★ Padrão" if option.default else "Alternativa")
                child.setForeground(3, Qt.GlobalColor.green if option.default else Qt.GlobalColor.gray)
                child.setData(0, Qt.ItemDataRole.UserRole, system.system_id)
                child.setData(1, Qt.ItemDataRole.UserRole, option.key)
                if option.core_dll:
                    child.setToolTip(1, f"Core: {option.core_dll}\nCaminho: {option.core_path or 'não encontrado'}")
                elif option.executable:
                    child.setToolTip(1, f"Executável: {option.executable}")

    def _filter_tree(self, key: str, text: str) -> None:
        """Filtra linhas mantendo sistemas pais visíveis quando algum filho corresponde."""
        tree = self.trees[key]
        needle = text.casefold().strip()
        for i in range(tree.topLevelItemCount()):
            parent = tree.topLevelItem(i)
            parent_match = not needle or any(needle in parent.text(c).casefold() for c in range(tree.columnCount()))
            child_match = False
            for j in range(parent.childCount()):
                child = parent.child(j)
                match = not needle or any(needle in child.text(c).casefold() for c in range(tree.columnCount()))
                child.setHidden(not match)
                child_match = child_match or match
            parent.setHidden(bool(needle) and not parent_match and not child_match)
            parent.setExpanded(not needle or child_match)

    def _show_context_menu(self, tree: QTreeWidget, pos) -> None:
        """Abre menu contextual para tornar um core/emulador o único padrão."""
        item = tree.itemAt(pos)
        if item is None or item.parent() is None:
            return
        system_id = item.data(0, Qt.ItemDataRole.UserRole)
        option_key = item.data(1, Qt.ItemDataRole.UserRole)
        system = next((s for s in self.systems if s.system_id == system_id), None)
        if system is None:
            return
        option = next((o for o in system.options if o.key == option_key), None)
        if option is None:
            return
        menu = QMenu(self)
        action = menu.addAction("★ Definir como padrão deste sistema")
        action.setEnabled(not option.default)
        action.triggered.connect(lambda: self._set_default(system, option))
        menu.addSeparator()
        info = menu.addAction(f"Sistema: {system.name}")
        info.setEnabled(False)
        menu.exec(tree.viewport().mapToGlobal(pos))

    def _set_default(self, system: LaunchBoxSystem, option: LaunchBoxCoreOption) -> None:
        """Troca o padrão removendo automaticamente o anterior."""
        self.service.set_default_option(system, option)
        self._populate()
        self.status.setText(f"Padrão alterado: {system.name} → {option.name}. Apenas um candidato permanece como padrão.")

    def export(self) -> None:
        """Completa o LaunchBox e aplica somente mudanças de padrão solicitadas."""
        if not self.installation:
            QMessageBox.warning(self, "LaunchBox", "Selecione primeiro o LaunchBox.exe.")
            return
        try:
            target = self.service.export_emulators_xml(self.installation.root, self.systems, overwrite=False)
            self.installation = self.service.load_launchbox_installation(self.installation.executable)
            self._populate()
            QMessageBox.information(self, "LaunchBox", f"Integração concluída sem reconstruir os XMLs.\n\nArquivo: {target}")
            self.status.setText(f"Integração concluída: {target}")
        except Exception as exc:
            QMessageBox.critical(self, "LaunchBox", f"Falha na integração; o XML original não foi substituído.\n\n{type(exc).__name__}: {exc}")


__all__ = ["LaunchBoxIntegrationTab"]
