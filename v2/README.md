# SERM V2

SERM V2 is the new active architecture of the project.

## V2 rules

- V1 is legacy reference only.
- V2 does not depend on V1 database, models, services, configuration files, XML or tests.
- V2 starts with a clean Home and a new application package.
- SQLite is the local source of truth for SERM-managed data.
- SQLAlchemy is the persistence layer; migrations are versioned.
- External XML/CFG/JSON formats are adapters or generated artifacts when required.
- ROMs, ISOs, CHDs and archives remain in user-selected filesystem locations.

## Initial scope

The first V2 milestone is an executable clean shell with the Home already established as the application entry point. No legacy service is imported.

Next implementation order:

1. data paths and application settings;
2. SQLite engine/session and migration infrastructure;
3. source registry;
4. platform/system identity;
5. catalog and provenance;
6. files/hashes;
7. runtime/emulator/core/execution profiles;
8. source adapters;
9. scan/matching;
10. transformation/reconstruction.
