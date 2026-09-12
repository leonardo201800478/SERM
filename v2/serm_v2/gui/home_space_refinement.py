"""Correções de composição espacial da Home V2."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPlainTextEdit, QProgressBar, QSizePolicy, QVBoxLayout, QWidget


LOG_LABELS = {"Log detalhado da instalação", "Log RetroArch"}


def _detach(layout, widget: QWidget) -> None:
    """Remove um widget do layout sem destruir seu contrato Python."""
    if layout is not None and layout.indexOf(widget) >= 0:
        layout.removeWidget(widget)
    widget.hide()
    widget.setMinimumHeight(0)
    widget.setMaximumHeight(0)


def compact_home_space(home) -> bool:
    """Remove itens ocultos que ainda reservavam espaço e prioriza conteúdo útil."""
    tabs = getattr(home, "home_tabs", None)
    if tabs is None or tabs.count() == 0:
        return False

    for index in range(tabs.count()):
        page = tabs.widget(index)
        if page is None:
            continue
        layout = page.layout()
        if not isinstance(layout, QVBoxLayout):
            continue

        for widget in page.findChildren(QPlainTextEdit):
            _detach(layout, widget)
        for label in page.findChildren(QLabel):
            if label.text().strip() in LOG_LABELS:
                _detach(layout, label)

        layout.setSpacing(5)
        layout.setContentsMargins(4, 4, 4, 4)

    core_list = getattr(home, "core_list", None)
    if core_list is not None:
        core_list.setMinimumHeight(0)
        policy = core_list.sizePolicy()
        policy.setVerticalPolicy(QSizePolicy.Policy.Expanding)
        core_list.setSizePolicy(policy)

    dock = getattr(home.window(), "log_dock", None)
    if dock is not None:
        dock.setMinimumHeight(68)
        dock.setMaximumHeight(112)

    progress = getattr(home, "home_progress", None)
    if isinstance(progress, QProgressBar):
        progress.setTextVisible(False)
        progress.setFixedHeight(9)
        progress.setStyleSheet(
            "QProgressBar#xpProgress{background:#0b1220;border:1px solid #2a3b55;"
            "border-radius:5px;padding:0;}"
            "QProgressBar#xpProgress::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #4ca8ff,stop:0.5 #55d6c2,stop:1 #7aa7ff);border-radius:4px;}"
        )

    return True


__all__ = ["compact_home_space"]
