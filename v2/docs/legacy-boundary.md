# V1 Legacy Boundary

V1 is retained for knowledge only.

## Allowed use

- reading old implementations;
- understanding behavior already validated;
- extracting algorithms and edge cases;
- comparing historical data models;
- creating V2 fixtures from known scenarios;
- documenting lessons learned.

## Forbidden use in V2 runtime

- importing V1 Python modules;
- opening the V1 database;
- reading V1 configuration as required application state;
- writing V1 files;
- depending on V1 JSON/XML/INI structures;
- running V1 tests as V2 tests;
- preserving V1 schema solely for compatibility.

V2 must remain executable when the V1 application database and configuration are absent.
