# Auditoria inicial — MAME Set Builder

> **Documento histórico.** Para o estado atual, consulte `AUDIT_NOTES.md`, `README.md` e `docs/phases.md`.

A auditoria original identificou limitações de parser, banco, scanner e reconstrução que motivaram a evolução posterior. Ela não deve ser usada como descrição da implementação atual.

## Regra atual

O código do GitHub é a fonte de verdade. Itens descritos neste documento podem ter sido corrigidos posteriormente.

## Principais temas históricos

- preservação completa do `listxml`;
- integração entre modelos e schema;
- scanner físico e hashes;
- associação Machine ↔ arquivo;
- reconstrução segura sem alterar o FULLSET;
- resolução de dependências;
- integração futura com torrent.

Consulte `AUDIT_NOTES.md` para o estado atualizado e `docs/architecture.md` para a arquitetura vigente.
