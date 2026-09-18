# V2 Migrations

As migrations desta pasta pertencem exclusivamente ao schema SQLite da V2.

## Regras

- não importar schema da V1;
- foreign keys habilitadas quando a migration exigir relações;
- índices explícitos para caminhos de consulta relevantes;
- toda coluna precisa ter consumidor definido;
- migrations devem ser idempotentes sempre que tecnicamente possível;
- mudanças destrutivas são permitidas durante o desenvolvimento Alpha quando melhorarem o modelo;
- cada migration recebe um identificador numérico único;
- nunca criar duas migrations com o mesmo prefixo numérico;
- uma migration já publicada não deve ser reescrita para alterar comportamento: crie uma nova migration.

## Sequência atual

```text
001–012  configuração e catálogo MAME
013      mame_resolution_sources
014      rom_scan_schema
015      whloader_schema
016      mame_vsync_sources
017      scan_filter_pipeline
```

Os identificadores `013_rom_scan_schema`, `013_whloader_schema`, `014_mame_vsync_sources` e `014_scan_filter_pipeline` foram normalizados para eliminar colisões de versão. Os nomes antigos não devem voltar a ser utilizados.

## Bootstrap

`serm_v2/database/bootstrap.py` descobre automaticamente arquivos no padrão `[0-9][0-9][0-9]_*.sql`, ordena-os pelo nome e registra as versões aplicadas em `schema_migrations`.

Uma migration pode conter `INSERT OR IGNORE INTO schema_migrations(...)` para registrar sua aplicação. O bootstrap também possui tratamento especial para compatibilidade com estruturas antigas do catálogo MAME.

## Alterações de schema

Ao alterar o banco:

1. crie uma migration com o próximo número livre;
2. atualize os modelos/serviços afetados;
3. atualize testes;
4. valide banco limpo;
5. valide upgrade a partir de uma base anterior;
6. confirme que `schema_migrations` registra a nova versão.
