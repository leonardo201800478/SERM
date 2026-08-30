PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS config_option_translation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    option_id INTEGER NOT NULL REFERENCES config_option(id) ON DELETE CASCADE,
    locale TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    UNIQUE (option_id, locale)
);

CREATE INDEX IF NOT EXISTS ix_config_option_translation_locale
    ON config_option_translation(option_id, locale);

CREATE TABLE IF NOT EXISTS config_group_translation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES config_group(id) ON DELETE CASCADE,
    locale TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    UNIQUE (group_id, locale)
);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('002_configuration_localization', datetime('now'));
