# No-Intro acquisition

## Source

SERM V2 no longer uses DAT-o-MATIC, Selenium, Firefox, geckodriver or per-system No-Intro download pages.

The sole No-Intro acquisition source is the maintained release archive:

`https://github.com/hugo19941994/auto-datfile-generator/releases/latest/download/no-intro_parent-clone.zip`

## Workflow

1. Download one ZIP from the release URL.
2. Store it in `data/sources/no_intro/no-intro_parent-clone.zip`.
3. Extract all `.dat` files belonging to the official parent/clone set.
4. Ignore `Non-Redump`, `Source Code`, `Unofficial`, development-kit and update/DLC variants.
5. Store the accepted DATs in `data/sources/no_intro/dats/`.
6. Build the LaunchBox matching list from the extracted local catalog.

A selected system therefore never causes another HTTP request to No-Intro. The individual DAT is already local after the archive acquisition.

## Cache and provenance

`data/sources/no_intro/manifest.json` records the archive URL, archive SHA-256 and the number/names of extracted DATs.

The archive is intentionally refreshed only when the user requests a catalog refresh/update. Normal selection and download operations work from the extracted local DATs.

## Categories

The release archive contains official No-Intro DATs mixed with auxiliary collections. The provider filters these prefixes:

- `Non-Redump -`
- `Source Code -`
- `Unofficial -`

It also excludes development-kit and update/DLC variants from the main system catalog.

## Why this design

The previous No-Intro implementation depended on DAT-o-MATIC page structure and browser automation. That caused failures when the website changed form fields or required browser interaction. The bulk release has a deterministic URL and turns acquisition into one ordinary ZIP download followed by local extraction.
