"""Tela dedicada de filtros MAME dividida em tipo de jogos, curadoria e SET."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root, database_path
from ..services.mame_fundamental_filter_service import (
    DEFAULT_FILTERS,
    FILTER_DEFINITIONS,
    MameFundamentalFilterService,
)
from ..services.scan_filter_service import ScanFilterService
from ..services.scan_repository import ScanRepository
from .components.mame_curation_panel import MameCurationPanel
from .filter_profiles_page import FilterProfileData


class MameFilterPage(QWidget):
    """Configuração e aplicação dos filtros MAME V2."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._profiles_path = data_root() / "filter_profiles.json"
        self._curation_profiles_path = data_root() / "mame_curation_profiles.json"
        self._building = False
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("MAME — FILTROS")
        title.setProperty("role", "title")
        root.addWidget(title)
        description = QLabel(
            "O pipeline agora separa classificação, curadoria e montagem do SET. "
            "A curadoria ocorre depois do catálogo/scan e antes da filtragem física e da reconstrução."
        )
        description.setWordWrap(True)
        root.addWidget(description)

        scan_box = QGroupBox("Scan MAME de entrada")
        scan_layout = QVBoxLayout(scan_box)
        row = QHBoxLayout()
        self.scan_combo = QComboBox()
        self.scan_combo.currentIndexChanged.connect(self._scan_changed)
        row.addWidget(self.scan_combo, 1)
        refresh = QPushButton("ATUALIZAR SCANS")
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)
        scan_layout.addLayout(row)
        self.scan_info = QLabel("Nenhum scan selecionado.")
        self.scan_info.setWordWrap(True)
        scan_layout.addWidget(self.scan_info)
        root.addWidget(scan_box)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._game_type_page(), "1 — TIPO DE JOGOS")
        self.curation_panel = MameCurationPanel()
        self.curation_panel.changed.connect(self._update_preview)
        self.tabs.addTab(self.curation_panel, "2 — CURADORIA")
        self.tabs.addTab(self._set_type_page(), "3 — TIPO DE SET")
        root.addWidget(self.tabs, 1)

        actions = QHBoxLayout()
        self.new_profile_button = QPushButton("NOVO PERFIL")
        self.save_button = QPushButton("SALVAR FILTROS")
        self.apply_button = QPushButton("APLICAR E GERAR ARQUIVO FILTRADO")
        self.new_profile_button.clicked.connect(self.new_profile)
        self.save_button.clicked.connect(self.save_profile)
        self.apply_button.clicked.connect(self.apply_filters)
        actions.addWidget(self.new_profile_button)
        actions.addWidget(self.save_button)
        actions.addWidget(self.apply_button)
        actions.addStretch()
        root.addLayout(actions)

        self.preview = QLabel("Selecione um scan para calcular o preview.")
        self.preview.setWordWrap(True)
        root.addWidget(self.preview)
        self.result = QLabel("Nenhum arquivo filtrado gerado nesta sessão.")
        self.result.setWordWrap(True)
        root.addWidget(self.result)

    def _game_type_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        intro = QLabel(
            "Marque os tipos que devem ser EXCLUÍDOS do set final. A classificação é a congelada no snapshot do scan."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        box = QGroupBox("Classificação do jogo")
        box_layout = QVBoxLayout(box)
        self.game_checks: dict[str, QCheckBox] = {}
        for key, definition in FILTER_DEFINITIONS.items():
            check = QCheckBox(str(definition["label"]))
            check.setToolTip(str(definition["description"]))
            check.setChecked(DEFAULT_FILTERS[key])
            check.toggled.connect(self._update_preview)
            self.game_checks[key] = check
            box_layout.addWidget(check)
        layout.addWidget(box)
        layout.addStretch()
        return page

    def _set_type_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        intro = QLabel(
            "Tipo de SET é uma decisão de montagem/reconstrução. Ele fica salvo no perfil e acompanha o arquivo filtrado."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        set_box = QGroupBox("Formato do SET")
        set_layout = QVBoxLayout(set_box)
        self.set_type = QComboBox()
        self.set_type.addItem("Split — arquivos dependentes separados", "split")
        self.set_type.addItem("Non-Merged — cada set independente", "non_merged")
        self.set_type.addItem("Full-Merged — parent + clones no mesmo set", "full_merged")
        self.set_type.currentIndexChanged.connect(self._update_preview)
        set_layout.addWidget(self.set_type)
        layout.addWidget(set_box)

        clone_box = QGroupBox("Seleção de máquinas")
        clone_layout = QVBoxLayout(clone_box)
        self.clone_policy = QComboBox()
        self.clone_policy.addItem("Com clones", "with_clones")
        self.clone_policy.addItem("Somente parents", "parents_only")
        self.clone_policy.currentIndexChanged.connect(self._update_preview)
        clone_layout.addWidget(self.clone_policy)
        self.include_bios = QCheckBox("Incluir BIOS / sets de BIOS")
        self.include_devices = QCheckBox("Incluir Devices")
        self.include_chd = QCheckBox("Incluir CHDs / disks")
        self.include_optional = QCheckBox("Incluir ROMs opcionais")
        self.working_only = QCheckBox("Somente máquinas working")
        self.include_chd.setChecked(True)
        self.include_optional.setChecked(True)
        for check in (
            self.include_bios,
            self.include_devices,
            self.include_chd,
            self.include_optional,
            self.working_only,
        ):
            check.toggled.connect(self._update_preview)
            clone_layout.addWidget(check)
        layout.addWidget(clone_box)

        self.set_note = QLabel(
            "Observação: Split/Non-Merged/Full-Merged não descartam evidências do scan por si só; "
            "eles definem como os arquivos selecionados deverão ser organizados na reconstrução."
        )
        self.set_note.setWordWrap(True)
        layout.addWidget(self.set_note)
        layout.addStretch()
        return page

    def _read_profiles(self) -> list[FilterProfileData]:
        try:
            raw = json.loads(self._profiles_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return []
        if not isinstance(raw, list):
            return []
        profiles: list[FilterProfileData] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                profiles.append(
                    FilterProfileData(
                        **{
                            k: v
                            for k, v in item.items()
                            if k in FilterProfileData.__dataclass_fields__
                        }
                    )
                )
            except (TypeError, ValueError):
                continue
        return profiles

    def _read_curation_profiles(self) -> list[dict]:
        try:
            raw = json.loads(self._curation_profiles_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return []
        return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []

    def _current_curation(self) -> dict:
        return self.curation_panel.values()

    def _load_curation(self, profile: FilterProfileData | None) -> None:
        if profile is None:
            self.curation_panel.set_values({})
            return
        records = self._read_curation_profiles()
        record = next((item for item in records if item.get("profile_id") == profile.profile_id), None)
        if record is None:
            record = next((item for item in records if item.get("system") == profile.system), None)
        self.curation_panel.set_values(record.get("values", {}) if record else {})

    def _save_curation(self, profile: FilterProfileData) -> None:
        records = [
            item for item in self._read_curation_profiles()
            if item.get("profile_id") != profile.profile_id and item.get("system") != profile.system
        ]
        records.append({"profile_id": profile.profile_id, "system": profile.system, "values": self._current_curation()})
        self._curation_profiles_path.parent.mkdir(parents=True, exist_ok=True)
        self._curation_profiles_path.write_text(
            json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def refresh(self) -> None:
        self.scan_combo.blockSignals(True)
        self.scan_combo.clear()
        for row in ScanRepository(database_path()).list_for_source("MAME"):
            label = str(row.get("catalog_label") or "MAME")
            self.scan_combo.addItem(
                f"{label} › {row.get('scan_type') or 'full'} | {row.get('scan_id')}", row
            )
        self.scan_combo.blockSignals(False)
        self._scan_changed()

    @staticmethod
    def _counts(row: dict) -> dict[str, int]:
        try:
            raw = json.loads(row.get("status_counts_json") or "{}")
            return {str(k): int(v) for k, v in raw.items()}
        except (TypeError, ValueError, AttributeError):
            return {}

    def _scan_changed(self, *_args) -> None:
        row = self.scan_combo.currentData()
        if not isinstance(row, dict):
            self.scan_info.setText("Nenhum scan MAME concluído.")
            self.apply_button.setEnabled(False)
            self.curation_panel.set_values({})
            return
        counts = self._counts(row)
        self.scan_info.setText(
            f"Arquivo: {row.get('scan_file_path') or '—'}\n"
            f"CURRENT={counts.get('CURRENT', 0):,} | MISSING={counts.get('MISSING', 0):,} | WRONG={counts.get('WRONG', 0):,}"
        )
        self.apply_button.setEnabled(Path(str(row.get("scan_file_path") or "")).is_file())
        self._load_curation(self._current_profile())
        self._update_preview()

    def _current_profile(self) -> FilterProfileData | None:
        row = self.scan_combo.currentData()
        if not isinstance(row, dict):
            return None
        now = datetime.now(UTC).isoformat()
        profiles = self._read_profiles()
        existing = next(
            (
                p
                for p in profiles
                if p.source == "MAME" and p.system == str(row.get("system") or "MAME")
            ),
            None,
        )
        profile = existing or FilterProfileData(
            source="MAME",
            system=str(row.get("system") or "MAME"),
            dat_path=row.get("dat_path"),
            profile_id=str(uuid4()),
            name=f"MAME — {row.get('system') or 'MAME'} — filtros",
            created_at=now,
            updated_at=now,
        )
        profile.updated_at = now
        profile.mame_set_type = str(self.set_type.currentData())
        profile.mame_clone_policy = str(self.clone_policy.currentData())
        profile.mame_include_bios = self.include_bios.isChecked()
        profile.mame_include_devices = self.include_devices.isChecked()
        profile.mame_include_chd = self.include_chd.isChecked()
        profile.mame_include_optional = self.include_optional.isChecked()
        profile.mame_working_only = self.working_only.isChecked()
        return profile

    def _values(self) -> dict[str, bool]:
        return {key: check.isChecked() for key, check in self.game_checks.items()}

    def _update_preview(self, *_args) -> None:
        if self._building:
            return
        row = self.scan_combo.currentData()
        if not isinstance(row, dict):
            return
        path = Path(str(row.get("scan_file_path") or ""))
        if not path.is_file():
            self.preview.setText("Preview indisponível: arquivo de scan não localizado.")
            return
        profile = self._current_profile()
        if profile is None:
            return
        try:
            result = ScanFilterService.preview_mame(
                path,
                profile,
                self._values(),
                curation_values=self._current_curation(),
            )
            self.preview.setText(
                f"Preview | entrada={result['input_count']:,} | selecionadas={result['output_count']:,} | "
                f"excluídas={result['filtered_count']:,} | curadoria={result.get('curation_selected', 0):,} "
                f"selecionadas / {result.get('curation_excluded', 0):,} decisões | SET={profile.mame_set_type}"
            )
        except Exception as exc:
            self.preview.setText(f"Preview indisponível: {type(exc).__name__}: {exc}")

    def new_profile(self) -> None:
        row = self.scan_combo.currentData()
        if not isinstance(row, dict):
            QMessageBox.information(self, "Novo perfil", "Selecione um scan MAME primeiro.")
            return
        self._building = True
        try:
            for key, default in DEFAULT_FILTERS.items():
                self.game_checks[key].setChecked(default)
            self.set_type.setCurrentIndex(0)
            self.clone_policy.setCurrentIndex(0)
            self.include_bios.setChecked(False)
            self.include_devices.setChecked(False)
            self.include_chd.setChecked(True)
            self.include_optional.setChecked(True)
            self.working_only.setChecked(False)
            self.curation_panel.set_values({})
        finally:
            self._building = False
        self._update_preview()

    def save_profile(self) -> None:
        profile = self._current_profile()
        if profile is None:
            QMessageBox.information(self, "Filtros MAME", "Selecione um scan MAME.")
            return
        profiles = [p for p in self._read_profiles() if p.profile_id != profile.profile_id]
        profiles.append(profile)
        self._profiles_path.parent.mkdir(parents=True, exist_ok=True)
        self._profiles_path.write_text(
            json.dumps([asdict(p) for p in profiles], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        MameFundamentalFilterService.save(profile.profile_id, self._values())
        self._save_curation(profile)
        curation = self._current_curation()
        self.result.setText(
            f"Filtros salvos: {profile.name} | curadoria 1G1R={'sim' if curation['curation_one_game_one_rom'] else 'não'} | SET={profile.mame_set_type}"
        )

    def apply_filters(self) -> None:
        row = self.scan_combo.currentData()
        if not isinstance(row, dict):
            return
        path = Path(str(row.get("scan_file_path") or ""))
        if not path.is_file():
            QMessageBox.warning(self, "Filtros MAME", "O arquivo do scan não existe mais.")
            return
        profile = self._current_profile()
        if profile is None:
            return
        try:
            values = self._values()
            curation = self._current_curation()
            result = ScanFilterService.apply_mame(
                path, profile, values, curation_values=curation
            )
            self.save_profile()
            ScanRepository(database_path()).save_filter_result(result)
            self.result.setText(
                f"ARQUIVO FILTRADO GERADO\n{result['filtered_file_path']}\n"
                f"entrada={result['input_count']:,} | saída={result['output_count']:,} | "
                f"curadoria={result.get('curation_selected', 0):,} selecionadas / "
                f"{result.get('curation_excluded', 0):,} decisões | SET={profile.mame_set_type}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Filtros MAME", f"Falha ao aplicar filtros:\n{exc}")


__all__ = ["MameFilterPage"]
