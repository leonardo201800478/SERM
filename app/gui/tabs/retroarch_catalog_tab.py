"""Catálogo RetroArch baseado nos .info locais, cores e BIOS."""
from __future__ import annotations

import binascii
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config.app_config import AppConfig
from app.core.services.retroarch_bios_reconstruction_service import RetroArchBiosReconstructionService
from app.core.services.retroarch_bios_service import RetroArchBiosService
from app.core.services.retroarch_catalog_database_service import RetroArchCatalogDatabaseService
from app.core.services.retroarch_download_service import RetroArchDownloadService
from app.core.services.retroarch_info_service import RetroArchInfoCore, RetroArchInfoService
from app.database.database import Database


class RetroArchCatalogTab(QWidget):
    """Catálogo hierárquico Core → Sistema → BIOS com scanner visual."""

    COLORS = {
        "ok": QColor(55, 185, 85),
        "update": QColor(220, 170, 35),
        "fixable": QColor(225, 175, 35),
        "corrupt": QColor(215, 55, 55),
        "missing": QColor(135, 135, 135),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        self.bios_service = RetroArchBiosService()
        self.core_service = RetroArchDownloadService()
        self.info_service = RetroArchInfoService()
        self.catalog_db = RetroArchCatalogDatabaseService(Database())
        self.core_infos: list[dict] = []
        self.info_cores: list[RetroArchInfoCore] = []
        self.last_bios_source: Path | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta catálogo, scanner, progresso e log persistente da sessão."""
        layout = QVBoxLayout(self)
        title = QLabel("Catálogo RetroArch")
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        description = QLabel(
            "Core → sistema → BIOS/firmware. Os .info locais são a fonte primária do catálogo; "
            "o Buildbot informa o estado dos cores instalados."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color:#888;")
        layout.addWidget(description)

        actions = QGroupBox("Ações")
        row = QHBoxLayout(actions)
        for text, slot in (
            ("Atualizar catálogo", self.refresh),
            ("Escanear BIOS dos cores", self.scan_bios),
            ("Reconstruir BIOS", self.rebuild_bios),
            ("Reconstruir a partir de uma pasta", self.rebuild_from_folder),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            row.addWidget(button)
        row.addStretch()
        layout.addWidget(actions)

        self.count_label = QLabel()
        layout.addWidget(self.count_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("BIOS: %p%")
        layout.addWidget(self.progress)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Core", "Sistema", "BIOS / Firmware"])
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(False)
        self.tree.setColumnWidth(0, 280)
        self.tree.setColumnWidth(1, 260)
        layout.addWidget(self.tree, 1)

        log_group = QGroupBox("Log do catálogo / scanner")
        log_layout = QVBoxLayout(log_group)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        log_layout.addWidget(self.log)
        clear_log = QPushButton("Limpar log")
        clear_log.clicked.connect(self.log.clear)
        log_layout.addWidget(clear_log)
        layout.addWidget(log_group)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color:#888;")
        layout.addWidget(self.status_label)

    def _log(self, message: str) -> None:
        """Adiciona uma mensagem ao log visual do catálogo."""
        self.log.appendPlainText(message)

    def refresh(self) -> None:
        """Atualiza o catálogo .info, banco local, cores e árvore da interface."""
        self.config.load()
        self.progress.setValue(0)
        self.tree.clear()
        self._load_bios_catalog()
        self._log("CATÁLOGO | iniciando atualização")

        info_directory = self.config.retroarch_native_paths.get("libretro_info_path")
        info_directory = Path(info_directory) if info_directory else None
        if info_directory and info_directory.is_dir():
            try:
                self.info_cores = self.info_service.scan_directory(info_directory)
                self.catalog_db.replace_catalog(self.info_cores)
                self.bios_service.load_info_catalog(self.info_cores)
                self._log(f"INFO | arquivos válidos={len(self.info_cores)} | origem={info_directory}")
            except Exception as exc:
                self.info_cores = []
                self._log(f"ERRO INFO | {type(exc).__name__}: {exc}")
                self.status_label.setText(f"Erro ao atualizar banco de .info: {type(exc).__name__}: {exc}")
        else:
            self.info_cores = []
            self._log("AVISO INFO | diretório libretro_info_path não configurado ou inexistente")

        cores_dir = self.config.get_emulator_path("retroarch", "cores")
        installed = {}
        if cores_dir and Path(cores_dir).is_dir():
            installed = {
                p.name.casefold(): p
                for p in Path(cores_dir).glob("*_libretro.dll")
                if p.is_file()
            }
        self.core_infos = self._load_core_index(installed)
        self._populate_tree()
        try:
            db_cores, db_systems, db_firmware = self.catalog_db.count()
        except Exception:
            db_cores = db_systems = db_firmware = 0
        self.count_label.setText(
            f"Cores instalados: {len(installed)} | Cores .info: {len(self.info_cores)} | "
            f"Sistemas: {sum(len(i['systems']) for i in self.core_infos)} | "
            f"Banco: {db_cores} cores / {db_systems} sistemas / {db_firmware} firmwares"
        )
        self.progress.setValue(100)
        self.status_label.setText(
            f"Catálogo atualizado a partir de {len(self.info_cores)} arquivo(s) .info. "
            "A árvore é construída a partir dos .info locais."
        )
        self._log(f"CATÁLOGO | árvore preenchida | cores={len(self.core_infos)}")

    def _load_bios_catalog(self) -> None:
        """Inicializa o scanner usando o System Directory real do RetroArch."""
        system_dir = self.config.get_emulator_path("retroarch", "system")
        self.bios_service = RetroArchBiosService(system_dir)
        self._log(f"SYSTEM | diretório={system_dir or 'não configurado'}")

    def _load_core_index(self, installed: dict[str, Path]) -> list[dict]:
        """Classifica os cores usando .info como catálogo primário.

        O Buildbot é consultado apenas para determinar se a DLL instalada está
        atualizada. Isso evita que a ausência de um core no índice impeça a
        árvore de sistemas/BIOS de ser construída.
        """
        buildbot_by_name = {}
        try:
            cores = self.core_service.list_cores(RetroArchDownloadService.channel("nightly"))
            buildbot_by_name = {core.filename.removesuffix(".zip").casefold(): core for core in cores}
            self._log(f"BUILDBOT | cores publicados={len(cores)}")
        except Exception as exc:
            self._log(f"AVISO BUILDBOT | {type(exc).__name__}: {exc}")

        result = []
        for index, local in enumerate(self.info_cores, start=1):
            dll_name = local.corename
            if not dll_name.casefold().endswith("_libretro"):
                dll_name += "_libretro"
            dll_name += ".dll"
            path = installed.get(dll_name.casefold())
            build = buildbot_by_name.get(dll_name.casefold())
            if path is None:
                status = "missing"
            elif build is None:
                status = "ok"
            elif self._crc32(path) == str(build.crc32).casefold().zfill(8):
                status = "ok"
            else:
                status = "update"
            systems = self.bios_service.systems_for_core(local.corename)
            result.append({
                "core_name": local.corename,
                "label": local.display_name or local.corename,
                "status": status,
                "systems": systems,
                "info": local,
                "path": path,
            })
            self._log(f"CORE {index}/{len(self.info_cores)} | {local.display_name} | sistemas={len(systems)} | {status}")
        return result

    def _populate_tree(self) -> None:
        """Preenche Core → Sistema → BIOS usando o catálogo local."""
        self.tree.clear()
        total = len(self.core_infos)
        for index, info in enumerate(self.core_infos, start=1):
            core_item = QTreeWidgetItem(self.tree)
            core_item.setText(0, info["label"])
            core_item.setToolTip(0, info["core_name"])
            self._color_item(core_item, info["status"])
            core_item.setExpanded(True)
            self.progress.setValue(int(index * 100 / total) if total else 100)

            if not info["systems"]:
                system_item = QTreeWidgetItem(core_item)
                system_item.setText(1, info["info"].system_name or info["info"].system_id or "Sistema não informado")
                system_item.setText(2, "Nenhuma BIOS/firmware declarada")
                self._color_item(system_item, "ok")
                continue

            for system in info["systems"]:
                system_item = QTreeWidgetItem(core_item)
                system_item.setText(1, system.native_id)
                system_item.setToolTip(1, system.docs or "")
                bios_results = self.bios_service.scan_systems_for_core(info["core_name"]).get(system.system_id, [])
                if bios_results:
                    self._set_system_summary(system_item, bios_results)
                    for result in bios_results:
                        bios_item = QTreeWidgetItem(system_item)
                        label = result.definition.name
                        label += " [obrigatória]" if result.definition.required else " [opcional]"
                        bios_item.setText(2, label)
                        bios_item.setToolTip(2, result.message or result.definition.destination)
                        self._color_item(bios_item, result.status)
                else:
                    system_item.setText(2, "Sem BIOS/firmware catalogada")
                    self._color_item(system_item, "ok")

    def _set_system_summary(self, item: QTreeWidgetItem, results) -> None:
        """Resume BIOS obrigatórias/opcionais e aplica o estado dominante."""
        required = [r for r in results if r.definition.required]
        optional = [r for r in results if not r.definition.required]
        if any(r.status == "corrupt" for r in results):
            status = "corrupt"
        elif any(r.status == "fixable" for r in results):
            status = "fixable"
        elif any(r.status == "missing" for r in required):
            status = "missing"
        elif any(r.status == "missing" for r in optional):
            status = "update"
        else:
            status = "ok"
        item.setText(2, self._status_text(status, required, optional))
        self._color_item(item, status)

    @staticmethod
    def _status_text(status: str, required, optional) -> str:
        """Formata o resumo de BIOS do sistema."""
        req_ok = sum(r.status == "ok" for r in required)
        opt_ok = sum(r.status == "ok" for r in optional)
        if status == "corrupt":
            return f"BIOS corrompida | Obrigatórias: {req_ok}/{len(required)}"
        if status == "fixable":
            return f"Correção possível | Obrigatórias: {req_ok}/{len(required)}"
        if status == "missing":
            return f"Obrigatórias: {req_ok}/{len(required)} | Opcionais: {opt_ok}/{len(optional)}"
        if status == "update":
            return f"OK | Obrigatórias: {req_ok}/{len(required)} | Opcionais faltantes: {len(optional)-opt_ok}"
        return f"OK | Obrigatórias: {req_ok}/{len(required)} | Opcionais: {opt_ok}/{len(optional)}"

    def _color_item(self, item: QTreeWidgetItem, status: str) -> None:
        """Aplica cor ao estado de core, sistema ou BIOS."""
        color = self.COLORS.get(status, QColor(235, 235, 235))
        for column in range(3):
            item.setForeground(column, color)

    def scan_bios(self) -> None:
        """Executa uma varredura completa com progresso e log detalhado."""
        self.progress.setValue(0)
        self._log("SCAN BIOS | iniciando")
        try:
            self.config.load()
            self._load_bios_catalog()
            if self.info_cores:
                self.bios_service.load_info_catalog(self.info_cores)
            if not self.bios_service.systems:
                raise ValueError("Nenhum sistema/firmware foi carregado dos arquivos .info.")
            results = self.bios_service.scan()
            counts = {key: sum(r.status == key for r in results) for key in ("ok", "fixable", "missing", "corrupt")}
            self.progress.setValue(100)
            self._log(
                f"SCAN BIOS | arquivos={len(results)} | OK={counts['ok']} | "
                f"corrigíveis={counts['fixable']} | ausentes={counts['missing']} | corrompidas={counts['corrupt']}"
            )
            self.status_label.setText(
                f"BIOS escaneadas: {len(results)} | OK={counts['ok']} | "
                f"corrigíveis={counts['fixable']} | ausentes={counts['missing']} | corrompidas={counts['corrupt']}"
            )
            self._populate_tree()
        except Exception as exc:
            self._log(f"ERRO SCAN BIOS | {type(exc).__name__}: {exc}")
            self.status_label.setText(f"Erro no scanner de BIOS: {type(exc).__name__}: {exc}")
            self.progress.setValue(0)

    def rebuild_from_folder(self) -> None:
        """Seleciona uma fonte e inicia reconstrução no System Directory."""
        source = QFileDialog.getExistingDirectory(self, "Selecionar pasta de origem das BIOS")
        if source:
            self.last_bios_source = Path(source)
            self._run_reconstruction(self.last_bios_source)

    def rebuild_bios(self) -> None:
        """Reexecuta a reconstrução usando a última fonte escolhida."""
        if self.last_bios_source is None:
            self.status_label.setText("Nenhuma fonte selecionada. Use 'Reconstruir a partir de uma pasta' primeiro.")
            self._log("RECONSTRUÇÃO | nenhuma pasta de origem selecionada")
            return
        self._run_reconstruction(self.last_bios_source)

    def _run_reconstruction(self, source: Path) -> None:
        """Reconstrói arquivos necessários no System Directory."""
        system_dir = self.config.get_emulator_path("retroarch", "system")
        if not system_dir:
            self._log("ERRO RECONSTRUÇÃO | System Directory não configurado")
            self.status_label.setText("Diretório System do RetroArch não configurado.")
            return
        try:
            self.progress.setValue(0)
            self._log(f"RECONSTRUÇÃO | origem={source} | destino={system_dir}")
            service = RetroArchBiosReconstructionService(system_dir)
            if self.info_cores:
                service.scanner.load_info_catalog(self.info_cores)
            else:
                service.load_catalog()
            results = service.reconstruct_needed(source)
            rebuilt = sum(r.status == "reconstructed" for r in results)
            missing = sum(r.status == "missing" for r in results)
            self.progress.setValue(100)
            self._log(f"RECONSTRUÇÃO | reconstruídos={rebuilt} | não encontrados={missing}")
            self.status_label.setText(
                f"Reconstrução concluída | reparados={rebuilt} | não encontrados={missing} | destino={system_dir}"
            )
            self.scan_bios()
        except Exception as exc:
            self._log(f"ERRO RECONSTRUÇÃO | {type(exc).__name__}: {exc}")
            self.status_label.setText(f"Erro na reconstrução: {type(exc).__name__}: {exc}")
            self.progress.setValue(0)

    @staticmethod
    def _crc32(path: Path) -> str:
        """Calcula CRC32 de uma DLL instalada."""
        crc = 0
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                crc = binascii.crc32(chunk, crc)
        return f"{crc & 0xffffffff:08x}"


__all__ = ["RetroArchCatalogTab"]
