"""GUI da integração direta com LaunchBox."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config.app_config import AppConfig
from app.core.services.launchbox_integration_service import (
    LaunchBoxCoreOption,
    LaunchBoxInstallation,
    LaunchBoxIntegrationService,
    LaunchBoxSystem,
)
from app.core.services.shader_dependency_service import ShaderDependencyService
from app.core.services.system_optimization_service import SystemOptimizationProfile, SystemOptimizationService


class LaunchBoxIntegrationTab(QWidget):
    """Integra sistemas, cores e otimizações preservando o estado do LaunchBox."""

    GROUPS = (
        ("consoles", "Consoles"),
        ("portables", "Portáteis"),
        ("computers", "Computadores"),
        ("arcade", "Arcade"),
    )

    COL_SYSTEM = 0
    COL_EMULATOR = 1
    COL_TYPE = 2
    COL_COMMAND = 3
    COL_STATUS = 4
    COL_DEFAULT = 5
    COL_OPTIMIZATION = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        self.service = LaunchBoxIntegrationService(config=self.config)
        self.optimization_service = SystemOptimizationService(
            project_root=self.service.project_root,
            config=self.config,
        )
        self.shader_dependency_service = ShaderDependencyService(
            config=self.config,
            catalog_path=self.service.project_root / "data" / "launchbox" / "shader_library.json",
        )
        self.systems: list[LaunchBoxSystem] = []
        self.installation: LaunchBoxInstallation | None = None
        self.settings_file = self.service.project_root / "data" / "launchbox" / "settings.json"
        self.optimization_settings_file = self.service.project_root / "data" / "launchbox" / "optimization_settings.json"
        self.optimization_selections: dict[str, str] = {}
        self.filters: dict[str, QLineEdit] = {}
        self.trees: dict[str, QTreeWidget] = {}
        self._updating_tree = False
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta configuração, filtros, tabela, otimização e exportação."""
        layout = QVBoxLayout(self)
        title = QLabel("Integração LaunchBox")
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(QLabel(
            "Todos os sistemas do Platforms.xml são importados. Cada sistema pode ter várias opções, "
            "mas somente uma é marcada como padrão. CommandLine pode ser editado diretamente. "
            "Otimização de Sistema aplica perfis RetroArch prontos por plataforma."
        ))

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
        for key, label in self.GROUPS:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            filter_row = QHBoxLayout()
            filter_row.addWidget(QLabel("Filtro:"))
            edit = QLineEdit()
            edit.setPlaceholderText("Sistema, emulador/core, tipo, command line, estado, padrão ou otimização...")
            edit.textChanged.connect(lambda text, k=key: self._filter_tree(k, text))
            filter_row.addWidget(edit)
            clear = QPushButton("Limpar")
            clear.clicked.connect(edit.clear)
            filter_row.addWidget(clear)
            page_layout.addLayout(filter_row)

            tree = QTreeWidget()
            tree.setColumnCount(7)
            tree.setHeaderLabels([
                "Sistema oficial / LaunchBox",
                "Emulador / Core",
                "Tipo",
                "CommandLine",
                "Estado",
                "Padrão",
                "Otimização de Sistema",
            ])
            tree.setAlternatingRowColors(True)
            tree.setRootIsDecorated(True)
            tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            tree.customContextMenuRequested.connect(lambda pos, t=tree: self._show_context_menu(t, pos))
            tree.itemChanged.connect(self._on_item_changed)
            tree.setColumnWidth(self.COL_SYSTEM, 300)
            tree.setColumnWidth(self.COL_EMULATOR, 340)
            tree.setColumnWidth(self.COL_TYPE, 70)
            tree.setColumnWidth(self.COL_COMMAND, 430)
            tree.setColumnWidth(self.COL_STATUS, 110)
            tree.setColumnWidth(self.COL_DEFAULT, 100)
            tree.setColumnWidth(self.COL_OPTIMIZATION, 250)
            page_layout.addWidget(tree, 1)
            self.tabs.addTab(page, label)
            self.trees[key] = tree
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
        """Persiste o LaunchBox.exe fora dos XMLs nativos."""
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text(
            json.dumps({"launchbox_executable": str(executable)}, indent=2),
            encoding="utf-8",
        )

    def _load_optimization_settings(self) -> None:
        """Carrega as escolhas de otimização por sistema."""
        try:
            data = json.loads(self.optimization_settings_file.read_text(encoding="utf-8"))
            values = data.get("systems", {}) if isinstance(data, dict) else {}
            self.optimization_selections = {
                str(key): str(value) for key, value in values.items() if str(value).strip()
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.optimization_selections = {}

    def _save_optimization_settings(self) -> None:
        """Persiste as escolhas sem tocar nos XMLs do LaunchBox."""
        self.optimization_settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.optimization_settings_file.write_text(
            json.dumps({"systems": self.optimization_selections}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def select_launchbox(self) -> None:
        """Seleciona LaunchBox.exe e importa imediatamente os XMLs existentes."""
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
        self.refresh()

    def _update_path_label(self, path: Path | None) -> None:
        """Atualiza o caminho visual da instalação."""
        self.path_label.setText(f"LaunchBox.exe: {path if path else 'não configurado'}")

    def _update_launchbox_status(self) -> None:
        """Mostra o estado dos XMLs importados."""
        if not self.installation:
            self.log.setText("Nenhuma instalação do LaunchBox carregada.")
            return
        self.log.setText(
            f"LaunchBox carregado sem alterações | Emulators.xml: {'OK' if self.installation.emulators_loaded else 'não encontrado'} | "
            f"Platforms.xml: {'OK' if self.installation.platforms_loaded else 'não encontrado'} | Emuladores: {len(self.installation.emulators)} | "
            f"Plataformas: {len(self.installation.platforms)} | Associações: {len(self.installation.emulator_platforms)}"
        )

    def refresh(self) -> None:
        """Recarrega LaunchBox, catálogo RetroArch e perfis de otimização."""
        self.service.reload_rules()
        self.optimization_service.config = self.config
        self.optimization_service.reload()
        self.shader_dependency_service = ShaderDependencyService(
            config=self.config,
            catalog_path=self.service.project_root / "data" / "launchbox" / "shader_library.json",
        )
        self._load_optimization_settings()
        launchbox = self._load_settings()
        self._update_path_label(launchbox)
        self.config.load()
        self.service.config = self.config
        self.optimization_service.config = self.config
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
            self.systems = self.service.build_systems([], self.installation)
            self._add_standalone_entries()
            self._populate()
            self.status.setText("Configure o diretório de .info do RetroArch para completar os cores.")
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
            options = sum(len(s.options) for s in self.systems)
            self.status.setText(f"{len(infos)} cores .info | {len(self.systems)} sistemas | {options} opções | existentes={existing} | novos={missing}")
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

    def _optimization_profiles(self, system: LaunchBoxSystem) -> list[SystemOptimizationProfile]:
        """Retorna perfis prontos compatíveis com o sistema exibido."""
        return self.optimization_service.profiles_for_system(system.name, system.system_id)

    def _create_optimization_selector(self, system: LaunchBoxSystem) -> QComboBox:
        """Cria o seletor de otimização inline do sistema."""
        combo = QComboBox()
        combo.setMinimumWidth(235)
        combo.setToolTip("Selecione um perfil pronto para aplicar configurações de core, vídeo, shader e remap.")
        combo.addItem("Sem otimização", "")
        profiles = self._optimization_profiles(system)
        for profile in profiles:
            combo.addItem(profile.name, profile.profile_id)
            combo.setItemData(combo.count() - 1, profile.description, Qt.ItemDataRole.ToolTipRole)
        selected = self.optimization_selections.get(system.system_id, "")
        index = combo.findData(selected)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.currentIndexChanged.connect(lambda _index, s=system, c=combo: self._optimization_changed(s, c))
        return combo

    def _populate(self) -> None:
        """Preenche Sistema → Emulador/Core → Tipo → CommandLine + otimização."""
        self._updating_tree = True
        try:
            self._clear_trees()
            for system in self.systems:
                tree = self.trees.get(system.group)
                if tree is None:
                    continue
                parent = QTreeWidgetItem(tree)
                parent.setText(self.COL_SYSTEM, system.name)
                parent.setToolTip(self.COL_SYSTEM, system.system_id)
                parent.setExpanded(True)
                parent.setText(self.COL_STATUS, "EXISTENTE" if system.existing else "NOVO")
                parent.setForeground(self.COL_STATUS, Qt.GlobalColor.green if system.existing else Qt.GlobalColor.darkYellow)
                parent.setData(self.COL_SYSTEM, Qt.ItemDataRole.UserRole, system.system_id)
                selector = self._create_optimization_selector(system)
                tree.setItemWidget(parent, self.COL_OPTIMIZATION, selector)
                for option in sorted(system.options, key=lambda x: (not x.default, not x.existing, -x.score, x.name.casefold())):
                    child = QTreeWidgetItem(parent)
                    child.setText(self.COL_EMULATOR, option.name)
                    child.setText(self.COL_TYPE, option.kind)
                    child.setText(self.COL_COMMAND, option.command_line)
                    child.setText(self.COL_STATUS, "EXISTENTE" if option.existing else "A ADICIONAR")
                    child.setForeground(self.COL_STATUS, Qt.GlobalColor.green if option.existing else Qt.GlobalColor.darkYellow)
                    child.setText(self.COL_DEFAULT, "★ Padrão" if option.default else "Alternativa")
                    child.setForeground(self.COL_DEFAULT, Qt.GlobalColor.green if option.default else Qt.GlobalColor.gray)
                    child.setFlags(child.flags() | Qt.ItemFlag.ItemIsEditable)
                    child.setData(self.COL_SYSTEM, Qt.ItemDataRole.UserRole, system.system_id)
                    child.setData(self.COL_EMULATOR, Qt.ItemDataRole.UserRole, option.key)
                    if option.core_dll:
                        child.setToolTip(self.COL_EMULATOR, f"Core: {option.core_dll}\nCaminho: {option.core_path or 'não encontrado'}")
                    elif option.executable:
                        child.setToolTip(self.COL_EMULATOR, f"Executável: {option.executable}")
        finally:
            self._updating_tree = False

    def _optimization_changed(self, system: LaunchBoxSystem, combo: QComboBox) -> None:
        """Aplica um perfil, resolvendo dependências de shaders antes da escrita."""
        if self._updating_tree:
            return
        profile_id = str(combo.currentData() or "")
        if not profile_id:
            self.optimization_selections.pop(system.system_id, None)
            self._save_optimization_settings()
            self.status.setText(f"Otimização removida da seleção: {system.name}")
            return
        profile = self.optimization_service.get(profile_id)
        if profile is None:
            return

        dependency = None
        if profile.shader:
            shader_profile = self.shader_dependency_service.manager._catalog_entry(profile.shader.shader_id)
            from app.core.services.shader_manager_service import ShaderProfile
            catalog_profile = ShaderProfile.from_dict(shader_profile)
            dependency = self.shader_dependency_service.inspect(profile.shader, catalog_profile)

        if dependency and dependency.requires_download:
            details = (
                f"O perfil '{profile.name}' necessita do shader de terceiros '{profile.shader.shader_id}'.\n\n"
                f"Origem: {dependency.source_name}\n\n"
                "O shader será baixado diretamente do repositório upstream. "
                "Nenhum arquivo do shader será armazenado no projeto.\n\n"
                "Deseja baixar e instalar essa dependência agora?"
            )
            answer = QMessageBox.question(
                self,
                "Dependência de Shader",
                details,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._updating_tree = True
                combo.setCurrentIndex(0)
                self._updating_tree = False
                return
            try:
                self.status.setText(f"Baixando shader: {dependency.source_name}...")
                self.shader_dependency_service.ensure_installed(dependency)
            except Exception as exc:
                self._updating_tree = True
                combo.setCurrentIndex(0)
                self._updating_tree = False
                QMessageBox.critical(self, "Dependência de Shader", f"Não foi possível instalar o shader.\n\n{type(exc).__name__}: {exc}")
                return

        answer = QMessageBox.question(
            self,
            "Otimização de Sistema",
            f"Aplicar '{profile.name}' ao sistema '{system.name}'?\n\n"
            "Os arquivos gerenciados pelo Arcade Manager serão sobrescritos. "
            "Nenhum backup .bak será criado e o retroarch.cfg global não será alterado.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self._updating_tree = True
            combo.setCurrentIndex(0)
            self._updating_tree = False
            return
        try:
            result = self.optimization_service.apply(system.name, system.system_id, profile_id)
            self.optimization_selections[system.system_id] = profile_id
            self._save_optimization_settings()
            written = len(result["written"])
            warning_text = ""
            if result["warnings"]:
                warning_text = "\n\nAvisos:\n" + "\n".join(result["warnings"])
            self.status.setText(f"Otimização aplicada: {system.name} → {profile.name} | arquivos={written}{warning_text}")
        except Exception as exc:
            self._updating_tree = True
            combo.setCurrentIndex(0)
            self._updating_tree = False
            QMessageBox.critical(self, "Otimização de Sistema", f"Não foi possível aplicar o perfil. Nenhum arquivo foi escrito após a falha de preparação.\n\n{type(exc).__name__}: {exc}")

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """Persiste alterações de CommandLine feitas diretamente na tabela."""
        if self._updating_tree or column != self.COL_COMMAND or item.parent() is None:
            return
        system_id = item.data(self.COL_SYSTEM, Qt.ItemDataRole.UserRole)
        option_key = item.data(self.COL_EMULATOR, Qt.ItemDataRole.UserRole)
        system = next((s for s in self.systems if s.system_id == system_id), None)
        if system is None:
            return
        option = next((o for o in system.options if o.key == option_key), None)
        if option is None:
            return
        option.command_line = item.text(self.COL_COMMAND)
        self.status.setText(f"CommandLine alterado: {system.name} → {option.name}")

    def _filter_tree(self, key: str, text: str) -> None:
        """Filtra todas as colunas mantendo o sistema pai quando necessário."""
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
            optimization_widget = tree.itemWidget(parent, self.COL_OPTIMIZATION)
            if optimization_widget is not None and needle:
                parent_match = parent_match or needle in optimization_widget.currentText().casefold()
            parent.setHidden(bool(needle) and not parent_match and not child_match)
            parent.setExpanded(not needle or child_match)

    def _show_context_menu(self, tree: QTreeWidget, pos) -> None:
        """Abre o menu para tornar uma opção o único padrão do sistema."""
        item = tree.itemAt(pos)
        if item is None or item.parent() is None:
            return
        system_id = item.data(self.COL_SYSTEM, Qt.ItemDataRole.UserRole)
        option_key = item.data(self.COL_EMULATOR, Qt.ItemDataRole.UserRole)
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
        """Troca o padrão e remove automaticamente o anterior."""
        self.service.set_default_option(system, option)
        self._populate()
        self.status.setText(f"Padrão alterado: {system.name} → {option.name}. Somente um candidato permanece como padrão.")

    def export(self) -> None:
        """Aplica as mudanças mantendo o XML existente como base."""
        if not self.installation:
            QMessageBox.warning(self, "LaunchBox", "Selecione primeiro o LaunchBox.exe.")
            return
        try:
            target = self.service.export_emulators_xml(self.installation.root, self.systems, overwrite=False)
            self.installation = self.service.load_launchbox_installation(self.installation.executable)
            self._populate()
            QMessageBox.information(self, "LaunchBox", "Integração concluída usando o XML existente como base.\n\n" f"Arquivo: {target}\n\n")
        except Exception as exc:
            QMessageBox.critical(self, "LaunchBox", f"Falha ao exportar. Nenhum XML adicional foi alterado.\n\n{type(exc).__name__}: {exc}")
