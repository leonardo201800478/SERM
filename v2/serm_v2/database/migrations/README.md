# V2 Migrations

Migrations in this directory belong exclusively to the V2 schema.

The first migration will be created after the conceptual data model is reviewed. It will not alter or import the V1 schema.

Rules:

- no compatibility tables;
- no unused placeholder columns;
- foreign keys enabled;
- explicit indexes;
- every column has a defined consumer;
- migrations are versioned and tested;
- destructive changes are allowed in V2 during development when they improve the model.
