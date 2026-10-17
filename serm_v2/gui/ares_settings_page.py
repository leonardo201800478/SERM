"""Video configuration for ares, matching the emulator's native menus."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root
from .directories_guide_page import ConfigFileEditor


class AresSettingsPage(QWidget):
    """Expose the ares video controls, window/output menus, and installed shaders."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    WINDOW_SIZES = (
        ("NTSC 4:3 (640×480)", 640, 480),
        ("PAL 4:3 (768×576)", 768, 576),
        ("SVGA 4:3 (800×600)", 800, 600),
        ("qHD 4:3 (960×720)", 960, 720),
        ("XGA 4:3 (1024×768)", 1024, 768),
        ("XGA+ 4:3 (1152×864)", 1152, 864),
        ("HD 16:9 (1280×720)", 1280, 720),
        ("SXGA 4:3 (1280×960)", 1280, 960),
        ("WXGA (1366×768)", 1366, 768),
        ("HD+ 16:9 (1600×900)", 1600, 900),
    )
    QUALITY_VALUES = (("SD", "1× Native"), ("HD", "2× Native"), ("UHD", "4× Native"))

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.checks: dict[str, QCheckBox] = {}
        self.check_initial: dict[str, bool] = {}
        self.sliders: dict[str, tuple[QSlider, QLabel, int]] = {}
        self.quality_buttons: dict[str, QRadioButton] = {}
        self._build_ui()
        self.refresh()

    @classmethod
    def _paths(cls) -> dict[str, str]:
        try:
            data = json.loads(cls.PATHS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return (
            {str(key): str(value) for key, value in data.items()} if isinstance(data, dict) else {}
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("Configurações de vídeo do ares")
        title.setProperty("role", "title")
        root.addWidget(title)
        note = QLabel("As opções são aplicadas ao settings.bml selecionado em Diretórios.")
        note.setWordWrap(True)
        root.addWidget(note)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        video_page = QWidget()
        video_layout = QVBoxLayout(video_page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        color_group = QGroupBox("Ajuste de cor")
        color_form = QFormLayout(color_group)
        self._add_slider(color_form, "Video.Luminance", "Luminância", 0, 100, 0)
        self._add_slider(color_form, "Video.Saturation", "Saturação", 0, 200, 0)
        self._add_slider(color_form, "Video.Gamma", "Gama", 0, 100, 100)
        layout.addWidget(color_group)

        emulator_group = QGroupBox("Configurações do emulador")
        emulator_form = QFormLayout(emulator_group)
        for key, label in (
            ("Video.ColorBleed", "Color Bleed"),
            ("Video.ColorEmulation", "Color Emulation"),
            ("Video.DeepBlackBoost", "Deep Black Boost"),
            ("Video.InterframeBlending", "Interframe Blending"),
            ("Video.Overscan", "Overscan"),
            ("Video.PixelAccuracy", "Pixel Accuracy"),
        ):
            emulator_form.addRow(self._check(key, label))
        layout.addWidget(emulator_group)

        n64_group = QGroupBox("Renderização do Nintendo 64")
        n64_form = QFormLayout(n64_group)
        for suffix, label in (
            ("DisableVideoInterfaceProcessing", "Disable Video Interface Processing"),
            ("WeaveDeinterlacing", "Weave Deinterlacing"),
            ("Supersampling", "Supersampling"),
        ):
            key = self._n64_key(suffix)
            n64_form.addRow(self._check(key, label))
        self.quality_group = QButtonGroup(self)
        quality_row = QWidget()
        quality_layout = QHBoxLayout(quality_row)
        quality_layout.setContentsMargins(0, 0, 0, 0)
        for value, label in self.QUALITY_VALUES:
            button = QRadioButton(label)
            self.quality_group.addButton(button)
            self.quality_buttons[value] = button
            quality_layout.addWidget(button)
        quality_layout.addStretch(1)
        n64_form.addRow("Resolução interna:", quality_row)
        hint = QLabel("As opções de renderização do N64 exigem recarregar o jogo.")
        hint.setWordWrap(True)
        n64_form.addRow("", hint)
        layout.addWidget(n64_group)

        menus_group = QGroupBox("Menus de vídeo")
        menus_layout = QHBoxLayout(menus_group)
        self.window_button = self._menu_button("Window Size")
        self.output_button = self._menu_button("Output")
        self.window_menu = QMenu(self.window_button)
        self.output_menu = QMenu(self.output_button)
        self.window_button.setMenu(self.window_menu)
        self.output_button.setMenu(self.output_menu)
        self._build_window_menu()
        self._build_output_menu()
        menus_layout.addWidget(self.window_button)
        menus_layout.addWidget(self.output_button)
        menus_layout.addStretch(1)
        layout.addWidget(menus_group)

        layout.addStretch(1)
        scroll.setWidget(content)
        video_layout.addWidget(scroll, 1)
        self.status = QLabel()
        video_layout.addWidget(self.status)
        actions = QHBoxLayout()
        actions.addStretch(1)
        reload_button = QPushButton("Recarregar")
        reload_button.clicked.connect(self.refresh)
        save_button = QPushButton("Salvar configurações")
        save_button.setProperty("role", "primary")
        save_button.clicked.connect(self.save)
        actions.addWidget(reload_button)
        actions.addWidget(save_button)
        video_layout.addLayout(actions)
        self.tabs.addTab(video_page, "Vídeo")

        shader_page = QWidget()
        shader_layout = QVBoxLayout(shader_page)
        shader_layout.addWidget(QLabel("Presets .slangp instalados na pasta Shaders do ares."))
        self.shader_button = self._menu_button("Selecionar shader")
        self.shader_menu = QMenu(self.shader_button)
        self.shader_button.setMenu(self.shader_menu)
        self.shader_menu.aboutToShow.connect(self._populate_shader_menu)
        shader_layout.addWidget(self.shader_button, 0, Qt.AlignmentFlag.AlignLeft)
        shader_layout.addStretch(1)
        self.tabs.addTab(shader_page, "Shaders")

        bezel_page = QWidget()
        bezel_layout = QVBoxLayout(bezel_page)
        bezel_note = QLabel(
            "O ares não oferece uma configuração nativa de bezels. Use shaders/presets ou os recursos do frontend para molduras."
        )
        bezel_note.setWordWrap(True)
        bezel_layout.addWidget(bezel_note)
        bezel_layout.addStretch(1)
        self.tabs.addTab(bezel_page, "Bezels")

    @staticmethod
    def _menu_button(text: str) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        return button

    def _add_slider(
        self,
        form: QFormLayout,
        key: str,
        title: str,
        minimum: int,
        maximum: int,
        display_offset: int,
    ) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        value = QLabel()
        value.setMinimumWidth(48)
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        slider.valueChanged.connect(
            lambda position, target=value, offset=display_offset: target.setText(
                f"{position + offset}%"
            )
        )
        row_layout.addWidget(slider, 1)
        row_layout.addWidget(value)
        form.addRow(title, row)
        self.sliders[key] = (slider, value, display_offset)

    def _check(self, key: str, label: str) -> QCheckBox:
        checkbox = QCheckBox(label)
        self.checks[key] = checkbox
        return checkbox

    def _n64_key(self, suffix: str) -> str:
        editor = self._editor()
        for section in ("Video", "Nintendo64"):
            key = f"{section}.{suffix}"
            if editor is not None and editor.values(key):
                return key
        return f"Video.{suffix}"

    @staticmethod
    def _quality_key(editor: ConfigFileEditor) -> str:
        for section in ("Video", "Nintendo64"):
            key = f"{section}.Quality"
            if editor.values(key):
                return key
        return "Video.Quality"

    def _build_window_menu(self) -> None:
        for label, width, height in self.WINDOW_SIZES:
            action = self.window_menu.addAction(label)
            action.triggered.connect(
                lambda _checked=False, w=width, h=height: self._queue_updates(
                    {"Video.WindowWidth": str(w), "Video.WindowHeight": str(h)}
                )
            )
        self.window_menu.addSeparator()
        custom = self.window_menu.addAction("Custom…")
        custom.triggered.connect(self._custom_window_size)
        self.window_menu.addSeparator()
        center = self.window_menu.addAction("Center Window")
        center.setCheckable(True)
        center.triggered.connect(lambda checked: self._queue_bool("Video.AutoCentering", checked))
        self.center_action = center

    def _build_output_menu(self) -> None:
        scale = self.output_menu.addMenu("Scale")
        self.scale_actions: list[tuple[QAction, str, str | None]] = []
        options = (
            ("Best Fit", "Scale", None),
            ("Integer (auto)", "Integer", None),
            *((f"Integer (fixed {factor}x)", "Fixed", str(factor)) for factor in range(1, 8)),
            ("Stretch to Fill", "Stretch", None),
        )
        for label, output, factor in options:
            action = scale.addAction(label)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, out=output, fixed=factor: self._choose_scale(out, fixed)
            )
            self.scale_actions.append((action, output, factor))
        aspect = self.output_menu.addMenu("Aspect")
        self.aspect_actions: list[tuple[QAction, str]] = []
        for label, value in (
            ("No correction", "None"),
            ("Standard", "Standard"),
            ("Anamorphic (16:9)", "Anamorphic"),
        ):
            action = aspect.addAction(label)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, mode=value: self._choose_aspect(mode))
            self.aspect_actions.append((action, value))
        window = self.output_menu.addMenu("Window")
        adaptive = window.addAction("Auto resize to content aspect")
        adaptive.setCheckable(True)
        adaptive.triggered.connect(
            lambda checked: self._queue_bool("Video.AdaptiveSizing", checked)
        )
        self.adaptive_action = adaptive
        auto_center = window.addAction("Auto center")
        auto_center.setCheckable(True)
        auto_center.triggered.connect(
            lambda checked: self._queue_bool("Video.AutoCentering", checked)
        )
        self.auto_center_action = auto_center

    def _custom_window_size(self) -> None:
        editor = self._editor()
        if editor is None:
            return
        width = self._integer(editor, "Video.WindowWidth", 800)
        height = self._integer(editor, "Video.WindowHeight", 576)
        dialog = QDialog(self)
        dialog.setWindowTitle("Custom window size")
        form = QFormLayout(dialog)
        width_spin = QSpinBox()
        width_spin.setRange(320, 16384)
        width_spin.setValue(width)
        height_spin = QSpinBox()
        height_spin.setRange(240, 16384)
        height_spin.setValue(height)
        form.addRow("Width:", width_spin)
        form.addRow("Height:", height_spin)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._queue_updates(
                {
                    "Video.WindowWidth": str(width_spin.value()),
                    "Video.WindowHeight": str(height_spin.value()),
                }
            )

    def _choose_scale(self, output: str, fixed_scale: str | None) -> None:
        updates = {"Video.Output": output}
        if fixed_scale is not None:
            updates["Video.FixedScale"] = fixed_scale
        self._queue_updates(updates)

    def _choose_aspect(self, mode: str) -> None:
        self._queue_updates({"Video.AspectCorrectionMode": mode})

    def _queue_bool(self, key: str, value: bool) -> None:
        editor = self._editor()
        if editor is None:
            return
        values = editor.values(key)
        self._queue_updates({key: self._bool_value(value, values[0] if values else "false")})

    def _queue_updates(self, updates: dict[str, str]) -> None:
        editor = self._editor()
        if editor is None:
            QMessageBox.warning(self, "ares", "Configure o settings.bml em Diretórios primeiro.")
            return
        missing = [key for key in updates if not editor.values(key)]
        if missing:
            QMessageBox.warning(
                self,
                "Opção indisponível",
                "O settings.bml não contém estas opções: " + ", ".join(missing),
            )
            self.refresh()
            return
        pending_checks = {key: checkbox.isChecked() for key, checkbox in self.checks.items()}
        pending_sliders = {
            key: slider.value() for key, (slider, _label, _offset) in self.sliders.items()
        }
        try:
            for key, value in updates.items():
                editor.set_value(key, value)
            editor.save()
        except (OSError, KeyError, ValueError) as exc:
            QMessageBox.critical(self, "Falha ao salvar", str(exc))
            return
        self.refresh()
        for key, checked in pending_checks.items():
            checkbox = self.checks[key]
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.blockSignals(False)
        for key, position in pending_sliders.items():
            self.sliders[key][0].setValue(position)

    def _populate_shader_menu(self) -> None:
        self.shader_menu.clear()
        none = self.shader_menu.addAction("None")
        none.triggered.connect(lambda: self._queue_updates({"Video.Shader": "None"}))
        self.shader_menu.addSeparator()
        paths = self._paths()
        root = Path(paths.get("ares_shaders", "")) if paths.get("ares_shaders") else None
        if root is None or not root.is_dir():
            install = Path(paths.get("ares", "")) if paths.get("ares") else None
            root = install / "Shaders" if install else None
        presets: list[Path] = []
        if root is not None and root.is_dir():
            try:
                presets = sorted(
                    (
                        path
                        for path in root.rglob("*.slangp")
                        if not any(part.startswith(".") for part in path.relative_to(root).parts)
                    ),
                    key=lambda path: path.relative_to(root).as_posix().casefold(),
                )
            except OSError:
                presets = []
        if not presets or root is None:
            unavailable = self.shader_menu.addAction(
                "No .slangp presets found in the ares Shaders folder"
            )
            unavailable.setEnabled(False)
            return
        tree: dict[str, object] = {}
        for preset in presets:
            relative = preset.relative_to(root)
            node: dict[str, object] = tree
            for part in relative.parts[:-1]:
                child = node.setdefault(part, {})
                if not isinstance(child, dict):
                    child = {}
                    node[part] = child
                node = child
            node[relative.name] = relative.as_posix()
        current = self._read_value("Video.Shader", "None")
        matched = False

        def add_nodes(menu: QMenu, nodes: dict[str, object], prefix: tuple[str, ...] = ()) -> None:
            nonlocal matched
            folders = sorted(
                (key for key, value in nodes.items() if isinstance(value, dict)), key=str.casefold
            )
            files = sorted(
                (key for key, value in nodes.items() if isinstance(value, str)), key=str.casefold
            )
            for folder in folders:
                submenu = menu.addMenu(folder)
                add_nodes(submenu, nodes[folder], (*prefix, folder))  # type: ignore[arg-type]
            for filename in files:
                relative = str(nodes[filename])
                name = Path(filename).stem
                action = menu.addAction(name)
                action.setToolTip(relative)
                if relative.casefold() == current.replace("\\", "/").casefold():
                    action.setCheckable(True)
                    action.setChecked(True)
                    matched = True
                action.triggered.connect(
                    lambda _checked=False, shader=relative: self._queue_updates(
                        {"Video.Shader": shader}
                    )
                )

        add_nodes(self.shader_menu, tree)
        if current != "None" and not matched:
            self.shader_menu.addSeparator()
            existing = self.shader_menu.addAction(
                f"Current shader (missing from folder): {current}"
            )
            existing.setEnabled(False)

    @staticmethod
    def _integer(editor: ConfigFileEditor, key: str, default: int) -> int:
        try:
            return int(editor.values(key)[0])
        except (IndexError, ValueError):
            return default

    @staticmethod
    def _parse_bool(value: str) -> bool:
        return value.strip().casefold() in {"true", "yes", "1", "on"}

    @staticmethod
    def _bool_value(value: bool, original: str) -> str:
        if original.strip().casefold() in {"true", "false"}:
            return "true" if value else "false"
        if original.strip().casefold() in {"yes", "no"}:
            return "yes" if value else "no"
        return "1" if value else "0"

    def _editor(self) -> ConfigFileEditor | None:
        config = self._paths().get("ares_config")
        path = Path(config).expanduser() if config else None
        if path is None or not path.is_file():
            return None
        try:
            return ConfigFileEditor(path)
        except (OSError, UnicodeError):
            return None

    def _read_value(self, key: str, default: str = "") -> str:
        editor = self._editor()
        if editor is None:
            return default
        values = editor.values(key)
        return values[0] if values else default

    @staticmethod
    def _decimal(value: float) -> str:
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def refresh(self) -> None:
        editor = self._editor()
        if editor is None:
            self.status.setText("settings.bml não configurado / não encontrado")
            for checkbox in self.checks.values():
                checkbox.setEnabled(False)
            for slider, _label, _offset in self.sliders.values():
                slider.setEnabled(False)
            for button in self.quality_buttons.values():
                button.setEnabled(False)
            return
        self.status.setText(f"Arquivo: {editor.path}")
        for key, checkbox in self.checks.items():
            values = editor.values(key)
            checkbox.setEnabled(bool(values))
            if values:
                checkbox.blockSignals(True)
                checkbox.setChecked(self._parse_bool(values[0]))
                checkbox.blockSignals(False)
                self.check_initial[key] = checkbox.isChecked()
        for key, (slider, label, offset) in self.sliders.items():
            values = editor.values(key)
            slider.setEnabled(bool(values))
            if not values:
                continue
            try:
                raw = float(values[0]) * 100
                position = round(raw - 100) if key == "Video.Gamma" else round(raw)
                slider.blockSignals(True)
                slider.setValue(max(slider.minimum(), min(slider.maximum(), position)))
                slider.blockSignals(False)
                shown = slider.value() + offset
                label.setText(f"{shown}%")
            except ValueError:
                pass
        quality_key = self._quality_key(editor)
        quality = self._read_value(quality_key, "SD")
        for value, button in self.quality_buttons.items():
            button.setEnabled(bool(editor.values(quality_key)))
            button.blockSignals(True)
            button.setChecked(quality == value)
            button.blockSignals(False)
        self.center_action.setChecked(
            self._parse_bool(self._read_value("Video.AutoCentering", "false"))
        )
        self.adaptive_action.setChecked(
            self._parse_bool(self._read_value("Video.AdaptiveSizing", "false"))
        )
        self.auto_center_action.setChecked(self.center_action.isChecked())
        self._refresh_menu_labels()

    def _refresh_menu_labels(self) -> None:
        width = self._read_value("Video.WindowWidth", "800")
        height = self._read_value("Video.WindowHeight", "576")
        preset = next(
            (label for label, w, h in self.WINDOW_SIZES if str(w) == width and str(h) == height),
            None,
        )
        self.window_button.setText(f"Window Size: {preset or f'{width}×{height}'}")
        output = self._read_value("Video.Output", "Scale")
        fixed = self._read_value("Video.FixedScale", "2")
        output_label = {
            "Scale": "Best Fit",
            "Integer": "Integer (auto)",
            "Fixed": f"Integer (fixed {fixed}x)",
            "Stretch": "Stretch to Fill",
        }.get(output, output)
        self.output_button.setText(f"Output: {output_label}")
        mode = self._read_value("Video.AspectCorrectionMode", "Standard")
        if mode != "Standard":
            self.output_button.setToolTip(f"Aspect: {mode}")
        else:
            self.output_button.setToolTip("")
        shader = self._read_value("Video.Shader", "None")
        self.shader_button.setText(f"Shader: {Path(shader).stem if shader != 'None' else 'None'}")
        for action, value, factor in self.scale_actions:
            action.setChecked(output == value and (factor is None or fixed == factor))
        for action, value in self.aspect_actions:
            action.setChecked(mode == value)

    def save(self) -> None:
        editor = self._editor()
        if editor is None:
            QMessageBox.warning(self, "ares", "Configure o settings.bml em Diretórios primeiro.")
            return
        updates: dict[str, str] = {}
        for key, checkbox in self.checks.items():
            values = editor.values(key)
            if values and checkbox.isChecked() != self.check_initial.get(key, checkbox.isChecked()):
                updates[key] = self._bool_value(checkbox.isChecked(), values[0])
        for key, (slider, _label, _offset) in self.sliders.items():
            values = editor.values(key)
            if not values:
                continue
            raw = float(values[0])
            original_position = round(raw * 100)
            if key == "Video.Gamma":
                original_position -= 100
            if slider.value() == original_position:
                continue
            if key == "Video.Luminance":
                number = slider.value() / 100
            elif key == "Video.Saturation":
                number = slider.value() / 100
            else:
                number = 1 + slider.value() / 100
            updates[key] = self._decimal(number)
        quality_key = self._quality_key(editor)
        for value, button in self.quality_buttons.items():
            if button.isChecked() and value != self._read_value(quality_key, "SD"):
                updates[quality_key] = value
        if not updates:
            QMessageBox.information(self, "ares", "Nenhuma alteração pendente.")
            return
        missing = [key for key in updates if not editor.values(key)]
        if missing:
            QMessageBox.warning(
                self, "Opção indisponível", "Ausente no settings.bml: " + ", ".join(missing)
            )
            return
        try:
            for key, value in updates.items():
                editor.set_value(key, value)
            backup = editor.save()
        except (OSError, KeyError, ValueError) as exc:
            QMessageBox.critical(self, "Falha ao salvar", str(exc))
            return
        self.refresh()
        QMessageBox.information(
            self, "ares", f"{len(updates)} opção(ões) salva(s).\nBackup:\n{backup}"
        )


__all__ = ["AresSettingsPage"]
