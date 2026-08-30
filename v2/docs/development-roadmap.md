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

### Milestone 0 boundary

The emulator installation/update backend from V1 is **not imported** into V2. The Home keeps the visual organization and operational intent of the proven legacy screen, while runtime/emulator services will be rebuilt against V2 contracts.

## Milestone 1 — Data Foundation

- path resolver;
- SQLite engine;
- SQLAlchemy declarative base;
- session management;
- migration runner;
- first schema;
- database health check.

## Milestone 2 — Canonical data model

- sources and versions;
- platforms and systems;
- canonical identities and releases;
- source identities;
- provenance and mappings;
- files and hashes.

## Milestone 3 — Runtime model

- runtime;
- emulator/backend;
- core;
- execution profile;
- platform/runtime/core relationships;
- configuration properties;
- filesystem paths.

## Milestone 4 — Metadata providers

- LaunchBox Metadata DB;
- LaunchBox Platforms.xml;
- RetroArch RDB;
- provider validation and conflict handling.

## Milestone 5 — Preservation providers

- No-Intro;
- Redump;
- MAME/listxml;
- FBNeo;
- Softlists.

### MAME foundation increment

The first MAME integration is now implemented in `serm_v2.emulation.mame_dat_scraper`.

It obtains the authoritative machine catalog from the installed executable with:

```text
mame.exe -listxml
```

This increment intentionally stops at safe extraction/validation. The next MAME increments are parser → provenance → persistence → resolution/refresh fallback handling → display geometry → Timing Advisor.

## Milestone 6 — Convenience providers

- WHDLoad/Retroplay;
- eXoDOS;
- C64 and other specialized sources.

## Milestone 7 — Matching and reconstruction

- physical scan;
- hash matching;
- DE-PARA;
- reconstruction planner;
- ArchiveService;
- CHD service;
- atomic publication.

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

See `v2/docs/timing-and-display-planning.md` and `v2/docs/mame-dat-scraper.md`.

## Rule

Do not implement later milestones by importing V1 services. If a V1 behavior is valuable, reimplement it against the V2 contracts.
