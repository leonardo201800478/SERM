from __future__ import annotations

from pathlib import Path

import pytest


# The default suite is deliberately limited to deterministic, local tests.
# Dataset/live audits remain available through ``pytest --extended``.
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
