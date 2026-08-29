"""Filesystem path policy for SERM V2.

Development and portable/compiled deployments keep operational data in a
`data` directory owned by the V2 application root. The location can be
explicitly overridden with ``SERM_DATA_DIR`` when required by an administrator.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def application_root() -> Path:
    """Return the V2 application root for source and packaged execution."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def data_root() -> Path:
    """Return the operational data directory owned by SERM V2."""
    configured = os.environ.get("SERM_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return application_root() / "data"


def database_path() -> Path:
    """Return the V2 SQLite database path inside the V2 data directory."""
    return data_root() / "database" / "serm.db"


def catalogs_root() -> Path:
    """Return the directory for imported catalog data."""
    return data_root() / "catalogs"


def cache_root() -> Path:
    """Return the directory for disposable cache data."""
    return data_root() / "cache"


def scans_root() -> Path:
    """Return the directory for filesystem scan results."""
    return data_root() / "scans"


def staging_root() -> Path:
    """Return the directory for provider staging data."""
    return data_root() / "staging"


def integrations_root() -> Path:
    """Return the directory for external integration configuration."""
    return data_root() / "integrations"


def logs_root() -> Path:
    """Return the directory for SERM V2 logs."""
    return data_root() / "logs"


def exports_root() -> Path:
    """Return the directory for generated exports."""
    return data_root() / "exports"


def backups_root() -> Path:
    """Return the directory for database/application backups."""
    return data_root() / "backups"
