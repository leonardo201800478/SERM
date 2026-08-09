from PyQt6.QtWidgets import QWidget, QVBoxLayout
from .filters_panel import FiltersPanel

class FiltersTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        layout = QVBoxLayout(self)
        self.filters_panel = FiltersPanel(parent=self.main_window)
        layout.addWidget(self.filters_panel)
        self.filters_panel.profile_changed.connect(self.main_window.apply_profile)

    def update_count(self, count: int):
        self.filters_panel.update_count(count)