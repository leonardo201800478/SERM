# SERM V2

SERM V2 is the active architecture of the project.

## V2 rules

- V1 is legacy reference only.
- V2 does not depend on V1 database, models, services, configuration files, XML or tests.
- V2 starts with a clean Home and a new application package.
- SQLite is the local source of truth for SERM-managed data.
- SQLAlchemy is the persistence layer; migrations are versioned.
- External XML/CFG/JSON formats are adapters or generated artifacts when required.
- ROMs, ISOs, CHDs and archives remain in user-selected filesystem locations.

## Current status — September 2026

The Home is the first consolidated V2 application surface. Its four emulator management flows are operational and the Home is considered functionally validated for the current review cycle.

The Home currently covers:

- emulator discovery, configuration, installation and update operations;
- persisted executable and installed-version information;
- safe restoration of window size, position and monitor;
- RetroArch core catalog acquisition and local filtering;
- Stable and Beta/Nightly catalog handling;
- sequential core installation with retries and CRC validation;
- WHDLoad/Amiberry database acquisition and scan support;
- C64 catalog acquisition through the TOSEC source;
- central navigation to the remaining V2 application surfaces.

RetroArch catalog filters are persisted for the lifetime of the application session. This is intentionally session state; it is not yet a disk-persisted user preference.

The Home should now be treated as a stable functional surface while the next V2 work moves to ROM scanning and matching.

## Data architecture

The V2 data foundation follows:

```text
Source
  ↓
Catalog / Version
  ↓
Canonical Identity
  ↓
Mapping / Provenance
  ↓
File / Hash
  ↓
Scan / Matching
  ↓
Transformation / Reconstruction
  ↓
Execution Profile
```

SQLite stores SERM-managed metadata and scan state. Physical ROMs and archives remain in their original user-selected filesystem locations.

## ROM scanning architecture

ROM scanning is a cross-system capability, not a MAME-only feature.

The first implementation target is MAME because its V2 catalog already comes from the authoritative `mame.exe -listxml` output and because the legacy V1 implementation provides a proven behavioral reference. The V1 scanner will be studied and adapted, not imported as a V2 dependency.

The scan engine must be designed so the same core can support:

- MAME;
- systems whose catalogs and ROM definitions use the MAME-compatible model;
- other systems explicitly adapted to the same machine/ROM/disk/hash semantics.

The target pipeline is:

```text
System Catalog / DAT
        ↓
Canonical machine/release definitions
        ↓
Physical filesystem scan
        ↓
File metadata + hashes
        ↓
Hash / size / identity matching
        ↓
Scan result
        ↓
Missing / Wrong / Current / Fixable
        ↓
Reconstruction planner (future)
```

The scanner must remain independent of the GUI. The GUI is a consumer of scan results and should not contain filesystem traversal, hash calculation or matching rules.

### MAME first increment

The first MAME scan implementation will reuse the functional concepts proven in V1 while adapting them to the V2 data model:

- configured ROM directories;
- recursive filesystem discovery;
- archive/ZIP inspection without unnecessarily extracting files;
- ROM size and hash calculation;
- CRC32/SHA-1 matching according to the catalog definition;
- parent/clone awareness;
- detection of complete and incomplete sets;
- detection of incorrect ROMs;
- identification of potentially fixable/reconstructable content;
- incremental/rescan behavior;
- persistent scan runs and results;
- progress and operational logging;
- parallelizable work where safe.

No V1 database table or V1 service contract will be carried into V2. The V1 implementation is a behavioral and algorithmic reference only.

## Source families

The scan engine is intended to consume multiple catalog families through adapters:

### Preservation / authoritative

- MAME/ListXML;
- FBNeo;
- MAME Softlists;
- No-Intro / Dat-o-MATIC;
- Redump;
- trusted BIOS sources.

### Convenience / specialized

- WHDLoad / Amiberry database;
- C64 / TOSEC;
- other specialized sources added through dedicated adapters.

The source adapter is responsible for converting the external representation into the canonical V2 catalog. The scan engine should operate on canonical data rather than source-specific XML/JSON structures.

## Current implementation order

1. ~~clean Home~~ — consolidated;
2. ~~data paths and application settings~~ — implemented;
3. ~~SQLite engine/session and migration infrastructure~~ — implemented;
4. ~~source registry and initial catalog infrastructure~~ — implemented;
5. ~~platform/system identity and catalog/provenance foundations~~ — implemented progressively;
6. ~~runtime/emulator/core/execution profile foundations~~ — implemented progressively;
7. ~~source adapters~~ — MAME, Redump, WHLoader and C64/TOSEC foundations implemented;
8. **ROM scan engine** — next implementation target;
9. **MAME ROM scanner integration** — first consumer of the generic engine;
10. **MAME-compatible system adapters** — subsequent consumers;
11. **hash matching / DE-PARA refinement**;
12. **reconstruction planner**;
13. **ArchiveService / CHD service / atomic publication**;
14. **execution and profile integration**.

## V1 boundary

V1 remains available for historical research, behavioral comparison and recovery of proven algorithms. V2 must reimplement those behaviors against V2 contracts.

A V1 implementation is considered reusable knowledge only after its assumptions are identified and reconciled with the V2 data model.

## Documentation

- `v2/docs/architecture-v2.md` — architecture;
- `v2/docs/project-tree.md` — project structure;
- `v2/docs/development-roadmap.md` — implementation roadmap;
- `v2/docs/development-environment.md` — development environment;
- `v2/docs/legacy-boundary.md` — V1 isolation;
- `v2/docs/mame-dat-scraper.md` — MAME ListXML ingestion;
- `v2/docs/mame-data-and-profile-storage.md` — MAME data/profile persistence;
- `v2/docs/configuration-data-model.md` — configuration model;
- `v2/docs/timing-and-display-planning.md` — display/timing architecture;
- `docs/data-foundation.md` — consolidated data decisions;
- `docs/source-strategy.md` — source strategy;
- `docs/catalogs.md` — catalog strategy;
- `docs/phases.md` — historical/consolidated roadmap.
