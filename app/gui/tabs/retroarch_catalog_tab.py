"""Catálogo RetroArch: cores, sistemas e BIOS/firmware."""
from __future__ import annotations

import binascii
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFileDialog, QGroupBox, QHBoxLayout, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from app.config.app_config import AppConfig
from app.core.services.retroarch_bios_reconstruction_service import RetroArchBiosReconstructionService
from app.core.services.retroarch_bios_service import RetroArchBiosService
from app.core.services.retroarch_download_service import RetroArchDownloadService


class RetroArchCatalogTab(QWidget):
    """Catálogo hierárquico Core → Sistema → BIOS com scanner e reconstrução."""
    COLORS = {"ok": QColor(80, 205, 105), "update": QColor(230, 190, 60), "fixable": QColor(235, 190, 55), "corrupt": QColor(225, 70, 70), "missing": QColor(125, 125, 125)}

    def __init__(self, parent=None):
        super().__init__(parent); self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig(); self.bios_service = RetroArchBiosService(); self.core_service = RetroArchDownloadService()
        self.core_infos = []; self.last_bios_source: Path | None = None; self._build_ui(); self.refresh()

    def _build_ui(self) -> None:
        """Monta catálogo, scanner e ações de BIOS."""
        layout = QVBoxLayout(self); title = QLabel("Catálogo RetroArch"); title.setStyleSheet("font-size:22px;font-weight:bold;"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(title)
        description = QLabel("Core → sistema → BIOS/firmware, com validação contra o System Directory configurado no RetroArch."); description.setWordWrap(True); description.setStyleSheet("color:#888;"); layout.addWidget(description)
        actions = QGroupBox("Ações"); row = QHBoxLayout(actions)
        for text, slot in (("Atualizar catálogo", self.refresh), ("Escanear BIOS dos cores", self.scan_bios), ("Reconstruir BIOS", self.rebuild_bios), ("Reconstruir a partir de uma pasta", self.rebuild_from_folder)):
            button = QPushButton(text); button.clicked.connect(slot); row.addWidget(button)
        row.addStretch(); layout.addWidget(actions)
        self.count_label = QLabel(); layout.addWidget(self.count_label)
        self.tree = QTreeWidget(); self.tree.setColumnCount(3); self.tree.setHeaderLabels(["Core", "Sistema", "BIOS / Firmware"]); self.tree.setRootIsDecorated(True); self.tree.setAlternatingRowColors(True); self.tree.setUniformRowHeights(False); layout.addWidget(self.tree, 1)
        self.status_label = QLabel(); self.status_label.setWordWrap(True); self.status_label.setStyleSheet("color:#888;"); layout.addWidget(self.status_label)

    def refresh(self) -> None:
        """Atualiza cores, sistemas e estados das BIOS."""
        self.config.load(); self._load_bios_catalog(); self.tree.clear(); cores_dir = self.config.get_emulator_path("retroarch", "cores")
        if not cores_dir or not Path(cores_dir).is_dir(): self.count_label.setText("Cores: diretório não configurado ou inexistente"); return
        installed = {p.name.casefold(): p for p in Path(cores_dir).glob("*_libretro.dll") if p.is_file()}; self.core_infos = self._load_core_index(installed)
        for info in self.core_infos:
            core_item = QTreeWidgetItem(self.tree); core_item.setText(0, info["label"]); self._color_item(core_item, info["status"]); core_item.setExpanded(True)
            for system in info["systems"]:
                system_item = QTreeWidgetItem(core_item); system_item.setText(1, system.native_id); system_item.setToolTip(1, system.docs or "")
                bios_results = self.bios_service.scan_systems_for_core(info["core_name"]).get(system.system_id, [])
                if bios_results:
                    self._set_system_summary(system_item, bios_results)
                    for result in bios_results:
                        bios_item = QTreeWidgetItem(system_item); bios_item.setText(2, result.definition.name + (" [obrigatória]" if result.definition.required else " [opcional]")); bios_item.setToolTip(2, result.message or result.definition.destination); self._color_item(bios_item, result.status)
                else: system_item.setText(2, "Sem BIOS/firmware catalogada")
        self.count_label.setText(f"Cores instalados: {len(installed)} | Cores publicados: {len(self.core_infos)} | Sistemas: {sum(len(i['systems']) for i in self.core_infos)}")
        self.status_label.setText("Catálogo atualizado. Estados das BIOS são calculados no System Directory real.")

    def _load_bios_catalog(self) -> None:
        """Carrega RetroBIOS e ancora a verificação no System Directory."""
        system_dir = self.config.get_emulator_path("retroarch", "system"); self.bios_service = RetroArchBiosService(system_dir)
        try: self.bios_service.load_catalog()
        except Exception as exc: self.status_label.setText(f"Erro ao carregar catálogo RetroBIOS: {type(exc).__name__}: {exc}")

    def _load_core_index(self, installed: dict[str, Path]) -> list[dict]:
        """Classifica cada core como atualizado, desatualizado ou ausente."""
        try: cores = self.core_service.list_cores(RetroArchDownloadService.channel("nightly"))
        except Exception as exc: self.status_label.setText(f"Erro no índice de cores: {type(exc).__name__}: {exc}"); return []
        result = []
        for core in cores:
            dll_name = core.filename.removesuffix(".zip"); path = installed.get(dll_name.casefold()); status = "missing" if path is None else ("ok" if self._crc32(path) == core.crc32.casefold().zfill(8) else "corrupt")
            result.append({"core_name": core.core_name, "label": core.core_name, "status": status, "systems": self.bios_service.systems_for_core(core.core_name), "core": core})
        return result

    def _set_system_summary(self, item: QTreeWidgetItem, results) -> None:
        """Resume BIOS obrigatórias e opcionais e aplica o estado dominante."""
        required = [r for r in results if r.definition.required]; optional = [r for r in results if not r.definition.required]
        if any(r.status == "corrupt" for r in results): status = "corrupt"
        elif any(r.status == "fixable" for r in results): status = "fixable"
        elif any(r.status == "missing" for r in required): status = "missing"
        elif any(r.status == "missing" for r in optional): status = "update"
        else: status = "ok"
        item.setText(2, self._status_text(status, required, optional)); self._color_item(item, status)

    @staticmethod
    def _status_text(status: str, required, optional) -> str:
        """Formata o resumo de BIOS do sistema."""
        req_ok = sum(r.status == "ok" for r in required); opt_ok = sum(r.status == "ok" for r in optional)
        if status == "corrupt": return f"BIOS corrompida | Obrigatórias: {req_ok}/{len(required)}"
        if status == "fixable": return f"Correção possível | Obrigatórias: {req_ok}/{len(required)}"
        if status == "missing": return f"Obrigatórias: {req_ok}/{len(required)} | Opcionais: {opt_ok}/{len(optional)}"
        if status == "update": return f"OK | Obrigatórias: {req_ok}/{len(required)} | Opcionais faltantes: {len(optional)-opt_ok}"
        return f"OK | Obrigatórias: {req_ok}/{len(required)} | Opcionais: {opt_ok}/{len(optional)}"

    def _color_item(self, item: QTreeWidgetItem, status: str) -> None:
        """Aplica cor ao estado de core, sistema ou BIOS."""
        color = self.COLORS.get(status, QColor(235, 235, 235)); [item.setForeground(column, color) for column in range(3)]

    def scan_bios(self) -> None:
        """Executa varredura completa e atualiza a árvore."""
        try:
            self._load_bios_catalog(); results = self.bios_service.scan(); counts = {k: sum(r.status == k for r in results) for k in ("ok", "fixable", "missing", "corrupt")}
            self.status_label.setText(f"BIOS escaneadas: {len(results)} | OK={counts['ok']} | corrigíveis={counts['fixable']} | ausentes={counts['missing']} | corrompidas={counts['corrupt']}"); self.refresh()
        except Exception as exc: self.status_label.setText(f"Erro no scanner de BIOS: {type(exc).__name__}: {exc}")

    def rebuild_from_folder(self) -> None:
        """Seleciona a fonte, salva-a para as próximas reconstruções e repara o catálogo."""
        source = QFileDialog.getExistingDirectory(self, "Selecionar pasta de origem das BIOS")
        if source: self.last_bios_source = Path(source); self._run_reconstruction(self.last_bios_source)

    def rebuild_bios(self) -> None:
        """Reexecuta a reconstrução usando a última fonte escolhida."""
        if self.last_bios_source is None: self.status_label.setText("Nenhuma fonte selecionada. Use 'Reconstruir a partir de uma pasta' primeiro."); return
        self._run_reconstruction(self.last_bios_source)

    def _run_reconstruction(self, source: Path) -> None:
        """Reconstrói ausentes, corrigíveis e corrompidas no System Directory."""
        system_dir = self.config.get_emulator_path("retroarch", "system")
        if not system_dir: self.status_label.setText("Diretório System do RetroArch não configurado."); return
        try:
            service = RetroArchBiosReconstructionService(system_dir); service.load_catalog(); results = service.reconstruct_needed(source)
            rebuilt = sum(r.status == "reconstructed" for r in results); missing = sum(r.status == "missing" for r in results)
            self.status_label.setText(f"Reconstrução concluída | reparados={rebuilt} | não encontrados={missing} | destino={system_dir}"); self.scan_bios()
        except Exception as exc: self.status_label.setText(f"Erro na reconstrução: {type(exc).__name__}: {exc}")

    @staticmethod
    def _crc32(path: Path) -> str:
        """Calcula CRC32 de uma DLL instalada."""
        crc = 0
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024): crc = binascii.crc32(chunk, crc)
        return f"{crc & 0xffffffff:08x}"


__all__ = ["RetroArchCatalogTab"]
