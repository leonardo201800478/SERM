PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS emulator_definition (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    family TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS config_scope (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    precedence INTEGER NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS config_group (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emulator_id INTEGER NOT NULL REFERENCES emulator_definition(id) ON DELETE CASCADE,
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE (emulator_id, slug)
);

CREATE TABLE IF NOT EXISTS config_option (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emulator_id INTEGER NOT NULL REFERENCES emulator_definition(id) ON DELETE CASCADE,
    group_id INTEGER REFERENCES config_group(id) ON DELETE SET NULL,
    key TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    value_type TEXT NOT NULL,
    control_type TEXT NOT NULL,
    default_value TEXT,
    min_value REAL,
    max_value REAL,
    step_value REAL,
    unit TEXT,
    scope_slug TEXT NOT NULL DEFAULT 'global',
    applies_when TEXT,
    driver_family TEXT,
    advanced INTEGER NOT NULL DEFAULT 0 CHECK (advanced IN (0,1)),
    read_only INTEGER NOT NULL DEFAULT 0 CHECK (read_only IN (0,1)),
    source_kind TEXT NOT NULL DEFAULT 'emulator',
    source_version TEXT,
    source_reference TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE (emulator_id, key),
    FOREIGN KEY (emulator_id, scope_slug) REFERENCES emulator_definition(id, slug) DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX IF NOT EXISTS ix_config_option_emulator_group
    ON config_option(emulator_id, group_id, sort_order);
CREATE INDEX IF NOT EXISTS ix_config_option_scope
    ON config_option(emulator_id, scope_slug);

CREATE TABLE IF NOT EXISTS config_option_value (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    option_id INTEGER NOT NULL REFERENCES config_option(id) ON DELETE CASCADE,
    value TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0,1)),
    UNIQUE (option_id, value)
);

CREATE TABLE IF NOT EXISTS config_option_dependency (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    option_id INTEGER NOT NULL REFERENCES config_option(id) ON DELETE CASCADE,
    depends_on_option_id INTEGER NOT NULL REFERENCES config_option(id) ON DELETE CASCADE,
    operator TEXT NOT NULL,
    expected_value TEXT,
    effect TEXT NOT NULL,
    reason TEXT,
    UNIQUE (option_id, depends_on_option_id, operator, expected_value, effect)
);

CREATE INDEX IF NOT EXISTS ix_config_dependency_option
    ON config_option_dependency(option_id);
CREATE INDEX IF NOT EXISTS ix_config_dependency_parent
    ON config_option_dependency(depends_on_option_id);

CREATE TABLE IF NOT EXISTS config_file_binding (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emulator_id INTEGER NOT NULL REFERENCES emulator_definition(id) ON DELETE CASCADE,
    scope_slug TEXT NOT NULL,
    target_key TEXT,
    file_path TEXT NOT NULL,
    file_format TEXT NOT NULL,
    precedence INTEGER NOT NULL,
    writable INTEGER NOT NULL DEFAULT 1 CHECK (writable IN (0,1)),
    preserve_unknown INTEGER NOT NULL DEFAULT 1 CHECK (preserve_unknown IN (0,1)),
    preserve_comments INTEGER NOT NULL DEFAULT 1 CHECK (preserve_comments IN (0,1)),
    UNIQUE (emulator_id, scope_slug, target_key, file_path)
);

CREATE TABLE IF NOT EXISTS config_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emulator_id INTEGER NOT NULL REFERENCES emulator_definition(id) ON DELETE CASCADE,
    scope_slug TEXT NOT NULL,
    name TEXT NOT NULL,
    target_key TEXT,
    parent_profile_id INTEGER REFERENCES config_profile(id) ON DELETE SET NULL,
    profile_kind TEXT NOT NULL DEFAULT 'generated',
    status TEXT NOT NULL DEFAULT 'draft',
    generated_by TEXT,
    source_version TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (emulator_id, scope_slug, name, target_key)
);

CREATE INDEX IF NOT EXISTS ix_config_profile_target
    ON config_profile(emulator_id, scope_slug, target_key);

CREATE TABLE IF NOT EXISTS config_profile_value (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES config_profile(id) ON DELETE CASCADE,
    option_id INTEGER NOT NULL REFERENCES config_option(id) ON DELETE CASCADE,
    value TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'user',
    locked INTEGER NOT NULL DEFAULT 0 CHECK (locked IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (profile_id, option_id)
);

CREATE TABLE IF NOT EXISTS config_observation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emulator_id INTEGER NOT NULL REFERENCES emulator_definition(id) ON DELETE CASCADE,
    executable TEXT NOT NULL,
    version TEXT,
    observed_at TEXT NOT NULL,
    command TEXT NOT NULL,
    output_hash TEXT,
    status TEXT NOT NULL,
    raw_output_path TEXT
);

CREATE TABLE IF NOT EXISTS hardware_capability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capability_key TEXT NOT NULL UNIQUE,
    value_type TEXT NOT NULL,
    value TEXT,
    detected_by TEXT,
    detected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS config_option_capability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    option_id INTEGER NOT NULL REFERENCES config_option(id) ON DELETE CASCADE,
    capability_key TEXT NOT NULL REFERENCES hardware_capability(capability_key) ON DELETE CASCADE,
    operator TEXT NOT NULL,
    expected_value TEXT,
    effect TEXT NOT NULL,
    reason TEXT,
    UNIQUE (option_id, capability_key, operator, expected_value, effect)
);

INSERT OR IGNORE INTO config_scope(slug, name, precedence, description) VALUES
('global', 'Global', 10, 'Configuração global do emulador.'),
('orientation', 'Orientação', 20, 'Configuração por orientação da tela.'),
('monitor', 'Monitor', 30, 'Configuração por tipo de monitor.'),
('source', 'Driver/Fonte', 40, 'Configuração associada ao driver/source.'),
('bios', 'BIOS', 50, 'Configuração herdada pelo conjunto BIOS.'),
('parent', 'Parent', 60, 'Configuração herdada pelo sistema pai.'),
('system', 'Sistema/Jogo', 70, 'Configuração específica da máquina.'),
('runtime', 'Runtime', 100, 'Override explícito de execução/linha de comando.');

INSERT OR IGNORE INTO emulator_definition(slug, name, family, created_at, updated_at) VALUES
('mame', 'MAME', 'arcade', datetime('now'), datetime('now')),
('fbneo', 'FinalBurn Neo', 'arcade', datetime('now'), datetime('now')),
('flycast', 'Flycast', 'console_arcade', datetime('now'), datetime('now')),
('supermodel', 'Supermodel', 'arcade', datetime('now'), datetime('now')),
('retroarch', 'RetroArch', 'frontend_emulator_host', datetime('now'), datetime('now'));

INSERT OR IGNORE INTO config_group(emulator_id, slug, name, description, sort_order)
SELECT id, 'video', 'Vídeo', 'Renderização, sincronização e geometria.', 10 FROM emulator_definition WHERE slug='mame';
INSERT OR IGNORE INTO config_group(emulator_id, slug, name, description, sort_order)
SELECT id, 'audio', 'Áudio', 'Backend, sample rate, volume e latência.', 20 FROM emulator_definition WHERE slug='mame';
INSERT OR IGNORE INTO config_group(emulator_id, slug, name, description, sort_order)
SELECT id, 'input', 'Controles', 'Dispositivos e comportamento de entrada.', 30 FROM emulator_definition WHERE slug='mame';
INSERT OR IGNORE INTO config_group(emulator_id, slug, name, description, sort_order)
SELECT id, 'paths', 'Diretórios', 'Caminhos pesquisados e diretórios de saída.', 40 FROM emulator_definition WHERE slug='mame';
INSERT OR IGNORE INTO config_group(emulator_id, slug, name, description, sort_order)
SELECT id, 'performance', 'Desempenho', 'Frame pacing, throttling e latência.', 50 FROM emulator_definition WHERE slug='mame';
INSERT OR IGNORE INTO config_group(emulator_id, slug, name, description, sort_order)
SELECT id, 'system', 'Sistema', 'Idioma, BIOS, plugins e comportamento geral.', 60 FROM emulator_definition WHERE slug='mame';
INSERT OR IGNORE INTO config_group(emulator_id, slug, name, description, sort_order)
SELECT id, 'debug', 'Avançado/Debug', 'Opções de diagnóstico e desenvolvimento.', 90 FROM emulator_definition WHERE slug='mame';

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('001_configuration_schema', datetime('now'));
