"""Dashboard contextual e compacto para a Home do SERM V2."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout


STATUS_KEYS = ("mame", "flycast", "supermodel", "fbneo")


def _label(text: str, object_name: str = "") -> QLabel:
    label = QLabel(text)
    if object_name:
        label.setObjectName(object_name)
    return label


def _status_card(title: str) -> tuple[QFrame, QLabel]:
    card = QFrame()
    card.setObjectName("homeStatusCard")
    card.setMinimumHeight(46)
    card.setMaximumHeight(58)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(8, 6, 8, 6)
    layout.setSpacing(1)
    name = _label(title, "homeStatusTitle")
    state = _label("● verificando", "homeStatusState")
    layout.addWidget(name)
    layout.addWidget(state)
    return card, state


def refine_home_dashboard(home) -> bool:
    """Adiciona estado dos emuladores, operação contextual e métricas do catálogo."""
    root = home.layout()
    tabs = getattr(home, "home_tabs", None)
    if not isinstance(root, QVBoxLayout) or tabs is None:
        return False
    if home.findChild(QFrame, "homeDashboard") is not None:
        return True

    dashboard = QFrame()
    dashboard.setObjectName("homeDashboard")
    dash_layout = QHBoxLayout(dashboard)
    dash_layout.setContentsMargins(6, 5, 6, 5)
    dash_layout.setSpacing(6)

    home._dashboard_states = {}
    labels = getattr(home, "LABELS", {})
    for key in STATUS_KEYS:
        card, state = _status_card(labels.get(key, key.title()))
        home._dashboard_states[key] = state
        dash_layout.addWidget(card, 1)

    retro_card, retro_state = _status_card("RetroArch")
    home._dashboard_states["retroarch"] = retro_state
    dash_layout.addWidget(retro_card, 1)
    root.insertWidget(max(1, root.indexOf(tabs)), dashboard)

    operation = QFrame()
    operation.setObjectName("homeOperation")
    operation_layout = QVBoxLayout(operation)
    operation_layout.setContentsMargins(8, 5, 8, 5)
    operation_layout.setSpacing(2)
    operation_header = QHBoxLayout()
    operation_header.setSpacing(8)
    home._operation_title = _label("● Nenhuma operação em andamento", "homeOperationTitle")
    home._operation_detail = _label("Pronto para executar", "homeOperationDetail")
    home._operation_detail.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    operation_header.addWidget(home._operation_title)
    operation_header.addWidget(home._operation_detail, 1)
    operation_layout.addLayout(operation_header)
    home._operation_progress = QProgressBar()
    home._operation_progress.setObjectName("homeOperationProgress")
    home._operation_progress.setTextVisible(False)
    home._operation_progress.setFixedHeight(7)
    home._operation_progress.hide()
    operation_layout.addWidget(home._operation_progress)
    root.addWidget(operation)
    operation.hide()
    home._home_operation = operation

    retro_tab = tabs.widget(1) if tabs.count() > 1 else None
    if retro_tab is not None:
        if retro_tab.findChild(QFrame, "homeCatalogMetrics") is None:
            metrics = QFrame()
            metrics.setObjectName("homeCatalogMetrics")
            metrics_layout = QHBoxLayout(metrics)
            metrics_layout.setContentsMargins(8, 3, 8, 3)
            metrics_layout.setSpacing(12)
            home._catalog_total = _label("0 catálogo", "homeMetric")
            home._catalog_visible = _label("0 visíveis", "homeMetric")
            home._catalog_installed = _label("0 instalados", "homeMetric")
            home._catalog_updates = _label("0 atualizações", "homeMetric")
            for metric in (home._catalog_total, home._catalog_visible, home._catalog_installed, home._catalog_updates):
                metrics_layout.addWidget(metric)
            metrics_layout.addStretch()
            retro_layout = retro_tab.layout()
            if isinstance(retro_layout, QVBoxLayout):
                list_widget = getattr(home, "core_list", None)
                position = retro_layout.indexOf(list_widget) if list_widget is not None else -1
                if position >= 0:
                    retro_layout.insertWidget(position, metrics)
                else:
                    retro_layout.addWidget(metrics)

    _apply_dashboard_style(home)

    timer = QTimer(home)
    timer.setInterval(1000)
    timer.timeout.connect(lambda: _refresh_dashboard(home))
    timer.start()
    home._dashboard_timer = timer
    _refresh_dashboard(home)
    return True


def _apply_dashboard_style(home) -> None:
    dashboard = home.findChild(QFrame, "homeDashboard")
    operation = home.findChild(QFrame, "homeOperation")
    if dashboard is not None:
        dashboard.setStyleSheet(
            "QFrame#homeDashboard{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #111b2c,stop:1 #0e1726);border:1px solid #2b3d58;border-radius:10px;}"
            "QFrame#homeStatusCard{background:rgba(255,255,255,0.025);border:1px solid #293b55;border-radius:7px;}"
            "QLabel#homeStatusTitle{color:#dbe7f4;font-size:9pt;font-weight:600;}"
            "QLabel#homeStatusState{color:#8fa5bb;font-size:8pt;}"
        )
    if operation is not None:
        operation.setStyleSheet(
            "QFrame#homeOperation{background:#0d1625;border:1px solid #293b55;border-radius:8px;}"
            "QLabel#homeOperationTitle{color:#dbe7f4;font-size:8pt;font-weight:600;}"
            "QLabel#homeOperationDetail{color:#8fa5bb;font-size:8pt;}"
            "QProgressBar#homeOperationProgress{background:#09111d;border:0;border-radius:4px;padding:0;}"
            "QProgressBar#homeOperationProgress::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #4ca8ff,stop:0.55 #55d6c2,stop:1 #7aa7ff);border-radius:4px;}"
        )
    for metric in home.findChildren(QLabel, "homeMetric"):
        metric.setStyleSheet("color:#9eb2c7;font-size:8pt;")


def _refresh_dashboard(home) -> None:
    """Atualiza o dashboard e o painel de operação."""
    states = getattr(home, "_dashboard_states", {})
    manager = getattr(home, "manager", None)
    if manager is not None:
        try:
            discovered = manager.discover()
            for key in STATUS_KEYS:
                state = discovered.get(key)
                label = states.get(key)
                if state is None or label is None:
                    continue
                if state.state == "ready":
                    label.setText("● Pronto")
                    label.setStyleSheet("color:#76d69a;font-size:8pt;")
                elif state.state == "configured":
                    label.setText("● Diretório configurado")
                    label.setStyleSheet("color:#e4c978;font-size:8pt;")
                else:
                    label.setText("● Não configurado")
                    label.setStyleSheet("color:#a4b1bf;font-size:8pt;")
        except Exception:  # noqa: BLE001
            pass

    retro_state = states.get("retroarch")
    retro = getattr(home, "retroarch", None)
    if retro_state is not None and retro is not None:
        try:
            executable, _, _ = retro.discover()
            retro_state.setText("● Pronto" if executable else "● Não configurado")
            retro_state.setStyleSheet(
                "color:#76d69a;font-size:8pt;" if executable else "color:#a4b1bf;font-size:8pt;"
            )
        except Exception:  # noqa: BLE001
            pass

    worker = getattr(home, "worker", None)
    progress = getattr(home, "retro_progress", None)
    operation = getattr(home, "_home_operation", None)
    operation_progress = getattr(home, "_operation_progress", None)
    title = getattr(home, "_operation_title", None)
    detail = getattr(home, "_operation_detail", None)
    if worker is not None:
        filename = getattr(home, "_core_current_filename", None)
        queue = getattr(home, "_core_queue_with_channels", [])
        title.setText(f"● Instalando {filename}" if filename else "● Operação em andamento")
        detail.setText(f"{len(queue)} na fila" if filename else "processando")
        operation.show()
        operation_progress.show()
        if progress is not None and progress.maximum() > 0:
            operation_progress.setRange(0, progress.maximum())
            operation_progress.setValue(progress.value())
        else:
            operation_progress.setRange(0, 0)
    else:
        title.setText("● Nenhuma operação em andamento")
        detail.setText("Pronto para executar")
        operation_progress.hide()
        operation.hide()

    cache = getattr(home, "_core_catalog_cache", None)
    if cache is None or not hasattr(home, "_catalog_total"):
        return
    try:
        total = len(cache)
        filtered = home._filtered_cached_cores()
        visible = len(filtered)
        _, _, destination = home.retroarch.discover()
        comparisons = (
            home.retroarch.compare_installed_cores(filtered, destination)
            if destination and destination.is_dir()
            else []
        )
        installed = len(comparisons)
        updates = sum(state == "update" for _, _, state in comparisons)
        home._catalog_total.setText(f"{total} catálogo")
        home._catalog_visible.setText(f"{visible} visíveis")
        home._catalog_installed.setText(f"{installed} instalados")
        home._catalog_updates.setText(f"{updates} atualizações")
    except Exception:  # noqa: BLE001
        pass


__all__ = ["refine_home_dashboard"]
