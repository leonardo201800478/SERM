# V2 Development Roadmap

## Milestone 0 — Clean Home

- V2 package exists;
- application entry point exists;
- Home uses only V2 modules;
- proven Home layout migrated conceptually from the legacy application;
- no V1 imports;
- isolated V2 tests start here;
- LaunchBox executable discovery/configuration/launch is available from Home;
- LaunchBox metadata database and `Platforms.xml` locations are discoverable.

### Status

**Consolidated / functionally validated in September 2026.**

The Home now provides the central emulator-management surface, including emulator discovery/configuration, installation/update operations, executable/version persistence, window/monitor persistence, RetroArch core catalog/filtering, sequential core installation with retry/CRC validation, WHDLoad/Amiberry data acquisition, and C64/TOSEC catalog acquisition.

The Home is now considered a stable functional surface for the current review cycle. Further work should avoid unnecessary redesign of the Home while the ROM scanning subsystem is built.

### Milestone 0 boundary

The emulator installation/update backend from V1 is **not imported** into V2. The Home keeps the visual organization and operational intent of the proven legacy screen, while runtime/emulator services are implemented against V2 contracts.

## Milestone 1 — Data Foundation

- path resolver;
- SQLite engine;
- SQLAlchemy declarative base;
- session management;
- migration runner;
- first schema;
- database health check;
- configuration schema bootstrap.

### Status

**Implemented.** Subsequent migrations continue to extend the foundation as new domains are introduced.

## Milestone 2 — Canonical data model

- sources and versions;
- platforms and systems;
- canonical identities and releases;
- source identities;
- provenance and mappings;
- files and hashes.

### Status

**Implemented progressively.** The model is now the basis for the MAME, Redump, WHLoader and C64/TOSEC integrations.

## Milestone 3 — Runtime model

- runtime;
- emulator/backend;
- core;
- execution profile;
- platform/runtime/core relationships;
- configuration properties;
- filesystem paths;
- emulator configuration catalog.

### Status

**Implemented progressively.** Emulator management and MAME configuration/catalog work are active V2 consumers of this model.

## Milestone 4 — Metadata providers

- LaunchBox Metadata DB;
- LaunchBox Platforms.xml;
- RetroArch RDB;
- provider validation and conflict handling.

### Status

**In progress / progressive integration.**

## Milestone 5 — Preservation providers

- No-Intro;
- Redump;
- MAME/listxml;
- FBNeo;
- Softlists.

### MAME foundation increment

The first MAME integration is implemented in `serm_v2.emulation.mame_dat_scraper`.

It obtains the authoritative machine catalog from the installed executable with:

```text
mame.exe -listxml
```

The V2 environment has already produced a catalog of 50,368 machines from the configured MAME executable.

### MAME configuration increment

The V2 contains a relational configuration schema and a catalog service in `serm_v2.services.mame_configuration_catalog`.

The service uses the configured MAME executable as the source of truth and queries:

```text
mame.exe -version
mame.exe -showconfig
mame.exe -noreadconfig -showconfig
mame.exe -showusage
```

The database records native options, observed defaults, current configuration observations, option types, recommended UI controls, discrete choices, configuration surface, scope/precedence, dependencies, hardware capability constraints, SERM profiles and configuration file bindings.

### MAME scan preparation

The MAME catalog is now the authoritative catalog layer for the first ROM scan implementation. The next work is to connect the physical filesystem to this catalog without coupling scan logic to the GUI.

## Milestone 6 — Convenience providers

- WHDLoad/Retroplay;
- eXoDOS;
- C64 and other specialized sources.

### Current scope adjustment

WHDLoad/Amiberry and C64/TOSEC foundations are implemented progressively. **eXoDOS is currently excluded from the active implementation scope** and should not be reintroduced without a new project decision.

## Milestone 7 — ROM Scan, Matching and Reconstruction

This milestone is expanded to make ROM scanning a first-class cross-system subsystem.

### 7.1 Generic ROM Scan Engine — NEXT

Build a system-independent scan engine responsible for physical filesystem inspection and matching against canonical catalog definitions.

Responsibilities:

- scan configured filesystem roots;
- discover files and archives;
- inspect ZIP contents without unnecessary extraction;
- collect file size and archive/member metadata;
- calculate required hashes efficiently;
- reuse previously calculated hashes when the file identity is unchanged;
- match physical files against canonical ROM/disk definitions;
- classify exact, current, wrong, missing and fixable content;
- preserve scan provenance and timestamps;
- support incremental re-scan;
- provide deterministic results independent of the GUI;
- expose progress, cancellation and operational diagnostics;
- allow safe parallelism for filesystem and hashing workloads.

### 7.2 MAME ROM Scanner — FIRST CONSUMER

The first concrete implementation will target MAME and reuse the proven behavior of the V1 scanner as a reference.

The MAME adapter must understand:

- machine definitions from ListXML;
- parent/clone relationships;
- ROM regions and ROM entries;
- ROM filenames;
- expected sizes;
- CRC32;
- SHA-1;
- disk/CHD definitions where applicable;
- BIOS relationships where applicable.

The GUI should present at minimum:

- scan root selection;
- scan progress;
- total files discovered;
- machines/sets analyzed;
- exact/current content;
- missing content;
- wrong content;
- potentially fixable content;
- parent/clone context;
- detailed diagnostics for a selected machine/set.

### 7.3 MAME-compatible systems

The scan engine must not be designed around MAME-specific assumptions when those assumptions can be generalized.

After the MAME implementation is stable, adapters can support **other systems based on the MAME ROM/catalog model**, reusing the same physical scanner, hashing layer, matching engine and result model.

MAME-compatible systems are therefore consumers of the same engine, not independent scanner implementations.

### 7.4 Matching / DE-PARA

- canonical hash identity;
- source-specific identity mapping;
- filename as supporting evidence rather than authoritative identity;
- parent/clone resolution;
- duplicate physical files;
- one physical file satisfying multiple catalog references when semantically valid;
- provenance of every match;
- conflict and ambiguity handling.

### 7.5 Reconstruction planner

After scanning and matching are stable:

- identify incomplete sets;
- determine whether missing content can be reconstructed from known physical files;
- plan safe archive transformations;
- generate deterministic reconstruction plans;
- keep transformation separate from scanning;
- never modify source files during the scan phase.

### 7.6 ArchiveService / CHD / publication

Later increments:

- ArchiveService;
- CHD service;
- atomic temporary workspace;
- validation before publication;
- atomic replacement/publication;
- rollback/error preservation.

## Cross-cutting MAME Display/Timing Track

- machine-native resolution and refresh facts;
- pixel aspect and physical/display aspect;
- orientation;
- monitor hardware profile;
- VRR/G-Sync/FreeSync detection;
- native monitor fullscreen policy;
- integer/pixel-perfect geometry;
- artwork-aware geometry;
- adaptive Timing Advisor;
- low-latency policy without frame-pacing regression;
- A/V/input synchronization policy;
- per-game SERM/MAME execution profiles;
- decision provenance and diagnostics.

See `v2/docs/timing-and-display-planning.md`, `v2/docs/mame-dat-scraper.md`, `v2/docs/mame-data-and-profile-storage.md` and `v2/docs/configuration-data-model.md`.

## Development rule

Do not implement later milestones by importing V1 services. If a V1 behavior is valuable, reimplement it against the V2 contracts.

For ROM scanning specifically, V1 is a **behavioral and algorithmic reference**. Its data structures, database schema and service contracts are not V2 contracts.

The generic scan engine must remain independent of GUI and source-specific adapters. Source adapters convert external catalogs into canonical V2 definitions; the scan engine consumes those canonical definitions.
