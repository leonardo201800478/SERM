"""Biblioteca visual do MAME integrada ao catálogo SERM V2."""

from __future__ import annotations

import json
import sqlite3
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QPushButton,
)

from ..runtime.paths import data_root, database_path
from ..services.mame_artwork_service import MameArtworkService
from .components.mame_game_grid import MameGameGrid


@dataclass(frozen=True, slots=True)
class MameVisualGame:
    """Metadados mínimos do ListXML usados pela apresentação visual."""

    short_name: str
    name: str
    title: str
    parent: str | None = None
    year: str | None = None
    manufacturer: str | None = None
    players: int | None = None
    buttons: int | None = None
    orientation: str = "Horizontal"
    category: str = "Arcade"
    subcategory: str = "MAME"


class MameVisualLibraryPage(QWidget):
    """Biblioteca em cards usando exclusivamente o artwork local do MAME."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._games: list[MameVisualGame] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("BIBLIOTECA MAME")
        title.setProperty("role", "title")
        root.addWidget(title)

        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Pesquisar jogo, machine, fabricante ou ano…")
        self.search.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.search, 1)
        self.sort = QComboBox()
        self.sort.addItems(["Nome", "Machine", "Ano"])
        self.sort.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self.sort)
        refresh = QPushButton("ATUALIZAR CATÁLOGO")
        refresh.clicked.connect(self.refresh)
        toolbar.addWidget(refresh)
        root.addLayout(toolbar)

        self.summary = QLabel("Carregando catálogo…")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.grid = MameGameGrid(parent=self)
        self.grid.game_activated.connect(self._show_game)
        splitter.addWidget(self.grid)
        splitter.setStretchFactor(0, 1)

        self.details = self._details_panel()
        splitter.addWidget(self.details)
        splitter.setSizes([850, 360])
        root.addWidget(splitter, 1)

    def _details_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        info_box = QGroupBox("Detalhes da machine")
        form = QFormLayout(info_box)
        self.detail_title = QLabel("Selecione um jogo")
        self.detail_title.setWordWrap(True)
        self.detail_machine = QLabel("—")
        self.detail_parent = QLabel("—")
        self.detail_meta = QLabel("—")
        self.detail_meta.setWordWrap(True)
        form.addRow("Jogo:", self.detail_title)
        form.addRow("Machine:", self.detail_machine)
        form.addRow("Parent:", self.detail_parent)
        form.addRow("Metadados:", self.detail_meta)
        layout.addWidget(info_box)

        artwork_box = QGroupBox("Artwork disponível")
        artwork_layout = QVBoxLayout(artwork_box)
        self.artwork_list = QListWidget()
        self.artwork_list.currentItemChanged.connect(self._show_artwork)
        artwork_layout.addWidget(self.artwork_list)
        self.preview = QLabel("Selecione uma arte")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(180)
        self.preview.setWordWrap(True)
        artwork_layout.addWidget(self.preview)
        layout.addWidget(artwork_box, 1)
        return panel

    def refresh(self) -> None:
        try:
            self._games = self._load_latest_catalog()
        except (OSError, sqlite3.Error, ET.ParseError, ValueError) as exc:
            self._games = []
            self.summary.setText(f"Não foi possível carregar o catálogo MAME: {exc}")
            self.grid.set_games([])
            return

        executable = self._mame_executable()
        if executable:
            self.grid.set_mame_executable(executable)
        self._apply_filter()
        if self._games:
            self.summary.setText(
                f"{len(self._games):,} machines carregadas. "
                "Os cards usam Snap → Title → Flyer → Marquee → Cabinet → Artwork como prioridade visual."
            )
        else:
            self.summary.setText(
                "Nenhum ListXML concluído foi encontrado. Importe um catálogo em MAME Studio → Catálogo."
            )

    def _load_latest_catalog(self) -> list[MameVisualGame]:
        db_path = database_path()
        if not db_path.is_file():
            return []
        with sqlite3.connect(db_path) as db:
            row = db.execute(
                """SELECT d.xml_text
                   FROM mame_listxml_import i
                   JOIN mame_listxml_document d ON d.import_id=i.id
                   WHERE i.status='completed'
                   ORDER BY i.id DESC LIMIT 1"""
            ).fetchone()
        if not row or not row[0]:
            return []
        root = ET.fromstring(str(row[0]))
        games: list[MameVisualGame] = []
        for machine in root.findall("machine"):
            short_name = str(machine.get("name") or "").strip()
            if not short_name:
                continue
            description = (machine.findtext("description") or short_name).strip()
            manufacturer = self._text(machine.findtext("manufacturer"))
            year = self._text(machine.findtext("year"))
            parent = self._text(machine.get("cloneof"))
            input_node = machine.find("input")
            players = self._int(input_node.get("players")) if input_node is not None else None
            buttons = self._int(input_node.get("buttons")) if input_node is not None else None
            display = machine.find("display")
            rotate = self._text(display.get("rotate")) if display is not None else None
            orientation = self._orientation(rotate)
            games.append(MameVisualGame(
                short_name=short_name,
                name=description,
                title=description,
                parent=parent,
                year=year,
                manufacturer=manufacturer,
                players=players,
                buttons=buttons,
                orientation=orientation,
            ))
        return games

    @staticmethod
    def _mame_executable() -> Path | None:
        path = data_root() / "emulator_paths.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, ValueError, TypeError):
            return None
        raw = data.get("mame_executable") if isinstance(data, dict) else None
        if not raw:
            return None
        executable = Path(str(raw)).expanduser()
        return executable if executable.is_file() else None

    def _apply_filter(self) -> None:
        query = self.search.text().strip().casefold()
        games = [
            game for game in self._games
            if not query or query in " ".join((game.short_name, game.name, game.manufacturer or "", game.year or "")).casefold()
        ]
        key = self.sort.currentText()
        if key == "Machine":
            games.sort(key=lambda item: item.short_name.casefold())
        elif key == "Ano":
            games.sort(key=lambda item: (item.year or "9999", item.name.casefold()))
        else:
            games.sort(key=lambda item: item.name.casefold())
        self.grid.set_games(games)
        if query:
            self.summary.setText(f"{len(games):,} resultado(s) para “{self.search.text().strip()}”.")

    def _show_game(self, game: MameVisualGame) -> None:
        self.detail_title.setText(game.title)
        self.detail_machine.setText(game.short_name)
        self.detail_parent.setText(game.parent or "Parent / SET próprio")
        self.detail_meta.setText(
            f"{game.year or 'Ano —'} · {game.manufacturer or 'Fabricante —'} · "
            f"{game.players or '—'} jogador(es) · {game.buttons or '—'} botão(ões) · {game.orientation}"
        )
        inventory = self.grid.artwork_inventory(game)
        self.artwork_list.blockSignals(True)
        self.artwork_list.clear()
        for kind, path in inventory.items():
            item = QListWidgetItem(f"{kind.upper()}  ·  {path.name}")
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.artwork_list.addItem(item)
        self.artwork_list.blockSignals(False)
        if self.artwork_list.count():
            self.artwork_list.setCurrentRow(0)
        else:
            self.preview.setText("Nenhuma arte local encontrada para esta machine.")
            self.preview.setPixmap(QPixmap())

    def _show_artwork(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        path = Path(str(current.data(Qt.ItemDataRole.UserRole) or ""))
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.preview.setText(str(path))
            return
        self.preview.setText("")
        self.preview.setPixmap(
            pixmap.scaled(
                330,
                230,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    @staticmethod
    def _text(value: object) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _int(value: object) -> int | None:
        try:
            return int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _orientation(rotate: str | None) -> str:
        if str(rotate or "").strip() in {"90", "270"}:
            return "Vertical"
        return "Horizontal"


__all__ = ["MameVisualGame", "MameVisualLibraryPage"]
