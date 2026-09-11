"""Painel de curadoria do MAME Studio."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QGroupBox, QLabel, QLineEdit, QVBoxLayout, QWidget


class MameCurationPanel(QWidget):
    """Editor compacto da política de curadoria aplicada antes do filtro físico."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        intro = QLabel(
            "A curadoria escolhe as machines antes da montagem do SET. "
            "O scan original permanece intacto e cada exclusão gera uma decisão auditável."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        preferences = QGroupBox("Preferências de seleção")
        form = QFormLayout(preferences)
        self.regions = QLineEdit()
        self.regions.setPlaceholderText("World, USA, Europe, Japan")
        self.languages = QLineEdit()
        self.languages.setPlaceholderText("English, Portuguese, Spanish")
        self.max_players = QLineEdit()
        self.max_players.setPlaceholderText("vazio = sem limite")
        self.max_buttons = QLineEdit()
        self.max_buttons.setPlaceholderText("vazio = sem limite")
        self.controls = QLineEdit()
        self.controls.setPlaceholderText("joystick, joy, paddle")
        self.directions = QLineEdit()
        self.directions.setPlaceholderText("2-way, 4-way, 8-way")
        form.addRow("Regiões preferidas:", self.regions)
        form.addRow("Idiomas preferidos:", self.languages)
        form.addRow("Máx. jogadores:", self.max_players)
        form.addRow("Máx. botões:", self.max_buttons)
        form.addRow("Controles aceitos:", self.controls)
        form.addRow("Direções aceitas:", self.directions)
        root.addWidget(preferences)

        rules = QGroupBox("Regras da curadoria")
        rule_form = QFormLayout(rules)
        self.orientation = QComboBox()
        self.orientation.addItem("Qualquer orientação", "both")
        self.orientation.addItem("Horizontal", "horizontal")
        self.orientation.addItem("Vertical", "vertical")
        self.strict_controls = QCheckBox("Exigir todos os controles/direções informados")
        self.include_clones = QCheckBox("Permitir clones")
        self.include_clones.setChecked(True)
        self.include_bootlegs = QCheckBox("Permitir bootlegs")
        self.include_bootlegs.setChecked(True)
        self.include_prototypes = QCheckBox("Permitir protótipos")
        self.include_prototypes.setChecked(True)
        self.one_game_one_rom = QCheckBox("1G1R — um representante por família parent/clone")
        self.min_quality = QLineEdit()
        self.min_quality.setPlaceholderText("vazio = sem limite")
        rule_form.addRow("Orientação:", self.orientation)
        rule_form.addRow(self.strict_controls)
        rule_form.addRow(self.include_clones)
        rule_form.addRow(self.include_bootlegs)
        rule_form.addRow(self.include_prototypes)
        rule_form.addRow(self.one_game_one_rom)
        rule_form.addRow("Qualidade mínima:", self.min_quality)
        root.addWidget(rules)
        root.addStretch()

    @staticmethod
    def _split(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    def values(self) -> dict:
        def optional_int(widget: QLineEdit):
            value = widget.text().strip()
            if not value:
                return None
            try:
                return int(value)
            except ValueError:
                return None

        def optional_float(widget: QLineEdit):
            value = widget.text().strip().replace(",", ".")
            if not value:
                return None
            try:
                return float(value)
            except ValueError:
                return None

        return {
            "curation_preferred_regions": self._split(self.regions.text()),
            "curation_preferred_languages": self._split(self.languages.text()),
            "curation_max_players": optional_int(self.max_players),
            "curation_max_buttons": optional_int(self.max_buttons),
            "curation_required_controls": self._split(self.controls.text()),
            "curation_required_directions": self._split(self.directions.text()),
            "curation_strict_controls": self.strict_controls.isChecked(),
            "curation_orientation": str(self.orientation.currentData()),
            "curation_include_clones": self.include_clones.isChecked(),
            "curation_include_bootlegs": self.include_bootlegs.isChecked(),
            "curation_include_prototypes": self.include_prototypes.isChecked(),
            "curation_one_game_one_rom": self.one_game_one_rom.isChecked(),
            "curation_min_quality_score": optional_float(self.min_quality),
        }

    def set_values(self, values: dict | None) -> None:
        values = values or {}
        self.regions.setText(", ".join(values.get("curation_preferred_regions", []) or []))
        self.languages.setText(", ".join(values.get("curation_preferred_languages", []) or []))
        self.max_players.setText(self._format(values.get("curation_max_players")))
        self.max_buttons.setText(self._format(values.get("curation_max_buttons")))
        self.controls.setText(", ".join(values.get("curation_required_controls", []) or []))
        self.directions.setText(", ".join(values.get("curation_required_directions", []) or []))
        self.strict_controls.setChecked(bool(values.get("curation_strict_controls", False)))
        index = self.orientation.findData(values.get("curation_orientation", "both"))
        self.orientation.setCurrentIndex(max(index, 0))
        self.include_clones.setChecked(bool(values.get("curation_include_clones", True)))
        self.include_bootlegs.setChecked(bool(values.get("curation_include_bootlegs", True)))
        self.include_prototypes.setChecked(bool(values.get("curation_include_prototypes", True)))
        self.one_game_one_rom.setChecked(bool(values.get("curation_one_game_one_rom", False)))
        self.min_quality.setText(self._format(values.get("curation_min_quality_score")))

    @staticmethod
    def _format(value) -> str:
        return "" if value is None else str(value)


__all__ = ["MameCurationPanel"]
