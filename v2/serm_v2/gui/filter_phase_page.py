"""Fase 2: filtra exclusivamente um arquivo de scan ja concluido."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root, database_path, scans_root
from ..services.mame_fundamental_filter_service import (
    DEFAULT_FILTERS,
    FILTER_DEFINITIONS,
    MameFundamentalFilterService,
)
from ..services.scan_filter_service import ScanFilterService
from ..services.scan_repository import ScanRepository
from .filter_profiles_page import FilterProfileData


class FilteringPhasePage(QWidget):
    """Editor da fase 2, com o scan bruto como entrada imutavel."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._profiles_path = data_root() / "filter_profiles.json"
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("2 — FILTRAGEM DE ROMS")
        title.setProperty("role", "title")
        layout.addWidget(title)
        description = QLabel(
            "Entrada: arquivo de scan completo. Saida: novo arquivo filtrado. "
            "O arquivo de scan nunca e sobrescrito e nenhuma leitura do filesystem "
            "e feita para descobrir novamente as ROMs."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        input_box = QGroupBox("1. Selecionar scan concluido")
        input_layout = QVBoxLayout(input_box)
        self.scan_combo = QComboBox()
        self.scan_combo.currentIndexChanged.connect(self._scan_changed)
        input_layout.addWidget(self.scan_combo)
        self.scan_info = QLabel("Nenhum scan selecionado.")
        self.scan_info.setWordWrap(True)
        input_layout.addWidget(self.scan_info)
        layout.addWidget(input_box)

        profile_box = QGroupBox("2. Perfil de filtragem")
        profile_layout = QVBoxLayout(profile_box)
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        profile_layout.addWidget(self.profile_combo)
        profile_actions = QHBoxLayout()
        self.save_profile_button = QPushButton("SALVAR PERFIL")
        self.save_profile_button.clicked.connect(self._save_profile)
        profile_actions.addWidget(self.save_profile_button)
        profile_actions.addStretch()
        profile_layout.addLayout(profile_actions)
        layout.addWidget(profile_box)

        fundamental = QGroupBox("MAME — filtros fundamentais")
        fundamental_layout = QVBoxLayout(fundamental)
        self.fundamental_checks: dict[str, QCheckBox] = {}
        for key, definition in FILTER_DEFINITIONS.items():
            check = QCheckBox(str(definition["label"]))
            check.setToolTip(str(definition["description"]))
            check.setChecked(DEFAULT_FILTERS[key])
            self.fundamental_checks[key] = check
            fundamental_layout.addWidget(check)
        layout.addWidget(fundamental)

        advanced = QGroupBox("MAME — selecao de set")
        advanced_layout = QVBoxLayout(advanced)
        self.clone_policy = QComboBox()
        self.clone_policy.addItem("Com clones", "with_clones")
        self.clone_policy.addItem("Somente parents", "parents_only")
        advanced_layout.addWidget(self.clone_policy)
        self.include_bios = QCheckBox("Incluir BIOS")
        self.include_devices = QCheckBox("Incluir Devices")
        self.include_optional = QCheckBox("Incluir ROMs opcionais")
        self.working_only = QCheckBox("Somente máquinas working")
        for check in (self.include_bios, self.include_devices, self.include_optional, self.working_only):
            advanced_layout.addWidget(check)
        layout.addWidget(advanced)

        action_box = QGroupBox("3. Gerar arquivo filtrado")
        action_layout = QVBoxLayout(action_box)
        self.preview = QLabel("Selecione um scan para calcular o resultado.")
        self.preview.setWordWrap(True)
        action_layout.addWidget(self.preview)
        self.apply_button = QPushButton("APLICAR FILTROS E GERAR SCAN FILTRADO")
        self.apply_button.clicked.connect(self.apply_filters)
        action_layout.addWidget(self.apply_button)
        self.result_label = QLabel("Nenhum arquivo filtrado gerado nesta sessão.")
        self.result_label.setWordWrap(True)
        action_layout.addWidget(self.result_label)
        layout.addWidget(action_box)
        layout.addStretch()

    def refresh(self) -> None:
        self._refresh_scans()
        self._refresh_profiles()
        self._scan_changed()

    def _refresh_scans(self) -> None:
        repository = ScanRepository(database_path())
        self.scan_combo.blockSignals(True)
        self.scan_combo.clear()
        try:
            import sqlite3
            with sqlite3.connect(database_path()) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(
                    "SELECT * FROM scan_runs WHERE status IN ('completed','cancelled') "
                    "ORDER BY started_at DESC"
                ).fetchall()
        except sqlite3.Error:
            rows = []
        for row in rows:
            data = dict(row)
            label = f"{data['source']} › {data['system']} › {data['catalog_label'] or 'catalogo'} | {data['scan_id']}"
            self.scan_combo.addItem(label, data)
        self.scan_combo.blockSignals(False)

    def _refresh_profiles(self) -> None:
        profiles: list[FilterProfileData] = []
        try:
            raw = json.loads(self._profiles_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        try:
                            profiles.append(FilterProfileData(**{k: v for k, v in item.items() if k in FilterProfileData.__dataclass_fields__}))
                        except (TypeError, ValueError):
                            continue
        except (OSError, ValueError, TypeError):
            pass
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("Perfil novo / configuração atual", None)
        for profile in profiles:
            self.profile_combo.addItem(f"{profile.name} | {profile.source} › {profile.system}", profile)
        self.profile_combo.blockSignals(False)

    def _scan_changed(self, *_args) -> None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict):
            self.scan_info.setText("Nenhum scan selecionado.")
            self.apply_button.setEnabled(False)
            return
        self.scan_info.setText(
            f"Entrada imutável: {data.get('scan_file_path') or 'arquivo não localizado'}\n"
            f"Status: {data.get('status')} | itens: {int(data.get('items_examined') or 0):,} | "
            f"CURRENT: {self._status_count(data, 'CURRENT'):,} | MISSING: {self._status_count(data, 'MISSING'):,}"
        )
        is_mame = str(data.get("source", "")).casefold() == "mame"
        for widget in (*self.fundamental_checks.values(), self.clone_policy, self.include_bios, self.include_devices, self.include_optional, self.working_only):
            widget.setEnabled(is_mame)
        self.apply_button.setEnabled(is_mame)
        self._update_preview()

    @staticmethod
    def _status_count(data: dict, status: str) -> int:
        try:
            counts = json.loads(data.get("status_counts_json") or "{}")
            return int(counts.get(status, 0))
        except (TypeError, ValueError, json.JSONDecodeError):
            return 0

    def _profile_changed(self, *_args) -> None:
        profile = self.profile_combo.currentData()
        if isinstance(profile, FilterProfileData):
            values = MameFundamentalFilterService.load(profile.profile_id)
            for key, check in self.fundamental_checks.items():
                check.setChecked(values[key])
            self._set_profile_options(profile)
        self._update_preview()

    def _set_profile_options(self, profile: FilterProfileData) -> None:
        index = self.clone_policy.findData(profile.mame_clone_policy)
        if index >= 0:
            self.clone_policy.setCurrentIndex(index)
        self.include_bios.setChecked(profile.mame_include_bios)
        self.include_devices.setChecked(profile.mame_include_devices)
        self.include_optional.setChecked(profile.mame_include_optional)
        self.working_only.setChecked(profile.mame_working_only)

    def _current_profile(self) -> FilterProfileData | None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict):
            return None
        existing = self.profile_combo.currentData()
        if isinstance(existing, FilterProfileData):
            profile = existing
        else:
            now = str(__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat())
            profile = FilterProfileData(
                source=str(data.get("source", "MAME")),
                system=str(data.get("system", "")),
                dat_path=data.get("dat_path"),
                profile_id=uuid4().hex,
                name=f"{data.get('source')} — {data.get('system')} — filtro",
                created_at=now,
                updated_at=now,
            )
        profile.mame_clone_policy = str(self.clone_policy.currentData())
        profile.mame_include_bios = self.include_bios.isChecked()
        profile.mame_include_devices = self.include_devices.isChecked()
        profile.mame_include_optional = self.include_optional.isChecked()
        profile.mame_working_only = self.working_only.isChecked()
        return profile

    def _save_profile(self) -> None:
        profile = self._current_profile()
        if profile is None:
            QMessageBox.information(self, "Perfil", "Selecione um scan primeiro.")
            return
        profiles: list[FilterProfileData] = []
        try:
            raw = json.loads(self._profiles_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        try:
                            profiles.append(FilterProfileData(**{k: v for k, v in item.items() if k in FilterProfileData.__dataclass_fields__}))
                        except (TypeError, ValueError):
                            pass
        except (OSError, ValueError, TypeError):
            pass
        profiles = [item for item in profiles if item.profile_id != profile.profile_id]
        profiles.append(profile)
        self._profiles_path.parent.mkdir(parents=True, exist_ok=True)
        self._profiles_path.write_text(json.dumps([asdict(item) for item in profiles], indent=2, ensure_ascii=False), encoding="utf-8")
        MameFundamentalFilterService.save(profile.profile_id, {key: check.isChecked() for key, check in self.fundamental_checks.items()})
        self._refresh_profiles()
        self.result_label.setText(f"Perfil salvo: {profile.name} | ID={profile.profile_id}")

    def _update_preview(self) -> None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict) or str(data.get("source", "")).casefold() != "mame":
            self.preview.setText("A filtragem específica desta fase ainda não está disponível para esta fonte.")
            return
        path = Path(str(data.get("scan_file_path") or ""))
        if not path.is_file():
            self.preview.setText("Arquivo de scan não localizado no caminho registrado.")
            return
        profile = self._current_profile()
        if profile is None:
            return
        values = {key: check.isChecked() for key, check in self.fundamental_checks.items()}
        try:
            result = ScanFilterService.preview_mame(path, profile, values)
            self.preview.setText(
                f"Preview: entrada={result['input_count']:,} | selecionadas={result['output_count']:,} | "
                f"excluídas={result['filtered_count']:,}"
            )
        except Exception as exc:  # noqa: BLE001
            self.preview.setText(f"Preview indisponível: {type(exc).__name__}: {exc}")

    def apply_filters(self) -> None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict):
            return
        path = Path(str(data.get("scan_file_path") or ""))
        if not path.is_file():
            QMessageBox.warning(self, "Filtragem", "O arquivo de scan selecionado não existe mais.")
            return
        profile = self._current_profile()
        if profile is None:
            return
        values = {key: check.isChecked() for key, check in self.fundamental_checks.items()}
        try:
            result = ScanFilterService.apply_mame(path, profile, values)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Filtragem", f"Falha ao gerar arquivo filtrado:\n{exc}")
            return
        self._save_profile()
        ScanRepository(database_path()).save_filter_result(result)
        self.result_label.setText(
            f"ARQUIVO FILTRADO GERADO\n{result['filtered_file_path']}\n"
            f"entrada={result['input_count']:,} | saída={result['output_count']:,}"
        )


__all__ = ["FilteringPhasePage"]
