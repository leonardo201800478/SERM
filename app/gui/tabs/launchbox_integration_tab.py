"""GUI da integração direta com LaunchBox."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config.app_config import AppConfig
from app.core.services.launchbox_integration_service import LaunchBoxIntegrationService, LaunchBoxSystem


class LaunchBoxIntegrationTab(QWidget):
    """Integra sistemas, cores e emuladores com a base XML do LaunchBox."""

    GROUPS = (("consoles", "Consoles"), ("portables", "Portáteis"), ("computers", "Computadores"), ("arcade", "Arcade"))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        self.service = LaunchBoxIntegrationService()
        self.systems: list[LaunchBoxSystem] = []
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
        layout.addWidget(QLabel("Mapeia os .info do RetroArch, emuladores standalone e favoritos por sistema; a exportação grava em Data/Emulators.xml."))

        path_row = QHBoxLayout()
        self.path_label = QLabel("LaunchBox.exe: não configurado")
        self.path_label.setWordWrap(True)
        path_row.addWidget(self.path_label, 1)
        select = QPushButton("Selecionar LaunchBox.exe")
        select.clicked.connect(self.select_launchbox)
        path_row.addWidget(select)
        self.export_button = QPushButton("Exportar para LaunchBox")
        self.export_button.clicked.connect(self.export)
        path_row.addWidget(self.export_button)
        layout.addLayout(path_row)

        action_row = QHBoxLayout()
        refresh = QPushButton("Atualizar sistemas e cores")
        refresh.clicked.connect(self.refresh)
        action_row.addWidget(refresh)
        reload_rules = QPushButton("Recarregar regras externas")
        reload_rules.clicked.connect(self.refresh)
        action_row.addWidget(reload_rules)
        self.status = QLabel()
        action_row.addWidget(self.status, 1)
        layout.addLayout(action_row)

        self.tabs = QTabWidget()
        self.trees: dict[str, QTreeWidget] = {}
        for key, label in self.GROUPS:
            tree = QTreeWidget()
            tree.setColumnCount(3)
            tree.setHeaderLabels(["Sistema oficial", "Core / Emulador", "Padrão"])
            tree.setAlternatingRowColors(True)
            tree.setRootIsDecorated(True)
            tree.setColumnWidth(0, 330)
            tree.setColumnWidth(1, 420)
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
        except (OSError, ValueError, TypeError):
            return None

    def _save_settings(self, executable: Path) -> None:
        """Persiste o LaunchBox.exe fora do código-fonte."""
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text(json.dumps({"launchbox_executable": str(executable)}, indent=2), encoding="utf-8")

    def select_launchbox(self) -> None:
        """Seleciona e valida LaunchBox.exe."""
        selected, _ = QFileDialog.getOpenFileName(self, "Selecionar LaunchBox.exe", "", "Executável (*.exe)")
        if not selected:
            return
        path = Path(selected).resolve()
        if path.name.casefold() != "launchbox.exe":
            QMessageBox.warning(self, "LaunchBox", "Selecione o arquivo LaunchBox.exe.")
            return
        self._save_settings(path)
        self._update_path_label(path)

    def _update_path_label(self, path: Path | None) -> None:
        """Atualiza o indicador visual da instalação."""
        self.path_label.setText(f"LaunchBox.exe: {path if path else 'não configurado'}")

    def refresh(self) -> None:
        """Reconstrói o mapeamento usando os .info locais do RetroArch."""
        self.service.reload_rules()
        launchbox = self._load_settings()
        self._update_path_label(launchbox)
        self.config.load()
        info_dir = self.config.retroarch_native_paths.get("libretro_info_path")
        if not info_dir or not Path(info_dir).is_dir():
            self.systems = []
            self._clear_trees()
            self.status.setText("Configure o diretório de .info do RetroArch.")
            return
        try:
            infos = self.service.scan_retroarch(Path(info_dir))
            self.systems = self.service.build_systems(infos)
            self._add_standalone_entries()
            self._populate()
            self.status.setText(f"{len(infos)} cores .info | {len(self.systems)} sistemas | 1 padrão por sistema")
            self.log.setText("Fonte: arquivos .info locais do RetroArch. Regras de classificação e command-lines são editáveis em data/launchbox/.")
        except Exception as exc:
            self.status.setText(f"Erro: {type(exc).__name__}: {exc}")

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
        """Preenche Sistema → Core/Emulador com o favorito destacado."""
        self._clear_trees()
        for system in self.systems:
            tree = self.trees.get(system.group)
            if tree is None:
                continue
            parent = QTreeWidgetItem(tree)
            parent.setText(0, system.name)
            parent.setToolTip(0, system.system_id)
            parent.setExpanded(True)
            for option in sorted(system.options, key=lambda x: (not x.default, -x.score, x.name.casefold())):
                child = QTreeWidgetItem(parent)
                child.setText(1, option.name)
                if option.core_dll:
                    child.setToolTip(1, option.core_dll)
                child.setText(2, "★ Padrão" if option.default else "Alternativa")
                child.setForeground(2, Qt.GlobalColor.green if option.default else Qt.GlobalColor.gray)

    def export(self) -> None:
        """Exporta o catálogo para Data/Emulators.xml do LaunchBox configurado."""
        launchbox = self._load_settings()
        if launchbox is None or not launchbox.is_file():
            QMessageBox.warning(self, "LaunchBox", "Configure primeiro o LaunchBox.exe.")
            return
        launchbox_dir = launchbox.parent
        try:
            target = self.service.export_emulators_xml(launchbox_dir, self.systems, overwrite=False)
            QMessageBox.information(self, "LaunchBox", f"Exportação concluída:\n{target}")
            self.status.setText(f"Exportado: {target}")
        except Exception as exc:
            QMessageBox.critical(self, "LaunchBox", f"Falha na exportação:\n{type(exc).__name__}: {exc}")


__all__ = ["LaunchBoxIntegrationTab"]
