# SERM V2

**Strife Emulator and ROMs Manager — V2**

SERM is a desktop application for managing emulators, catalogs, ROM collections, scans, filtering, reconstruction and execution metadata from a single local workspace.

> **V2 is the active implementation.** The current `main` tree contains the V2 project; no V1 source tree is present in the active filesystem hierarchy. Historical V1 behavior is treated as reference material and must not become a V2 runtime dependency.

## Architecture

```text
Qt / PySide6 GUI
        ↓
Application services
        ↓
Domain + persistence + adapters
        ↓
SQLite / filesystem / external tools
```

The V2 package is `serm_v2`. The application entry point is `serm_v2.main:main` and the installed console script is `serm`.

### Main subsystems

- **GUI** — Home, emulator management, directories, filters, scan and reconstruction surfaces.
- **Database** — SQLite with SQLAlchemy and versioned SQL migrations.
- **Catalog** — acquisition, normalization and persistence of catalog metadata.
- **MAME** — ListXML ingestion, classification, filtering, display/resolution/vsync data and scan integration.
- **No-Intro** — DAT/archive acquisition, filtering and scanning foundations.
- **WHDLoad/Amiberry** — specialized catalog acquisition and scan support.
- **C64/TOSEC** — catalog acquisition foundation.
- **ROM Scan** — filesystem discovery, metadata/hash matching, checkpoints, caching, filtering and persistent scan results.
- **Reconstruction** — dependency resolution, archive operations and publication workflows.
- **RetroArch** — runtime/core management and configuration integration.
- **LaunchBox** — optional metadata/provider and audit integration; never the SERM source of truth.

## Data model

SERM separates four concepts that must not be conflated:

```text
Source
  ↓
Catalog / Catalog Version
  ↓
Canonical Identity
  ↓
File / Hash
  ↓
Scan / Match
  ↓
Transformation / Reconstruction
  ↓
Execution Profile
```

SQLite stores SERM-managed metadata, relationships, configuration and scan state. Physical ROMs, ISOs, CHDs and archives remain in user-selected filesystem locations.

External XML, DAT, JSON, CFG and database formats are handled through adapters or generated as interoperability artifacts. They do not become the canonical SERM schema implicitly.

## V1 boundary

V1 is not part of the active V2 package hierarchy. If historical V1 material is consulted, it must remain outside the V2 import graph. No V2 service should import V1 models, database tables, configuration or runtime services.

## Development status

The project is in **alpha development**. The current V2 tree contains functional application infrastructure, Home and emulator-management flows, catalog acquisition/normalization, MAME and No-Intro filtering/scanning foundations, scan persistence/resilience, and reconstruction components. Some source families and advanced reconstruction workflows remain under active development.

The roadmap in [`docs/phases.md`](docs/phases.md) is authoritative for planned work. Historical audit documents are not current status documents.

## Requirements

- Python `>=3.12,<3.15`;
- PySide6 `>=6.8,<7`;
- SQLAlchemy `>=2.0,<3`;
- Windows is the primary target; Qt/X11 compatibility is declared by the package metadata.

Development dependencies: pytest, pytest-cov and Ruff.

## Installation

From the `v2` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

For development tooling:

```powershell
pip install -e ".[dev]"
```

## Running

```powershell
python -m serm_v2
```

or, after installation:

```powershell
serm
```

## Tests and quality checks

```powershell
pytest
ruff check serm_v2 tests
ruff format --check serm_v2 tests
```

Ruff is configured with a 100-character line limit, Python 3.12 target and import/bugbear/modernization checks.

## Database

Initialization and migration behavior live under `serm_v2/database`. Versioned SQL migrations are stored in `serm_v2/database/migrations` and are applied by the V2 bootstrap; Alembic is not part of the current migration mechanism.

The database is application state, not a copy of the user's ROM collection. Physical content stays outside the database.

## Documentation

The complete technical documentation is indexed in [`docs/index.md`](docs/index.md).

Recommended reading order:

1. [`docs/architecture.md`](docs/architecture.md) — architecture and boundaries;
2. [`docs/project-tree.md`](docs/project-tree.md) — source tree;
3. [`docs/development-environment.md`](docs/development-environment.md) — development setup;
4. [`docs/database.md`](docs/database.md) — persistence and migrations;
5. [`docs/catalogs.md`](docs/catalogs.md) — catalog model;
6. [`docs/source-strategy.md`](docs/source-strategy.md) — source authority;
7. [`docs/status/scan_status.md`](docs/status/scan_status.md) — scanner invariants;
8. [`docs/phases.md`](docs/phases.md) — roadmap.

## License

See [`LICENSE`](LICENSE).
