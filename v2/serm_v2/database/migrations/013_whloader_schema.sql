-- WHLoader / Amiberry WHDLoad database
CREATE TABLE IF NOT EXISTS whloader_database_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    source_url TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    schema_version TEXT,
    game_count INTEGER NOT NULL DEFAULT 0,
    scanned_at TEXT NOT NULL,
    raw_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS whloader_game (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    sha1 TEXT,
    name TEXT NOT NULL,
    subpath TEXT,
    slave_default TEXT,
    slave_count INTEGER NOT NULL DEFAULT 0,
    primary_control TEXT,
    port0 TEXT,
    port1 TEXT,
    chipset TEXT,
    cpu TEXT,
    fast_copper INTEGER,
    cpu_compatible INTEGER,
    jit INTEGER,
    screen_autoheight INTEGER,
    screen_centerh TEXT,
    screen_centerv TEXT,
    screen_height INTEGER,
    screen_y_offset INTEGER,
    line_doubling INTEGER,
    ntsc INTEGER,
    sprites TEXT,
    source_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(filename, sha1)
);

CREATE INDEX IF NOT EXISTS idx_whloader_game_name ON whloader_game(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_whloader_game_sha1 ON whloader_game(sha1);
CREATE INDEX IF NOT EXISTS idx_whloader_game_filename ON whloader_game(filename COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS whloader_slave (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES whloader_game(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    datapath TEXT,
    custom_json TEXT,
    UNIQUE(game_id, filename)
);

CREATE INDEX IF NOT EXISTS idx_whloader_slave_game ON whloader_slave(game_id);
CREATE INDEX IF NOT EXISTS idx_whloader_slave_filename ON whloader_slave(filename COLLATE NOCASE);
