SCHEMA = """

PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS machine
(
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT UNIQUE,

    description TEXT,

    cloneof TEXT,

    romof TEXT,

    manufacturer TEXT,

    year TEXT,

    sourcefile TEXT,

    runnable INTEGER,

    isbios INTEGER,

    isdevice INTEGER,

    ismechanical INTEGER,

    working INTEGER,

    players INTEGER
);

CREATE INDEX IF NOT EXISTS idx_machine_name
ON machine(name);

CREATE INDEX IF NOT EXISTS idx_machine_source
ON machine(sourcefile);

CREATE INDEX IF NOT EXISTS idx_machine_working
ON machine(working);

CREATE INDEX IF NOT EXISTS idx_machine_mechanical
ON machine(ismechanical);

CREATE INDEX IF NOT EXISTS idx_machine_device
ON machine(isdevice);

"""