# Redump direct acquisition

SERM V2 now acquires Redump DATs through the per-system direct endpoint instead of scraping the interactive downloads page.

## Endpoint

The direct pattern is:

```text
https://redump.info/datfile/<system-code>/
```

The legacy endpoint is retained as a fallback:

```text
http://redump.org/datfile/<system-code>/
```

The endpoint returns a ZIP containing the DAT for the selected system. SERM requires exactly one file in the ZIP, and that file must be an XML DAT.

## Supported systems

The system/code catalogue is based on the direct Redump endpoint mapping used by oxyromon and covers the currently known direct DAT systems, including PlayStation, PlayStation 2/3, PSP, Dreamcast, Saturn, Mega CD/Sega CD, GameCube, Wii, Xbox, Xbox 360, Neo Geo CD, PC Engine CD, PC-88/98, PC-FX, 3DO, CD-i and the arcade systems exposed by Redump.

## Design goals

- No Selenium.
- No Firefox/geckodriver dependency.
- No CAPTCHA interaction.
- No dependency on the interactive `/downloads/` page.
- Atomic `.part` download replacement.
- SHA-256 provenance in `manifest.json`.
- Automatic fallback from `redump.info` to the legacy `redump.org` endpoint.
- LaunchBox aliases are matched before presenting systems in the GUI.

## Important distinction

The direct DAT endpoint is used for DAT acquisition. Cuesheets and other Redump download-page artifacts are separate resources and should be added as separate acquisition types rather than being mixed into the DAT provider.
