# LaunchBox Provider — SERM V2

## Objetivo

O LaunchBox é um provider local de referência para o SERM V2. Nesta primeira implementação, o acesso é estritamente somente leitura.

## Fontes locais

A integração usa a instalação descoberta/configurada por `LaunchBoxIntegration` e pode acessar:

- `Metadata/LaunchBox.Metadata.db`;
- `Metadata/Platforms.xml`.

Outros arquivos (`MAME.xml`, `Files.xml`, caches etc.) serão adicionados somente quando houver um caso de uso definido.

## Segurança e isolamento

O provider:

- não escreve no LaunchBox;
- não altera `LaunchBox.Metadata.db`;
- não altera `Platforms.xml`;
- abre o SQLite em modo `ro`;
- não importa dados automaticamente para o banco SERM V2;
- não depende do LaunchBox para iniciar o SERM.

## API inicial

`LaunchBoxProvider` expõe:

- `metadata_database()`;
- `platforms_xml()`;
- `database_tables()`;
- `table_columns(table)`;
- `iter_games(limit=None)`;
- `iter_platforms()`.

`LaunchBoxGame` e `LaunchBoxPlatform` são modelos intermediários do provider. Eles ainda não são entidades do banco SERM.

## Fluxo futuro

```text
LaunchBox
  ↓
LaunchBoxProvider
  ↓
Provider models
  ↓
Normalizer
  ↓
Staging
  ↓
SERM Data Foundation
```

A etapa seguinte é auditar as tabelas e campos reais do `LaunchBox.Metadata.db` e confrontá-los com `Platforms.xml`, antes de definir quais dados entram no modelo canônico V2.
