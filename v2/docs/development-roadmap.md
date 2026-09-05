# V2 Development Roadmap

## Milestone 0 — Clean Home

### Status

**Consolidated / functionally validated in September 2026.**

The Home provides the central emulator-management surface, including emulator discovery/configuration, installation/update operations, executable/version persistence, window/monitor persistence, RetroArch core catalog/filtering, sequential core installation with retry/CRC validation, WHDLoad/Amiberry data acquisition, and C64/TOSEC catalog acquisition.

Further work should avoid unnecessary redesign of the Home while the ROM scanning subsystem is built.

## Milestone 1 — Data Foundation

- path resolver;
- SQLite engine/session;
- SQLAlchemy persistence layer;
- migration runner;
- database health check;
- configuration schema bootstrap.

**Status: implemented and extended progressively.**

## Milestone 2 — Canonical data model

- sources and versions;
- platforms and systems;
- canonical identities and releases;
- source identities;
- provenance and mappings;
- files and hashes.

**Status: implemented progressively.**

## Milestone 3 — Runtime model

- runtime;
- emulator/backend;
- core;
- execution profile;
- platform/runtime/core relationships;
- configuration properties;
- filesystem paths;
- emulator configuration catalog.

**Status: implemented progressively.**

## Milestone 4 — Metadata providers

- LaunchBox Metadata DB;
- LaunchBox Platforms.xml;
- RetroArch RDB;
- provider validation and conflict handling.

**Status: progressive integration.**

## Milestone 5 — Preservation providers

- No-Intro;
- Redump;
- MAME/ListXML;
- FBNeo;
- MAME Softlists;
- trusted BIOS sources.

### MAME foundation

The MAME catalog is obtained from the configured executable with `mame.exe -listxml`. The V2 environment has already produced a catalog of 50,368 machines. The relational catalog contains ROM, disk, display, BIOS, device, software-list and related machine definitions.

### MAME configuration

MAME configuration extraction uses the configured executable and records native options, defaults, current observations, UI types, choices, scope/precedence, dependencies, hardware constraints, SERM profiles and configuration bindings.

### Provider foundations

Redump, WHLoader/Amiberry and C64/TOSEC acquisition foundations are implemented progressively. eXoDOS is excluded from the active scope.

## Milestone 6 — ROM Scan subsystem — NEXT

ROM scanning is a first-class cross-system subsystem. The GUI surface is now established in `serm_v2.gui.rom_scan_page` with two dedicated areas:

1. **MAME** — first and most complete scanner implementation;
2. **Outros Scans** — shared surface for No-Intro, Redump, WHLoader and C64.

The GUI must consume a generic scan engine. Filesystem traversal, hashing, archive inspection, matching and result persistence must not be implemented inside the Qt widgets.

### 6.1 Generic physical scan engine

Responsibilities:

- scan configured filesystem roots;
- recursively discover supported physical files;
- inspect ZIP archives without unnecessary extraction;
- inspect WHDLoad `.lha` packages through an adapter/service;
- inspect optical-media representations;
- collect size, timestamps and physical location;
- calculate and cache hashes;
- match against canonical catalog definitions;
- classify current, wrong, missing, duplicate and fixable content;
- preserve scan provenance and run identity;
- support incremental re-scan;
- provide deterministic results independent of GUI;
- support progress, cancellation and safe parallelism.

### 6.2 MAME scan — first consumer

The MAME scanner is the reference implementation for the generic engine and must preserve the functional behavior already proven in V1 while adapting persistence to V2.

The MAME scan works from the canonical ListXML-derived catalog and must understand:

- machines;
- parent/clone relationships;
- ROM regions and ROM entries;
- expected filename, size, CRC32 and SHA-1;
- merge semantics;
- BIOS dependencies;
- optional ROMs;
- disks/CHDs;
- software lists where applicable.

The scan UI is expected to expose at least:

- ROM root selection;
- configured MAME executable/catalog;
- scan options;
- progress;
- machines/sets analyzed;
- files discovered;
- current/OK;
- wrong;
- missing;
- fixable/reconstructable;
- parent/clone context;
- detailed per-set/per-file diagnostics;
- last scan reuse;
- cancellation.

### 6.3 MAME-compatible scan family

The engine must be generalized from MAME semantics so systems using the MAME-style machine/ROM/archive/hash model can reuse the same implementation.

They are consumers of the generic engine, not separate scanners.

### 6.4 No-Intro and C64

No-Intro and C64 game content will primarily be handled as ZIP-based ROM collections. The external catalog adapter supplies canonical expected identities and hashes; the physical scanner supplies archive/member evidence.

### 6.5 WHLoader

WHLoader scans operate on `.lha` WHDLoad packages. The scan must identify the physical package, its expected catalog identity and its internal/metadata evidence without treating the package as a normal MAME ZIP.

The Amiberry Game DB already exists as the WHLoader catalog foundation.

### 6.6 Redump

Redump is the optical-media branch of the scan subsystem.

Priority order:

```text
CHD
 ↓
CUE/BIN
```

CHD is the preferred representation for scanned optical media. When CUE/BIN is found, the UI will offer conversion to CHD.

The conversion must use **only the command line of `chdman.exe`**, obtained from the MAME `exe` directory. SERM must not implement its own CHD encoder.

The CUE/BIN source should remain untouched by default. Conversion is a separate transformation operation, not part of the read-only physical scan itself.

After conversion, the generated CHD must be validated and then made available to the matching pipeline.

### 6.7 Scan result model

The canonical result state must distinguish at least:

```text
CURRENT / OK
WRONG
MISSING
FIXABLE
DUPLICATE
UNRESOLVED
```

A result must retain provenance sufficient to answer:

- which scan run produced it;
- which physical path was inspected;
- which archive/member was matched;
- which catalog/source version was used;
- which hash/size evidence produced the match;
- which parent/clone or canonical identity was resolved.

### 6.8 Matching and DE-PARA

- canonical hash identity;
- source-specific identity mapping;
- filename as supporting evidence, never sole authoritative identity;
- parent/clone resolution;
- duplicate physical files;
- valid shared physical evidence;
- conflict/ambiguity handling;
- provenance for every match.

### 6.9 Reconstruction planner

Only after scan/matching is stable:

- identify incomplete sets;
- determine reconstructable content;
- generate deterministic reconstruction plans;
- preserve source files;
- execute transformations in isolated temporary workspaces;
- validate before publication.

### 6.10 ArchiveService / CHD / atomic publication

Later work:

- ArchiveService;
- CHD service wrappers;
- `chdman.exe` integration;
- temporary workspaces;
- validation;
- atomic publication;
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

Do not implement later milestones by importing V1 services. V1 is a behavioral and algorithmic reference only. Reimplement proven behavior against V2 contracts and the current relational data model.
