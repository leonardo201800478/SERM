"""Catálogo RetroArch: cores, sistemas e BIOS/firmware."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config.app_config import AppConfig
from app.core.services.retroarch_bios_service import RetroArchBiosService
from app.core.services.retroarch_download_service import RetroArchDownloadService


class RetroArchCatalogTab(QWidget):
    """Catálogo hierárquico de core → sistema → BIOS."""

    COLORS = {
        "ok": QColor(90, 210, 110),
        "update": QColor(225, 190, 70),
        "corrupt": QColor(225, 85, 85),
        "missing": QColor(150, 150, 150),
        "text": QColor(235, 235, 235),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        self.bios_service = RetroArchBiosService()
        self.core_infos = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta catálogo, scanner e ações de BIOS."""
        layout = QVBoxLayout(self)
        title = QLabel("Catálogo RetroArch")
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        description = QLabel(
            "Catálogo de cores libretro com sistemas associados e verificação de BIOS/firmware no System Directory."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color:#888;")
        layout.addWidget(description)

        actions = QGroupBox("Ações")
        row = QHBoxLayout(actions)
        self.refresh_button = QPushButton("Atualizar catálogo")
        self.refresh_button.clicked.connect(self.refresh)
        row.addWidget(self.refresh_button)
        self.scan_bios_button = QPushButton("Escanear BIOS dos cores")
        self.scan_bios_button.clicked.connect(self.scan_bios)
        row.addWidget(self.scan_bios_button)
        self.rebuild_button = QPushButton("Reconstruir BIOS")
        self.rebuild_button.clicked.connect(self.rebuild_bios)
        row.addWidget(self.rebuild_button)
        self.rebuild_from_button = QPushButton("Reconstruir a partir de uma pasta")
        self.rebuild_from_button.clicked.connect(self.rebuild_from_folder)
        row.addWidget(self.rebuild_from_button)
        row.addStretch()
        layout.addWidget(actions)

        self.count_label = QLabel()
        layout.addWidget(self.count_label)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Core", "Sistema", "BIOS / Firmware"])
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(False)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.tree, 1)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color:#888;")
        layout.addWidget(self.status_label)

    def refresh(self) -> None:
        """Atualiza cores e estrutura core → sistema sem executar scan de BIOS automaticamente."""
        self.config.load()
        self._load_bios_catalog()
        self.tree.clear()
        cores_dir = self.config.get_emulator_path("retroarch", "cores")
        if not cores_dir or not Path(cores_dir).is_dir():
            self.count_label.setText("Cores: diretório não configurado ou inexistente")
            return
        installed = {p.name.casefold() for p in Path(cores_dir).glob("*_libretro.dll") if p.is_file()}
        self.core_infos = self._load_core_index(installed)
        for info in self.core_infos:
            core_item = QTreeWidgetItem(self.tree)
            core_item.setText(0, info["label"])
            self._color_item(core_item, info["status"])
            core_item.setExpanded(True)
            for system in info["systems"]:
                system_item = QTreeWidgetItem(core_item)
                system_item.setText(1, system.native_id)
                if system.docs:
                    system_item.setToolTip(1, system.docs)
                bios_results = self.bios_service.scan_systems_for_core(info["core_name"]).get(system.system_id, [])
                if bios_results:
                    self._set_system_summary(system_item, bios_results)
                    for result in bios_results:
                        bios_item = QTreeWidgetItem(system_item)
                        bios_item.setText(2, result.definition.name + (" [obrigatória]" if result.definition.required else " [opcional]"))
                        bios_item.setToolTip(2, result.message or result.definition.destination)
                        self._color_item(bios_item, result.status)
                else:
                    system_item.setText(2, "Sem BIOS/firmware catalogada")
                    system_item.setForeground(1, self.COLORS["ok"])
        self.count_label.setText(f"Cores no diretório: {len(installed)} | Cores catalogados: {len(self.core_infos)}")
        self.status_label.setText("Catálogo carregado. Use 'Escanear BIOS dos cores' para recalcular os estados.")

    def _load_bios_catalog(self) -> None:
        """Carrega o dataset externo RetroBIOS."""
        system_dir = self.config.get_emulator_path("retroarch", "system")
        self.bios_service = RetroArchBiosService(system_dir)
        try:
            self.bios_service.load_catalog()
        except Exception as exc:
            self.status_label.setText(f"Erro ao carregar catálogo RetroBIOS: {type(exc).__name__}: {exc}")

    def _load_core_index(self, installed: set[str]) -> list[dict]:
        """Carrega índice oficial de cores para o canal Nightly atual."""
        try:
            channel = RetroArchDownloadService.channel("nightly")
            cores = RetroArchDownloadService().list_cores(channel)
        except Exception:
            cores = []
        result: list[dict] = []
        for core in cores:
            filename = core.filename.removesuffix(".zip").casefold()
            core_name = core.core_name
            systems = self.bios_service.systems_for_core(core_name)
            status = "ok" if filename in installed else "missing"
            result.append({"core_name": core_name, "label": core_name, "status": status, "systems": systems})
        return result

    def _set_system_summary(self, item: QTreeWidgetItem, results) -> None:
        """Exibe um resumo de estado na linha do sistema."""
        required = [result for result in results if result.definition.required]
        optional = [result for result in results if not result.definition.required]
        if any(result.status == "corrupt" for result in results):
            status = "corrupt"
        elif any(result.status == "missing" for result in required):
            status = "missing"
        elif any(result.status == "missing" for result in optional):
            status = "update"
        else:
            status = "ok"
        item.setText(2, self._status_text(status, required, optional))
        self._color_item(item, status)

    @staticmethod
    def _status_text(status: str, required, optional) -> str:
        """Formata o resumo de BIOS de um sistema."""
        required_ok = sum(result.status == "ok" for result in required)
        optional_ok = sum(result.status == "ok" for result in optional)
        if status == "missing":
            return f"Obrigatórias: {required_ok}/{len(required)} | Opcionais: {optional_ok}/{len(optional)}"
        if status == "corrupt":
            return f"BIOS corrompida | Obrigatórias: {required_ok}/{len(required)}"
        if status == "update":
            return f"Obrigatórias: {required_ok}/{len(required)} | Opcionais faltantes: {len(optional) - optional_ok}"
        return f"OK | Obrigatórias: {required_ok}/{len(required)} | Opcionais: {optional_ok}/{len(optional)}"

    def _color_item(self, item: QTreeWidgetItem, status: str) -> None:
        """Aplica a cor de estado pedida para cada linha."""
        color = self.COLORS.get(status, self.COLORS["text"])
        item.setForeground(0, color)
        item.setForeground(1, color)
        item.setForeground(2, color)

    def scan_bios(self) -> None:
        """Executa a varredura completa no System Directory configurado."""
        try:
            self._load_bios_catalog()
            results = self.bios_service.scan()
            counts = {key: 0 for key in ("ok", "missing", "corrupt", "update")}
            for result in results:
                counts[result.status] = counts.get(result.status, 0) + 1
            self.status_label.setText(
                f"BIOS escaneadas: {len(results)} | OK={counts['ok']} | ausentes={counts['missing']} | corrompidas={counts['corrupt']}"
            )
            self._render_bios_results(results)
        except Exception as exc:
            self.status_label.setText(f"Erro no scanner de BIOS: {type(exc).__name__}: {exc}")

    def _render_bios_results(self, results) -> None:
        """Reaplica os estados sem precisar consultar novamente o índice de cores."""
        by_destination = {result.definition.destination.replace("\\", "/").casefold(): result for result in results}
        for top_index in range(self.tree.topLevelItemCount()):
            core_item = self.tree.topLevelItem(top_index)
            for system_index in range(core_item.childCount()):
                system_item = core_item.child(system_index)
                for bios_index in range(system_item.childCount()):
                    bios_item = system_item.child(bios_index)
                    name = bios_item.toolTip(2).split(" | ", 1)[0]
                    for destination, result in by_destination.items():
                        if destination.endswith(name.casefold()):
                            self._color_item(bios_item, result.status)
                            break

    def rebuild_bios(self) -> None:
        """Placeholder seguro: abre o fluxo de reconstrução sem baixar BIOS protegidas."""
        self.status_label.setText(
            "Reconstrução preparada: a próxima etapa ligará este botão ao motor de reconstrução existente, usando o System Directory como destino."
        )

    def rebuild_from_folder(self) -> None:
        """Placeholder seguro para selecionar uma pasta-fonte e iniciar reconstrução."""
        from PySide6.QtWidgets import QFileDialog

        source = QFileDialog.getExistingDirectory(self, "Selecionar pasta de origem das BIOS")
        if not source:
            return
        destination = self.config.get_emulator_path("retroarch", "system")
        if not destination:
            self.status_label.setText("Diretório System do RetroArch não configurado.")
            return
        self.status_label.setText(
            f"Origem selecionada: {source} | destino de reconstrução: {destination}. Integração com o motor de reconstrução será executada na próxima etapa."
        )


__all__ = ["RetroArchCatalogTab"]
