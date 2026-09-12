from __future__ import annotations

from pathlib import Path

import pytest


# The default suite is deliberately limited to deterministic, local tests.
# These patterns are applied by pytest itself during collection so that heavy
# tests are never imported/executed by the normal ``pytest -q`` command.
_EXTENDED_GLOB_PATTERNS = (
    "*_audit.py",
    "*_integrity.py",
    "*_performance.py",
    "*_query_plan.py",
    "*_real_sample.py",
    "*_real_catalog.py",
    "*_inventory.py",
    "*_integration.py",
)
_EXTENDED_DIRECTORIES = {"mame", "sources"}
_EXTENDED_NAME_PARTS = (
    "_audit",
    "_integrity",
    "_performance",
    "_query_plan",
    "_real_sample",
    "_real_catalog",
    "_inventory",
    "_integration",
)

# ``collect_ignore_glob`` is evaluated before test modules are imported.
# Keep this explicit in addition to the collection hook below: it protects
# the fast suite even when a slow test has expensive module-level setup.
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
