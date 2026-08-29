"""No-Intro-aware Home extension for V2."""
from __future__ import annotations

import hashlib
import logging

from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from ..sources.no_intro.catalog import NoIntroSystem
from ..sources.no_intro.downloader import NoIntroDownload
from ..sources.no_intro.update_manager import NoIntroUpdateManager
from .home import HomePage

logger = logging.getLogger(__name__)


class NoIntroHomePage(HomePage):
    """Extend the base Home with local No-Intro freshness management."""

    def __init__(self, parent=None) -> None:
        self.no_intro_update_manager = NoIntroUpdateManager()
        self.no_intro_freshness: tuple = ()
        super().__init__(parent)

    def _create_no_intro_card(self):
        """Add the dedicated update-only action to the existing No-Intro card."""
        card = super()._create_no_intro_card()
        row = card.layout().itemAt(card.layout().count() - 1).layout()
        update = QPushButton("🔄 Atualizar desatualizados")
        update.clicked.connect(self.update_outdated_no_intro)
        row.addWidget(update)
        self.no_intro_update_button = update
        return card

    def test_no_intro_catalog(self) -> None:
        """Run the normal catalog match and immediately inspect local freshness."""
        super().test_no_intro_catalog()
        self._refresh_freshness()

    def download_selected_no_intro(self) -> None:
        """Run the standard selected download and register its catalog revision."""
        super().download_selected_no_intro()
        if not self.no_intro_matches:
            return
        system = self.no_intro_matches[self.no_intro_systems.currentIndex()]
        path = self._no_intro_destination(system)
        if path.is_file():
            self._register_file(system, path)
            self._refresh_freshness()

    def download_all_no_intro(self) -> None:
        """Run the standard full download and register successful artifacts."""
        super().download_all_no_intro()
        self._register_existing()
        self._refresh_freshness()

    def update_outdated_no_intro(self) -> None:
        """Download only existing DATs whose catalog revision is older or unknown."""
        candidates = self.no_intro_update_manager.update_candidates(
            self.no_intro_matches,
            self._no_intro_destination,
        )
        if not candidates:
            self.no_intro_status.setText("● Nenhum DAT desatualizado")
            self.no_intro_status.setStyleSheet("color:#55d66b;font-weight:bold;")
            QMessageBox.information(self, "No-Intro", "Nenhum DAT existente precisa de atualização.")
            self.no_intro_update_button.setEnabled(False)
            return

        succeeded = 0
        failed: list[str] = []
        total = len(candidates)
        self.no_intro_test_button.setEnabled(False)
        self._set_no_intro_download_enabled(False)
        self.no_intro_update_button.setEnabled(False)
        try:
            for index, system in enumerate(candidates, start=1):
                self.no_intro_status.setText(f"● Atualizando {index}/{total} — {system.name}")
                QApplication.processEvents()
                destination = self._no_intro_destination(system)
                logger.info(
                    "[NO-INTRO][UPDATE] %d/%d início sistema=%s revisão=%s",
                    index,
                    total,
                    system.name,
                    system.update_text,
                )
                try:
                    result = self.no_intro_downloader.download_system(system.name, destination)
                    self.no_intro_update_manager.record(system, result)
                    succeeded += 1
                    logger.info("[NO-INTRO][UPDATE] %d/%d OK arquivo=%s", index, total, result.path)
                except Exception as exc:
                    failed.append(f"{system.name}: {exc}")
                    logger.exception("[NO-INTRO][UPDATE] %d/%d FALHA sistema=%s", index, total, system.name)

            self._refresh_freshness()
            detail = f"Atualizados: {succeeded}/{total}"
            if failed:
                detail += "\n\nFalhas:\n" + "\n".join(failed[:10])
            QMessageBox.information(self, "No-Intro — atualização", detail)
        finally:
            self.no_intro_test_button.setEnabled(True)
            self._set_no_intro_download_enabled(bool(self.no_intro_matches))
            self._refresh_freshness()

    def _register_existing(self) -> None:
        """Register existing downloaded files using the current catalog revision."""
        for system in self.no_intro_matches:
            path = self._no_intro_destination(system)
            if path.is_file():
                status = self.no_intro_update_manager.inspect(system, path)
                if status.state == "unknown":
                    self._register_file(system, path)
                    logger.info("[NO-INTRO][FRESHNESS] manifesto inicializado: %s", system.name)

    def _register_file(self, system: NoIntroSystem, path) -> None:
        """Create freshness metadata for an existing DAT when its revision is known."""
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.no_intro_update_manager.record(
            system,
            NoIntroDownload(
                system=system.name,
                path=path,
                sha256=digest,
                source_url="",
            ),
        )

    def _refresh_freshness(self) -> None:
        """Refresh freshness counters and expose the update button state."""
        if not self.no_intro_matches:
            self.no_intro_freshness = ()
            if hasattr(self, "no_intro_update_button"):
                self.no_intro_update_button.setEnabled(False)
            return
        self.no_intro_freshness = self.no_intro_update_manager.statuses(
            self.no_intro_matches,
            self._no_intro_destination,
        )
        missing = sum(item.missing for item in self.no_intro_freshness)
        outdated = sum(item.state == "outdated" for item in self.no_intro_freshness)
        unknown = sum(item.state == "unknown" for item in self.no_intro_freshness)
        current = sum(item.state == "current" for item in self.no_intro_freshness)
        self.no_intro_update_button.setEnabled(bool(outdated or unknown))
        self.no_intro_status.setText(
            f"● {len(self.no_intro_matches)} sistemas — atuais: {current} | "
            f"desatualizados: {outdated} | sem controle: {unknown} | ausentes: {missing}"
        )
        self.no_intro_status.setStyleSheet(
            "color:#e5c454;font-weight:bold;" if (outdated or unknown) else "color:#55d66b;font-weight:bold;"
        )
        logger.info(
            "[NO-INTRO][FRESHNESS] atuais=%d desatualizados=%d sem_manifesto=%d ausentes=%d",
            current,
            outdated,
            unknown,
            missing,
        )
