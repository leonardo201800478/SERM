from __future__ import annotations

from pathlib import Path

import pytest


_EXTENDED_GLOB_PATTERNS = (
    "*_audit.py", "*_integrity.py", "*_performance.py", "*_query_plan.py",
    "*_real_sample.py", "*_real_catalog.py", "*_inventory.py", "*_integration.py",
    "*_catalog_semantics.py",
)
_EXTENDED_DIRECTORIES = {"mame", "sources"}
_EXTENDED_NAME_PARTS = (
    "_audit", "_integrity", "_performance", "_query_plan", "_real_sample",
    "_real_catalog", "_inventory", "_integration", "_catalog_semantics",
)

collect_ignore_glob = list(_EXTENDED_GLOB_PATTERNS)


def _is_extended(path: Path) -> bool:
    parts = {part.casefold() for part in path.parts}
    if parts & _EXTENDED_DIRECTORIES:
        return True
    name = path.name.casefold()
    return any(part in name for part in _EXTENDED_NAME_PARTS)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--extended",
        action="store_true",
        default=False,
        help="run extended/live/dataset-oriented tests normally excluded from the fast suite",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "extended: dataset, live, integration or diagnostic test excluded from the default fast suite",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--extended"):
        return
    deselected: list[pytest.Item] = []
    selected: list[pytest.Item] = []
    for item in items:
        path = Path(str(item.fspath))
        if _is_extended(path):
            item.add_marker(pytest.mark.extended)
            deselected.append(item)
        else:
            selected.append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected
