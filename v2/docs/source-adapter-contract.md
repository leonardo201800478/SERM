# SERM V2 — Source Adapter Contract

Status: design baseline

## Purpose

Source adapters isolate external formats from the SERM canonical model. An adapter reads a source, validates its own format, normalizes records into provider-neutral DTOs and preserves provenance. It must never write directly into arbitrary canonical tables.

## Pipeline

`Source file/API -> parser -> source DTO -> validation -> mapping/resolution -> canonical repository`

The parser and source DTO may preserve source-specific fields. The canonical layer receives only normalized concepts plus provenance.

## Required adapter capabilities

Every adapter should expose:

- source identity and source version/date;
- input validation;
- streaming iteration where practical;
- stable source identifiers;
- source-native names;
- provenance for every emitted record;
- deterministic parsing;
- error reporting that identifies the source record without aborting the entire import when a recoverable record is malformed.

Adapters must not:
- assume filenames are canonical identity;
- overwrite canonical records blindly;
- discard source identifiers;
- mix user-local paths with source metadata;
- require the source to be installed locally when a DAT/XML/API representation is sufficient.

## Provider-neutral record families

### PlatformRecord

Represents a platform/system identity candidate.

Fields conceptually include:
- source_id
- source_name
- canonical_candidate_name
- alternate_names
- manufacturer/developer metadata when supplied
- technical metadata when supplied
- provenance

### GameRecord

Represents a logical software/game identity candidate.

Fields conceptually include:
- source_id
- source_name
- platform reference
- release metadata
- region/language/revision markers
- aliases
- descriptive metadata
- provenance

### ReleaseRecord

Represents a concrete release/dump definition.

Fields conceptually include:
- source_id
- game reference
- platform reference
- region
- languages
- revision/version
- release status/type
- source-native naming
- provenance

### ArtifactRecord

Represents a concrete file or media representation.

Fields conceptually include:
- source_id
- release reference
- filename
- extension/format
- size
- hashes
- container/media type
- parent/clone relationship when applicable
- provenance

### RelationshipRecord

Represents source-defined relationships such as parent/clone, BIOS dependency, device dependency, or emulator/platform capability. The adapter emits the relationship; the resolver decides how it maps to canonical entities.

## Initial adapter priorities

### 1. No-Intro

No-Intro is the first cartridge/handheld adapter. Its DAT convention explicitly encodes naming and dump metadata, and current Dat-o-Matic reports expose dump format, ROM name, size, CRC32 and SHA1. citeturn0search15turn0search2

The adapter must preserve the complete source-native name because region, language, revision and other status markers can carry semantic information. Filename normalization must therefore happen only after parsing, never before.

### 2. Redump

Redump is the first optical-media adapter. Its source model will be kept separate from cartridge DAT assumptions. The adapter must be able to represent disc-level identity, track/media information and hashes without forcing everything into a single ROM-file model.

### 3. MAME

MAME is a machine/software ecosystem rather than a simple game DAT. Its official `-listxml` output is intended for other tools to consume and contains comprehensive system/device information. citeturn0search16

MAME short names are source-native identifiers for systems, software lists, software items and parts. They must be preserved as source IDs, not replaced by SERM IDs. citeturn0search0

The MAME adapter must model at least:
- machine/system;
- parent/clone;
- ROM entries;
- BIOS/device relationships;
- samples where present;
- CHD/media dependencies;
- software lists;
- software items and parts.

MAME's parent/clone structure and CHD dependency behavior are explicitly part of its file lookup model. citeturn0search0turn0search5

### 4. LaunchBox

LaunchBox remains an auxiliary metadata adapter. It contributes names, aliases, descriptions, images, platform metadata and emulator relationships. It must not become the authority for preservation identity.

### 5. RetroArch RDB

RetroArch RDB is an auxiliary metadata adapter. Its records should be mapped through hashes/names/platform context when possible and retain the original RDB identity.

### 6. WHDLoad / eXoDOS

These are convenience-distribution adapters. Their primary purpose is mapping convenient package names and structures back to canonical games/releases and recording the supported launch representation. They must never redefine canonical preservation identity merely because their package naming differs.

## MAME-specific normalization rule

Do not flatten MAME machines, software-list items and ROM files into `Game` rows. A machine may have ROMs, BIOS devices, samples and CHDs; software-list items may contain multiple parts and parent/clone relationships. The canonical model therefore needs source relationships capable of representing these structures without losing the MAME hierarchy. citeturn0search0

## Hash policy

A source may provide CRC32, SHA-1, SHA-256 or other digests. The adapter preserves every supported digest with its algorithm. Canonical matching should use the strongest available compatible evidence and must not assume CRC32 alone is globally unique.

For CHD, do not treat the compressed file checksum as the semantic media identity. MAME documents that CHD lookup uses the content digest from the CHD header and that compression choices can change the file checksum. citeturn0search0

## Error policy

Parsing errors are classified as:

- fatal source error: the source cannot be parsed or validated;
- record error: one record is malformed and can be skipped with diagnostics;
- mapping ambiguity: record is valid but cannot yet be resolved to a canonical entity;
- unsupported feature: source feature is valid but not yet represented by the adapter.

The adapter must never silently discard unsupported or ambiguous data.

## Implementation order

1. Define shared provider DTOs and provenance types.
2. Implement No-Intro parser and fixtures.
3. Implement Redump parser and fixtures.
4. Implement MAME XML parser and fixtures.
5. Implement mapping/resolution contracts.
6. Add LaunchBox and RetroArch as enrichment providers.
7. Add WHDLoad/eXoDOS convenience mappings.
8. Freeze canonical relational schema only after the three preservation adapters are validated.
