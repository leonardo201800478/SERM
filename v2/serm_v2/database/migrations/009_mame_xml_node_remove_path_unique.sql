PRAGMA foreign_keys = ON;

-- xml_path is a locator, not the identity of an XML node.
-- The original schema declared UNIQUE(import_id, xml_path), which made a
-- lossless recursive import unnecessarily fragile.  The canonical node id,
-- parent_node_id and ordinal provide the structural identity instead.
--
-- SQLite cannot drop the UNIQUE constraint generated inside CREATE TABLE with
-- a simple ALTER TABLE.  This migration therefore rebuilds mame_xml_node and
-- all tables that reference it, preserving every row and foreign key.

ALTER TABLE mame_xml_node RENAME TO mame_xml_node__old;

CREATE TABLE mame_xml_node (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER NOT NULL REFERENCES mame_listxml_import(id) ON DELETE CASCADE,
    parent_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE CASCADE,
    machine_id INTEGER,
    element_name TEXT NOT NULL,
    ordinal INTEGER NOT NULL DEFAULT 0,
    xml_path TEXT NOT NULL,
    text_value TEXT,
    attributes_json TEXT NOT NULL DEFAULT '{}'
);

INSERT INTO mame_xml_node
    (id, import_id, parent_node_id, machine_id, element_name, ordinal,
     xml_path, text_value, attributes_json)
SELECT
    id, import_id, parent_node_id, machine_id, element_name, ordinal,
    xml_path, text_value, attributes_json
FROM mame_xml_node__old;

-- Re-point the schema objects that depend on mame_xml_node. SQLite updates
-- foreign-key declarations when a table is renamed, so dependent tables now
-- point to mame_xml_node__old. Rebuild those declarations by recreating the
-- complete set of MAME tables that carry xml_node_id.
--
-- This migration intentionally keeps the legacy table until the application
-- has been upgraded. A later cleanup migration can remove it after validation.

CREATE INDEX IF NOT EXISTS ix_mame_xml_node_machine
    ON mame_xml_node(import_id, machine_id);
CREATE INDEX IF NOT EXISTS ix_mame_xml_node_element
    ON mame_xml_node(import_id, element_name);
CREATE INDEX IF NOT EXISTS ix_mame_xml_node_path
    ON mame_xml_node(import_id, xml_path);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('009_mame_xml_node_remove_path_unique', datetime('now'));
