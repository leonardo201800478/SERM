# SERM V2 — Data Model Foundation

Status: design baseline

## 1. Architectural rule

SERM V2 owns its canonical data model. External sources are evidence/providers and are never copied as the canonical schema.

Sources currently considered:
- No-Intro / Dat-o-Matic: cartridge and clean commercial releases.
- Redump: optical media preservation.
- MAME / FBNeo: arcade and machine-oriented data.
- LaunchBox: rich auxiliary metadata, aliases, images, platforms and emulator relationships.
- RetroArch RDB: auxiliary metadata.
- WHDLoad / Retroplay: convenient Amiga distribution data, mapped back to canonical identities.
- eXoDOS: convenient MS-DOS distribution data, mapped back to canonical identities.

## 2. Canonical domain model

The core distinction is:

`Game` (canonical work/identity) -> `Release` -> `Media/Representation` -> `File/Artifact` -> `Hash`

A platform is a first-class entity. A release belongs to a platform and can have region, revision, language and source provenance without duplicating the canonical game.

## 3. Initial entities

### Platform
Canonical machine/platform identity. Stores normalized name and stable technical identity. Alternate provider names are separate records.

### Game
Canonical logical game identity, independent of a particular dump or convenience package.

### Release
A concrete commercial/software release of a game for a platform, including region/revision/language metadata.

### Artifact
A representation supplied by a source or present in the user's collection: ROM, ZIP, CHD, BIN/CUE, ISO, LHA, DOS archive, etc. Artifact identity is based on source evidence and hashes, not filename alone.

### Hash
Cryptographic or preservation hashes attached to artifacts or contained files. CRC32 is useful source evidence but is not sufficient as the sole canonical identity.

### Source
A registered data source with provenance and version/date information. Examples: No-Intro, Redump, MAME, LaunchBox, RetroArch, WHDLoad and eXoDOS.

### SourceRecord / Mapping
Maps an external identifier/name to a canonical SERM entity while retaining source identity. This is the DE-PARA layer.

### Alias
Alternative names for games, platforms or releases, with optional region/language/source provenance.

### Image
Metadata describing artwork/media associated with a canonical entity. Physical image files remain outside the relational core where appropriate.

### Emulator
Executable/runtime capable of launching one or more platforms.

### EmulatorPlatform
Capability relationship between emulator and platform, including supported extensions and execution information.

### LaunchProfile
A concrete SERM execution profile. This separates emulator capability from a user's local installation/configuration and permits standalone emulators, RetroArch cores and MAME configurations.

## 4. LaunchBox findings incorporated into the design

The audited installation contains 187,564 Games, 1,322,505 GameImages, 69,802 GameAlternateTitles, 190 Platforms, 431 PlatformAlternateNames, 35 Emulators and 98 EmulatorPlatforms.

Important observations:
- Games.Name is highly populated but is not a safe canonical identity by itself.
- Games.Platform is populated and has 189 distinct values.
- Overview, Developer and Publisher are rich metadata sources.
- GameAlternateTitles provides 69,802 alternate-title records and must be treated as alias evidence rather than canonical duplication.
- GameImages is a high-volume auxiliary domain and should not bloat the core game/release tables.
- EmulatorPlatforms contains command lines and applicable extensions for many, but not all, relationships.
- RequiredBiosFile is sparse and therefore should not be modeled as a mandatory emulator-platform property.
- LaunchBox-specific startup/setup fields are sparse and provider-specific; they do not belong in the canonical game model.

## 5. Provenance principle

Every imported external fact must be traceable to its source. A LaunchBox value may enrich SERM metadata, but it must remain distinguishable from a preservation authority value.

Preferred precedence is domain-specific, not global. Preservation identity comes from preservation DATs; metadata enrichment may come from LaunchBox or other auxiliary providers.

## 6. Storage direction

SQLite is the intended local embedded database for the desktop V2 application, accessed through SQLAlchemy and migrated with Alembic. The database belongs under `v2/data/`, never under the legacy V1 data tree.

Large mutable collections such as downloaded artwork, source archives, caches and generated reports remain filesystem assets with database references rather than BLOB-heavy tables.

## 7. Deliberately postponed

Do not create the final migration until:
1. source-specific schemas have been documented;
2. No-Intro and Redump identity requirements are mapped;
3. MAME machine/ROM/CHD relationships are mapped;
4. WHDLoad and eXoDOS DE-PARA requirements are mapped;
5. RetroArch RDB and LaunchBox mappings are defined;
6. uniqueness and foreign-key rules are reviewed.

The next implementation phase is therefore source adapters + normalized ingestion contracts, followed by the first Alembic migration.
