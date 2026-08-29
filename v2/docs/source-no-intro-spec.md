# SERM V2 — No-Intro Source Specification

Status: design / implementation preparation

## Purpose

Define the information SERM must preserve when consuming No-Intro DAT data without making No-Intro's naming convention the SERM canonical schema.

## Source role

No-Intro is a preservation-oriented source for cartridge and related clean commercial software dumps. In SERM it is an authoritative source for dump identity/evidence in the domains it covers, while SERM remains responsible for canonical game/release identity.

## Adapter boundary

The No-Intro adapter must perform only:

1. source file discovery and decoding;
2. DAT metadata extraction;
3. machine/system identification;
4. game/release grouping;
5. ROM/file extraction;
6. hash extraction;
7. region/language/status/name token preservation;
8. source provenance creation.

It must not write directly to the database or invent canonical identities.

## Information to preserve

At minimum the normalized source record must retain:

- source name;
- source DAT/version identity when available;
- source game/set name;
- source game/set description;
- source machine/system;
- source ROM filename;
- ROM size;
- CRC32;
- SHA-1 when supplied;
- MD5 when supplied;
- region/language information encoded by the source;
- status/flags encoded by the source;
- parent/clone or set relationship when explicitly supplied;
- original source naming string.

The original name is retained even when SERM derives normalized fields from it.

## Identity rules

Filename parsing is a normalization aid, not the sole identity mechanism.

Hash evidence must be retained separately from names. A release may contain multiple files and a file may be represented by multiple source records.

Region, language, revision and other semantic tokens must not be discarded during normalization.

## Proposed intermediate records

Conceptual DTOs:

- `NoIntroDatInfo`
- `NoIntroSetRecord`
- `NoIntroRomRecord`
- `NoIntroProvenance`

These records are source DTOs. They are not SQLAlchemy models.

## Mapping to SERM

`NoIntroSetRecord` -> candidate `Game` + `Release`

`NoIntroRomRecord` -> `Artifact` / contained file + `Hash`

No-Intro system identifier/name -> candidate `Platform` through source mapping.

Original source IDs/names -> `SourceRecord` mapping layer.

## Validation

The adapter must reject or flag records that have no usable source identity or no file/hash evidence. It must report malformed DAT/XML instead of silently dropping records.

Unknown fields should be preserved in source diagnostics where practical, but should not leak into the canonical model automatically.

## First implementation scope

The first implementation should support standard DAT/XML input, produce deterministic DTOs, expose parser diagnostics, and include fixtures covering:

- one single-file cartridge set;
- one multi-file set;
- regional variants;
- revision variants;
- a record with missing optional hash;
- malformed input handling.

No database import is part of this phase.
