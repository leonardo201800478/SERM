PRAGMA foreign_keys = ON;

-- Compatibilidade: a tabela é criada pela migration 003 para que uma base
-- nova tenha o schema lossless completo em uma única etapa. Esta migration
-- antiga permanece como marcador histórico e não tenta recriar a tabela.
INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('004_mame_raw_document', datetime('now'));
